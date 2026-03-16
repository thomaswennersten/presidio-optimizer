"""
FastAPI-applikation för Presidio Optimizer.

Endpoints för sessionshantering, dokumentuppladdning, analys,
feedback, LLM-optimering och konfigurationsexport.
"""

import os
import uuid
import hashlib
import secrets
import logging
import asyncio
import aiofiles
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from presidio_service import PresidioService
from document_processor import DocumentProcessor
from config_manager import ConfigManager, PresidioConfig, get_default_config, EntityConfig, RecognizerDefinition, RecognizerPattern
from feedback_processor import process_feedback
from llm_optimizer import optimize_config
from session_store import SessionStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Presidio Optimizer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
presidio = PresidioService()
doc_processor = DocumentProcessor()
config_manager = ConfigManager()
session_store = SessionStore()

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "/tmp/uploads")
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", 10 * 1024 * 1024))
ALLOWED_EXTENSIONS = {"docx", "xlsx", "pdf", "txt"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Authentication ---

APP_PASSWORD = os.environ.get("APP_PASSWORD", "eghed")
auth_tokens: set = set()


class LoginRequest(BaseModel):
    password: str


class CreateSessionRequest(BaseModel):
    name: str


def require_auth(request: Request):
    """Dependency that checks for valid auth token."""
    token = request.headers.get("X-Auth-Token", "")
    if token not in auth_tokens:
        raise HTTPException(401, "Unauthorized")


@app.post("/api/login")
async def login(req: LoginRequest):
    if req.password != APP_PASSWORD:
        raise HTTPException(401, "Fel lösenord")
    token = secrets.token_hex(32)
    auth_tokens.add(token)
    return {"token": token}


@app.get("/api/auth/check")
async def auth_check(request: Request):
    token = request.headers.get("X-Auth-Token", "")
    if token in auth_tokens:
        return {"authenticated": True}
    raise HTTPException(401, "Unauthorized")


# --- Pydantic models ---

class FeedbackItem(BaseModel):
    start: int
    end: int
    entity_type: str
    text: Optional[str] = ""
    score: Optional[float] = 0.0


class FeedbackRequest(BaseModel):
    false_positives: List[FeedbackItem] = []
    false_negatives: List[FeedbackItem] = []


class ThresholdUpdate(BaseModel):
    entity_type: str
    threshold: float


# --- Endpoints ---

@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "presidio-optimizer", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/session")
async def create_session(req: CreateSessionRequest, _=Depends(require_auth)):
    """Create a new named optimization session."""
    meta = session_store.create_session(req.name)
    session_id = meta["id"]

    config = get_default_config()
    config_manager.save_config(session_id, config)

    return {"session_id": session_id, "name": meta["name"], "config_version": 1}


@app.get("/api/sessions")
async def list_sessions(_=Depends(require_auth)):
    """List all sessions."""
    sessions = session_store.list_sessions()
    return {"sessions": sessions}


@app.post("/api/session/{session_id}/upload")
async def upload_document(session_id: str, file: UploadFile = File(...), _=Depends(require_auth)):
    """Upload a document for analysis."""
    if not session_store.session_exists(session_id):
        raise HTTPException(404, "Session not found")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type '{ext}' not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Max: {MAX_FILE_SIZE // (1024*1024)} MB")

    filepath = os.path.join(UPLOAD_FOLDER, f"{session_id}_{file.filename}")
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(content)

    try:
        text = await doc_processor.extract_text(filepath, ext)
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

    session_store.save_text(session_id, text, file.filename)

    return {
        "filename": file.filename,
        "text_length": len(text),
        "text_preview": text[:500],
    }


@app.post("/api/session/{session_id}/analyze")
async def analyze(session_id: str, _=Depends(require_auth)):
    """Run Presidio analysis with current config."""
    if not session_store.session_exists(session_id):
        raise HTTPException(404, "Session not found")

    text = session_store.load_text(session_id)
    if not text:
        raise HTTPException(400, "No document uploaded yet")

    config = config_manager.load_config(session_id)
    if not config:
        config = get_default_config()

    results = presidio.analyze_with_config(text, config)
    session_store.save_analysis_results(session_id, results)

    # Enrich results with text snippets
    enriched = []
    for r in results:
        enriched.append({
            **r,
            "text": text[r["start"]:r["end"]],
        })

    return {
        "results": enriched,
        "total": len(enriched),
        "config_version": config.version,
        "text": text,
    }


@app.post("/api/session/{session_id}/feedback")
async def submit_feedback(session_id: str, feedback: FeedbackRequest, _=Depends(require_auth)):
    """Submit false positive/negative feedback."""
    if not session_store.session_exists(session_id):
        raise HTTPException(404, "Session not found")

    fb_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "false_positives": [fp.dict() for fp in feedback.false_positives],
        "false_negatives": [fn.dict() for fn in feedback.false_negatives],
    }
    session_store.append_feedback(session_id, fb_entry)

    return {
        "status": "feedback_received",
        "false_positives": len(feedback.false_positives),
        "false_negatives": len(feedback.false_negatives),
    }


@app.post("/api/session/{session_id}/optimize")
async def optimize(session_id: str, _=Depends(require_auth)):
    """Trigger LLM optimization based on latest feedback."""
    if not session_store.session_exists(session_id):
        raise HTTPException(404, "Session not found")

    feedback_history = session_store.get_feedback_history(session_id)
    if not feedback_history:
        raise HTTPException(400, "No feedback submitted yet")

    text = session_store.load_text(session_id)
    analysis_results = session_store.load_analysis_results(session_id)
    latest_fb = feedback_history[-1]

    # Process feedback
    structured_feedback = process_feedback(
        text=text,
        analysis_results=analysis_results,
        false_positives=latest_fb["false_positives"],
        false_negatives=latest_fb["false_negatives"],
    )

    # Get current config
    config = config_manager.load_config(session_id)
    if not config:
        config = get_default_config()

    # Call LLM
    llm_result = await optimize_config(
        current_config=config.to_dict(),
        feedback=structured_feedback,
        text_sample=text[:1000],
    )

    # Apply changes to create new config version
    new_config = config_manager.create_next_version(
        session_id, config,
        description=llm_result.get("reasoning", "LLM optimization")[:200],
    )

    changes = llm_result.get("changes", [])
    _apply_changes(new_config, changes)

    config_manager.save_config(session_id, new_config)
    session_store.update_session(session_id, {
        "current_config_version": new_config.version,
    })

    # Spara optimeringsresultat persistent
    opt_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "reasoning": llm_result.get("reasoning", ""),
        "changes": changes,
        "expected_improvements": llm_result.get("expected_improvements", ""),
        "new_config_version": new_config.version,
    }
    session_store.append_optimization(session_id, opt_entry)

    return {
        "reasoning": llm_result.get("reasoning", ""),
        "changes": changes,
        "expected_improvements": llm_result.get("expected_improvements", ""),
        "new_config_version": new_config.version,
        "raw_response": llm_result.get("raw_response", None),
    }


@app.post("/api/session/{session_id}/reanalyze")
async def reanalyze(session_id: str, _=Depends(require_auth)):
    """Reanalyze with new config and return comparison."""
    if not session_store.session_exists(session_id):
        raise HTTPException(404, "Session not found")

    text = session_store.load_text(session_id)
    if not text:
        raise HTTPException(400, "No document uploaded")

    old_results = session_store.load_analysis_results(session_id)

    config = config_manager.load_config(session_id)
    if not config:
        config = get_default_config()

    new_results = presidio.analyze_with_config(text, config)
    session_store.save_analysis_results(session_id, new_results)

    # Enrich results
    enriched_old = [{**r, "text": text[r["start"]:r["end"]]} for r in old_results]
    enriched_new = [{**r, "text": text[r["start"]:r["end"]]} for r in new_results]

    # Compute diff
    old_set = {(r["start"], r["end"], r["entity_type"]) for r in old_results}
    new_set = {(r["start"], r["end"], r["entity_type"]) for r in new_results}

    added = new_set - old_set
    removed = old_set - new_set

    return {
        "old_results": enriched_old,
        "new_results": enriched_new,
        "comparison": {
            "old_count": len(old_results),
            "new_count": len(new_results),
            "added": len(added),
            "removed": len(removed),
        },
        "config_version": config.version,
        "text": text,
    }


@app.get("/api/session/{session_id}/config")
async def get_config(session_id: str, _=Depends(require_auth)):
    """Get current configuration."""
    config = config_manager.load_config(session_id)
    if not config:
        raise HTTPException(404, "No config found")
    return config.to_dict()


@app.get("/api/session/{session_id}/config/history")
async def get_config_history(session_id: str, _=Depends(require_auth)):
    """List all config versions."""
    history = config_manager.get_config_history(session_id)
    return {"versions": history}


@app.get("/api/session/{session_id}/config/export")
async def export_config(session_id: str, version: Optional[int] = None, format: str = "json", _=Depends(require_auth)):
    """Export config as JSON or YAML."""
    exported = config_manager.export_config(session_id, version, format)
    if not exported:
        raise HTTPException(404, "Config not found")
    return {"format": format, "content": exported}


@app.get("/api/session/{session_id}/files")
async def list_session_files(session_id: str, _=Depends(require_auth)):
    """Lista nedladdningsbara filer för en session."""
    if not session_store.session_exists(session_id):
        raise HTTPException(404, "Session not found")
    files = session_store.list_files(session_id)
    return {"files": files}


@app.get("/api/session/{session_id}/download/{filename:path}")
async def download_file(session_id: str, filename: str, _=Depends(require_auth)):
    """Ladda ner en fil från sessionen."""
    if not session_store.session_exists(session_id):
        raise HTTPException(404, "Session not found")

    # Hämta nedladdningsnamn med sessionsnamn
    files = session_store.list_files(session_id)
    download_name = filename
    is_virtual = False
    for f in files:
        if f["filename"] == filename:
            download_name = f["download_name"]
            is_virtual = f.get("virtual", False)
            break

    # Virtuella YAML-filer: generera från JSON on-the-fly
    if is_virtual and filename.endswith(".yaml"):
        json_filename = filename.replace(".yaml", ".json")
        json_path = session_store.get_file_path(session_id, json_filename)
        if not json_path:
            raise HTTPException(404, "Source config not found")
        import json, tempfile
        with open(json_path, "r", encoding="utf-8") as jf:
            data = json.load(jf)
        try:
            import yaml
            yaml_content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
        except ImportError:
            yaml_content = json.dumps(data, ensure_ascii=False, indent=2)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml", mode="w", encoding="utf-8")
        tmp.write(yaml_content)
        tmp.close()
        return FileResponse(tmp.name, filename=download_name, media_type="application/x-yaml")

    path = session_store.get_file_path(session_id, filename)
    if not path:
        raise HTTPException(404, "File not found")

    return FileResponse(path, filename=download_name)


@app.get("/api/session/{session_id}/report")
async def get_report(session_id: str, _=Depends(require_auth)):
    """Generera och hämta rapport."""
    if not session_store.session_exists(session_id):
        raise HTTPException(404, "Session not found")
    report = session_store.generate_report(session_id)
    return {"report": report}


# --- Helpers ---

def _apply_changes(config: PresidioConfig, changes: list):
    """Apply LLM-suggested changes to a config."""
    for change in changes:
        action = change.get("action", "")
        target = change.get("target", "")
        details = change.get("details", {})

        try:
            if action == "add_recognizer":
                patterns = []
                for p in details.get("patterns", []):
                    patterns.append(RecognizerPattern(
                        name=p.get("name", ""),
                        regex=p.get("regex", ""),
                        score=p.get("score", 0.6),
                    ))
                rec = RecognizerDefinition(
                    name=target,
                    entity_type=details.get("entity_type", ""),
                    patterns=patterns,
                    deny_list=details.get("deny_list", []),
                    context_words=details.get("context_words", []),
                    supported_language=details.get("supported_language", "sv"),
                )
                config.custom_recognizers.append(rec)
                logger.info(f"Added recognizer: {target}")

            elif action == "modify_recognizer":
                for rec in config.custom_recognizers:
                    if rec.name == target:
                        if "patterns" in details:
                            rec.patterns = [
                                RecognizerPattern(**p) for p in details["patterns"]
                            ]
                        if "deny_list" in details:
                            rec.deny_list = details["deny_list"]
                        if "context_words" in details:
                            rec.context_words = details["context_words"]
                        logger.info(f"Modified recognizer: {target}")
                        break

            elif action == "adjust_threshold":
                new_threshold = details.get("new_threshold", 0.5)
                if target in config.entity_settings:
                    config.entity_settings[target].threshold = new_threshold
                else:
                    config.entity_settings[target] = EntityConfig(
                        enabled=True, threshold=new_threshold, label=target,
                    )
                logger.info(f"Adjusted threshold for {target}: {new_threshold}")

            elif action == "toggle_entity":
                enabled = details.get("enabled", True)
                if target in config.entity_settings:
                    config.entity_settings[target].enabled = enabled
                else:
                    config.entity_settings[target] = EntityConfig(
                        enabled=enabled, threshold=0.5, label=target,
                    )
                logger.info(f"Toggled {target}: enabled={enabled}")

            elif action == "adjust_global_threshold":
                new_threshold = details.get("new_threshold", 0.5)
                config.score_threshold = new_threshold
                logger.info(f"Adjusted global threshold: {new_threshold}")

            else:
                logger.warning(f"Unknown action: {action}")

        except Exception as e:
            logger.error(f"Error applying change {action} on {target}: {e}")
