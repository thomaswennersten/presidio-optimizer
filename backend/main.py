# Presidio Optimizer
# Copyright (C) 2026 Sambruk
#
# Detta program är fri programvara; du får sprida och ändra det enligt
# villkoren i GNU General Public License version 2, som den publicerats av
# Free Software Foundation.
#
# Programmet distribueras i hopp om att det ska vara användbart, men UTAN
# NÅGON GARANTI. Se GNU General Public License för fler detaljer.
# Se filen LICENSE.

"""
FastAPI-applikation för Presidio Optimizer.

Endpoints för sessionshantering, dokumentuppladdning, analys,
feedback, LLM-optimering och konfigurationsexport.
"""

import os
import re
import time
import json
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

# Tokens sparas på disk. Tidigare låg de i en set() i minnet, och eftersom
# uvicorn kör med --reload mot en bind-monterad katalog räckte det att en fil
# ändrades för att alla skulle loggas ut mitt i en session. Nu överlever de både
# omladdning och omstart av containern.
TOKEN_FIL = os.path.join(os.environ.get("CONFIG_DIR", "/app/db/sessions"), "..", "auth_tokens.json")
TOKEN_GILTIGHET_DYGN = 14


def _las_tokens() -> dict:
    try:
        with open(TOKEN_FIL, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    nu = time.time()
    return {t: exp for t, exp in data.items() if exp > nu}


def _skriv_tokens(tokens: dict):
    try:
        os.makedirs(os.path.dirname(os.path.abspath(TOKEN_FIL)), exist_ok=True)
        with open(TOKEN_FIL, "w", encoding="utf-8") as f:
            json.dump(tokens, f)
    except OSError as e:
        logger.error(f"Kunde inte spara tokens: {e}")


def _token_giltig(token: str) -> bool:
    if not token:
        return False
    return token in _las_tokens()


class LoginRequest(BaseModel):
    password: str


class CreateSessionRequest(BaseModel):
    name: str


def require_auth(request: Request):
    """Dependency that checks for valid auth token."""
    token = request.headers.get("X-Auth-Token", "")
    if not _token_giltig(token):
        raise HTTPException(401, "Unauthorized")


@app.post("/api/login")
async def login(req: LoginRequest):
    if req.password != APP_PASSWORD:
        raise HTTPException(401, "Fel lösenord")
    token = secrets.token_hex(32)
    tokens = _las_tokens()
    tokens[token] = time.time() + TOKEN_GILTIGHET_DYGN * 86400
    _skriv_tokens(tokens)
    return {"token": token}


@app.get("/api/auth/check")
async def auth_check(request: Request):
    token = request.headers.get("X-Auth-Token", "")
    if _token_giltig(token):
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
    # Etiketterna för egna typer, t.ex. {"PRIS_EXKL_MOMS": "Pris exklusive moms"}.
    # Skrivs in i regelverkets entity_settings så att maskera kan visa det namn
    # verksamheten faktiskt skrev. Utan detta känner regelverket bara till det
    # normaliserade typnamnet, och etiketten stannar i optimizerns webbläsare.
    etiketter: Dict[str, str] = {}


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

    sparade = _spara_etiketter(session_id, feedback.etiketter)

    return {
        "status": "feedback_received",
        "false_positives": len(feedback.false_positives),
        "false_negatives": len(feedback.false_negatives),
        "etiketter": sparade,
    }


def _spara_etiketter(session_id: str, etiketter: Dict[str, str]) -> int:
    """Skriv in etiketter för egna typer i regelverkets entity_settings.

    `save_config` skriver till `{version}.json` och stegar INTE versionen, så
    det här skriver över den nuvarande versionen i stället för att skapa en ny.
    Det är avsikten: en etikett är inte en regeländring och ska inte se ut som
    en ny iteration i historiken.
    """
    if not etiketter:
        return 0
    config = config_manager.load_config(session_id) or get_default_config()
    antal = 0
    for typ, etikett in etiketter.items():
        typ = str(typ or "").strip().upper()
        etikett = str(etikett or "").strip()[:80]
        if not typ or not etikett:
            continue
        post = config.entity_settings.get(typ)
        if post is None:
            config.entity_settings[typ] = EntityConfig(enabled=True, threshold=0.5,
                                                       label=etikett)
        elif post.label != etikett:
            post.label = etikett
        else:
            continue
        antal += 1
    if antal:
        config_manager.save_config(session_id, config)
        logger.info(f"Etiketter sparade i regelverket: {antal} st")
    return antal


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

    # Misslyckad optimering får INTE spara en ny konfigurationsversion. Tidigare
    # ökade versionsräknaren även vid API-fel, vilket såg ut som att något hänt.
    if llm_result.get("fel"):
        return {
            "fel": llm_result["fel"],
            "reasoning": llm_result.get("reasoning", ""),
            "changes": [],
            "expected_improvements": "",
            "new_config_version": config.version,
        }

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
        "fel": llm_result.get("fel"),
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


# Optimizern skriver till db/sessions/<id>/configs/ men pii-mask-mcp monterar
# db/configs/ — publicering kopierar mellan dem.
SESSIONS_DIR = os.environ.get("CONFIG_DIR", "/app/db/sessions")
PUBLICERAD_DIR = os.path.join(os.path.dirname(SESSIONS_DIR.rstrip("/")), "configs")


def _slugga(namn: str) -> str:
    """Kort, filsäkert katalognamn — det är detta som syns som config_id i maskera."""
    import re as _re
    s = (namn or "").strip().lower()
    s = s.replace("å", "a").replace("ä", "a").replace("ö", "o")
    s = _re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:40] or "regelverk"


@app.post("/api/session/{session_id}/publish")
async def publish_config(session_id: str, _=Depends(require_auth)):
    """Publicera sessionens regelverk så maskera-applikationen kan använda det.

    Optimizern skriver till db/sessions/<id>/configs/, men pii-mask-mcp monterar
    db/configs/ — samma filformat, olika plats. Utan detta steg når ett nytt
    regelverk aldrig maskeringen.
    """
    if not session_store.session_exists(session_id):
        raise HTTPException(404, "Session not found")

    kalla = os.path.join(SESSIONS_DIR, session_id, "configs")
    if not os.path.isdir(kalla):
        raise HTTPException(400, "Sessionen har inga sparade regelverk att publicera")

    versioner = sorted(
        int(f[:-5]) for f in os.listdir(kalla) if f.endswith(".json") and f[:-5].isdigit()
    )
    if not versioner:
        raise HTTPException(400, "Sessionen har inga sparade regelverk att publicera")

    sess = session_store.get_session(session_id) or {}
    namn = _slugga(sess.get("name", "")) + "-" + session_id[:6]
    mal = os.path.join(PUBLICERAD_DIR, namn)
    os.makedirs(mal, exist_ok=True)

    import shutil
    for v in versioner:
        shutil.copy2(os.path.join(kalla, f"{v}.json"), os.path.join(mal, f"{v}.json"))

    # Härkomst i klartext. Utan detta blir väljaren i maskera en lista med
    # uuid:er och LLM-skrivna utvärderingsstycken — omöjlig att orientera sig i.
    with open(os.path.join(mal, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({
            "kalla": "presidio-optimizer",
            "session_namn": sess.get("name", ""),
            "session_id": session_id,
            "publicerad": datetime.utcnow().isoformat() + "Z",
            "versioner": versioner,
        }, f, ensure_ascii=False, indent=2)

    logger.info(f"Publicerade {len(versioner)} version(er) till {mal}")
    return {
        "config_id": namn,
        "versioner": versioner,
        "senaste_version": versioner[-1],
        "sokvag": mal,
    }


def _publicerad_sokvag(config_id: str) -> str:
    """Validerar och löser ut sökvägen till ett publicerat regelverk.

    Två spärrar: id:t måste vara enkla tecken, och den utlösta sökvägen måste
    ligga KVAR inuti katalogen. Utan den andra kontrollen skulle "../../etc"
    kunna ta sig ut, även om den första gör det osannolikt.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]+", config_id or ""):
        raise HTTPException(400, "Ogiltigt regelverks-id")
    bas = os.path.abspath(PUBLICERAD_DIR)
    mal = os.path.abspath(os.path.join(bas, config_id))
    if os.path.commonpath([bas, mal]) != bas:
        raise HTTPException(400, "Ogiltig sökväg")
    return mal


def _publicerade_fran(session_id: str) -> list:
    """Regelverk i maskeras katalog som kommer från den här sessionen.

    Behövs för att kunna säga rakt ut vad som INTE försvinner när en session
    tas bort. Ett publicerat regelverk kan vara i drift, och den som städar
    bland sina sessioner ska inte behöva gissa om driften påverkas.
    """
    ut = []
    if not os.path.isdir(PUBLICERAD_DIR):
        return ut
    for namn in sorted(os.listdir(PUBLICERAD_DIR)):
        meta_sokvag = os.path.join(PUBLICERAD_DIR, namn, "meta.json")
        try:
            with open(meta_sokvag, encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("session_id") == session_id:
            ut.append({"config_id": namn, "namn": meta.get("session_namn") or namn})
    return ut


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str, _=Depends(require_auth)):
    """Ta bort en session med text, feedback, iterationer och filer.

    Publicerade regelverk ligger kvar i maskera — de är en kopia i db/configs
    och tas bort separat i panelen "Publicerade regelverk". Svaret räknar upp
    vilka de är, så gränssnittet kan säga det i klartext i stället för att
    lämna användaren i tron att allt försvann.
    """
    if not session_store.session_exists(session_id):
        raise HTTPException(404, "Sessionen finns inte")

    kvar = _publicerade_fran(session_id)
    if not session_store.delete_session(session_id):
        raise HTTPException(400, "Ogiltigt sessions-id")

    logger.info(f"Tog bort session {session_id}"
                + (f" — {len(kvar)} publicerade regelverk ligger kvar" if kvar else ""))
    return {"borttagen": session_id, "publicerade_kvar": kvar}


@app.get("/api/published")
async def list_published(_=Depends(require_auth)):
    """Regelverk som publicerats till maskera-applikationen."""
    if not os.path.isdir(PUBLICERAD_DIR):
        return {"publicerade": []}
    ut = []
    for namn in sorted(os.listdir(PUBLICERAD_DIR)):
        d = os.path.join(PUBLICERAD_DIR, namn)
        if not os.path.isdir(d):
            continue
        versioner = sorted(
            int(f[:-5]) for f in os.listdir(d)
            if f.endswith(".json") and f[:-5].isdigit()
        )
        if not versioner:
            continue
        meta = {}
        try:
            with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
        skapad = ""
        try:
            with open(os.path.join(d, f"{versioner[-1]}.json"), encoding="utf-8") as f:
                skapad = (json.load(f) or {}).get("created_at", "")
        except (OSError, json.JSONDecodeError):
            pass
        ut.append({
            "config_id": namn,
            "namn": meta.get("session_namn") or namn,
            "session_id": meta.get("session_id"),
            "publicerad": meta.get("publicerad"),
            "skapad": skapad,
            "versioner": versioner,
            "senaste_version": versioner[-1],
            "har_meta": bool(meta),
        })
    ut.sort(key=lambda x: x.get("skapad") or "", reverse=True)
    return {"publicerade": ut}


@app.delete("/api/published/{config_id}")
async def delete_published(config_id: str, _=Depends(require_auth)):
    """Tar bort ett publicerat regelverk ur maskera-applikationens katalog.

    Sessionen i optimizern rörs INTE — bara den publicerade kopian. Regelverket
    kan alltså publiceras igen från sessionen om det behövs.
    """
    mal = _publicerad_sokvag(config_id)
    if not os.path.isdir(mal):
        raise HTTPException(404, "Regelverket finns inte")
    import shutil
    shutil.rmtree(mal)
    logger.info("Avpublicerade regelverk: %s", config_id)
    return {"borttaget": config_id}


@app.get("/api/session/{session_id}/state")
async def session_state(session_id: str, _=Depends(require_auth)):
    """Allt som behövs för att återuppta en session i gränssnittet.

    Innehållet har hela tiden legat kvar på disk, men det fanns ingen väg att
    hämta tillbaka det — gränssnittet nollställde vyn och man fick ladda upp
    dokumentet på nytt.
    """
    if not session_store.session_exists(session_id):
        raise HTTPException(404, "Session not found")

    text = session_store.load_text(session_id) or ""
    results = session_store.load_analysis_results(session_id) or []
    sess = session_store.get_session(session_id) or {}

    # feedback.json är en HISTORIK (lista av omgångar) — den senaste omgången är
    # den som gäller för vyn.
    historik = session_store.get_feedback_history(session_id) or []
    senaste = historik[-1] if historik else {}

    return {
        "session_id": session_id,
        "name": sess.get("name", ""),
        "text": text,
        "results": results,
        "false_positives": senaste.get("false_positives", []),
        "false_negatives": senaste.get("false_negatives", []),
        "current_config_version": sess.get("current_config_version"),
        "har_analys": bool(results),
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

            elif action in ("add_exclusion", "remove_exclusion"):
                ord_ = details.get("text") or target
                et = details.get("entity_type")
                if not hasattr(config, "exclusions") or config.exclusions is None:
                    config.exclusions = []
                finns = [u for u in config.exclusions
                         if (u.get("text") or "").lower() == (ord_ or "").lower()
                         and u.get("entity_type") == et]
                if action == "add_exclusion":
                    if ord_ and not finns:
                        config.exclusions.append({"text": ord_, "entity_type": et})
                        logger.info(f"Added exclusion: {ord_!r} ({et or 'alla typer'})")
                else:
                    for u in finns:
                        config.exclusions.remove(u)
                    logger.info(f"Removed exclusion: {ord_!r}")

            elif action == "adjust_global_threshold":
                new_threshold = details.get("new_threshold", 0.5)
                config.score_threshold = new_threshold
                logger.info(f"Adjusted global threshold: {new_threshold}")

            else:
                logger.warning(f"Unknown action: {action}")

        except Exception as e:
            logger.error(f"Error applying change {action} on {target}: {e}")
