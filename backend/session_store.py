"""
Persistent sessionslagring för Presidio Optimizer.

Ersätter in-memory sessions-dict med filbaserad lagring.
Varje session lagras i db/sessions/{session_id}/ med:
  - session.json  (metadata)
  - text.txt      (uppladdad dokumenttext)
  - feedback.json (alla feedback-omgångar)
  - optimizations.json (LLM-resultat)
  - report.md     (auto-genererad rapport)
  - configs/      (versionshanterade konfigurationer)
"""

import json
import os
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

SESSIONS_DIR = os.environ.get("CONFIG_DIR", "/app/db/sessions")


class SessionStore:
    """Filbaserad sessionslagring."""

    def __init__(self, base_dir: str = SESSIONS_DIR):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _session_dir(self, session_id: str) -> str:
        d = os.path.join(self.base_dir, session_id)
        os.makedirs(d, exist_ok=True)
        return d

    def _read_json(self, path: str, default=None):
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: str, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --- Session CRUD ---

    def create_session(self, name: str) -> Dict[str, Any]:
        """Skapa ny namngiven session. Returnerar metadata."""
        session_id = str(uuid.uuid4())[:12]
        d = self._session_dir(session_id)
        os.makedirs(os.path.join(d, "configs"), exist_ok=True)

        meta = {
            "id": session_id,
            "name": name,
            "created_at": datetime.utcnow().isoformat(),
            "filename": "",
            "text_length": 0,
            "iterations": 0,
            "current_config_version": 1,
        }
        self._write_json(os.path.join(d, "session.json"), meta)
        # Initiera tomma listor
        self._write_json(os.path.join(d, "feedback.json"), [])
        self._write_json(os.path.join(d, "optimizations.json"), [])
        logger.info(f"Created session {session_id}: {name}")
        return meta

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Hämta sessionsmetadata."""
        path = os.path.join(self.base_dir, session_id, "session.json")
        return self._read_json(path)

    def session_exists(self, session_id: str) -> bool:
        path = os.path.join(self.base_dir, session_id, "session.json")
        return os.path.exists(path)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Lista alla sessioner, sorterade efter skapandedatum (nyast först)."""
        sessions = []
        if not os.path.exists(self.base_dir):
            return sessions
        for entry in os.listdir(self.base_dir):
            meta_path = os.path.join(self.base_dir, entry, "session.json")
            if os.path.isfile(meta_path):
                meta = self._read_json(meta_path)
                if meta:
                    sessions.append(meta)
        sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return sessions

    def update_session(self, session_id: str, updates: Dict[str, Any]):
        """Uppdatera sessionens metadata."""
        d = self._session_dir(session_id)
        path = os.path.join(d, "session.json")
        meta = self._read_json(path, {})
        meta.update(updates)
        self._write_json(path, meta)

    # --- Text ---

    def save_text(self, session_id: str, text: str, filename: str):
        """Spara uppladdad dokumenttext."""
        d = self._session_dir(session_id)
        with open(os.path.join(d, "text.txt"), "w", encoding="utf-8") as f:
            f.write(text)
        self.update_session(session_id, {
            "filename": filename,
            "text_length": len(text),
        })

    def load_text(self, session_id: str) -> str:
        """Ladda dokumenttext."""
        path = os.path.join(self.base_dir, session_id, "text.txt")
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    # --- Feedback ---

    def append_feedback(self, session_id: str, entry: Dict[str, Any]):
        """Lägg till en feedback-omgång."""
        d = self._session_dir(session_id)
        path = os.path.join(d, "feedback.json")
        history = self._read_json(path, [])
        history.append(entry)
        self._write_json(path, history)

    def get_feedback_history(self, session_id: str) -> List[Dict[str, Any]]:
        path = os.path.join(self.base_dir, session_id, "feedback.json")
        return self._read_json(path, [])

    # --- Optimizations ---

    def append_optimization(self, session_id: str, entry: Dict[str, Any]):
        """Lägg till LLM-optimeringsresultat."""
        d = self._session_dir(session_id)
        path = os.path.join(d, "optimizations.json")
        history = self._read_json(path, [])
        history.append(entry)
        self._write_json(path, history)
        # Uppdatera iterationsräknare
        meta = self.get_session(session_id) or {}
        self.update_session(session_id, {
            "iterations": meta.get("iterations", 0) + 1,
        })

    def get_optimizations(self, session_id: str) -> List[Dict[str, Any]]:
        path = os.path.join(self.base_dir, session_id, "optimizations.json")
        return self._read_json(path, [])

    # --- Analysis results (kept for compatibility) ---

    def save_analysis_results(self, session_id: str, results: List[Dict[str, Any]]):
        d = self._session_dir(session_id)
        self._write_json(os.path.join(d, "analysis_results.json"), results)

    def load_analysis_results(self, session_id: str) -> List[Dict[str, Any]]:
        path = os.path.join(self.base_dir, session_id, "analysis_results.json")
        return self._read_json(path, [])

    # --- Report ---

    def generate_report(self, session_id: str) -> str:
        """Generera Markdown-rapport från all sessionsdata."""
        meta = self.get_session(session_id)
        if not meta:
            return ""

        text = self.load_text(session_id)
        feedback = self.get_feedback_history(session_id)
        optimizations = self.get_optimizations(session_id)

        lines = []
        lines.append(f"# Rapport: {meta.get('name', session_id)}")
        lines.append("")
        lines.append(f"**Session-ID:** {meta.get('id', '')}")
        lines.append(f"**Skapad:** {meta.get('created_at', '')}")
        lines.append(f"**Dokument:** {meta.get('filename', '-')}")
        lines.append(f"**Textlängd:** {meta.get('text_length', 0)} tecken")
        lines.append(f"**Antal iterationer:** {meta.get('iterations', 0)}")
        lines.append("")

        # Textutdrag
        if text:
            preview = text[:500]
            lines.append("## Textutdrag")
            lines.append("")
            lines.append(f"```\n{preview}\n```")
            lines.append("")

        # Feedback-historik
        if feedback:
            lines.append("## Feedback-historik")
            lines.append("")
            for i, fb in enumerate(feedback, 1):
                fp_count = len(fb.get("false_positives", []))
                fn_count = len(fb.get("false_negatives", []))
                lines.append(f"### Omgång {i} ({fb.get('timestamp', '')})")
                lines.append(f"- False positives: {fp_count}")
                lines.append(f"- False negatives: {fn_count}")
                lines.append("")

        # Optimeringsresultat
        if optimizations:
            lines.append("## Optimeringar")
            lines.append("")
            for i, opt in enumerate(optimizations, 1):
                lines.append(f"### Optimering {i} ({opt.get('timestamp', '')})")
                lines.append("")
                if opt.get("reasoning"):
                    lines.append(f"**Resonemang:** {opt['reasoning']}")
                    lines.append("")
                changes = opt.get("changes", [])
                if changes:
                    lines.append("**Ändringar:**")
                    for c in changes:
                        lines.append(f"- `{c.get('action', '')}` på `{c.get('target', '')}`")
                    lines.append("")
                if opt.get("expected_improvements"):
                    lines.append(f"**Förväntade förbättringar:** {opt['expected_improvements']}")
                    lines.append("")

        report = "\n".join(lines)

        # Spara till disk
        d = self._session_dir(session_id)
        with open(os.path.join(d, "report.md"), "w", encoding="utf-8") as f:
            f.write(report)

        return report

    # --- Nedladdningsbara filer ---

    def list_files(self, session_id: str) -> List[Dict[str, str]]:
        """Lista nedladdningsbara filer för en session."""
        d = os.path.join(self.base_dir, session_id)
        if not os.path.isdir(d):
            return []

        meta = self.get_session(session_id) or {}
        safe_name = self._safe_filename(meta.get("name", session_id))
        files = []

        # Feedback
        fb_path = os.path.join(d, "feedback.json")
        if os.path.exists(fb_path):
            fb = self._read_json(fb_path, [])
            if fb:
                files.append({
                    "filename": "feedback.json",
                    "download_name": f"{safe_name}_feedback.json",
                    "label": "Feedback-historik",
                })

        # Optimeringar
        opt_path = os.path.join(d, "optimizations.json")
        if os.path.exists(opt_path):
            opts = self._read_json(opt_path, [])
            if opts:
                files.append({
                    "filename": "optimizations.json",
                    "download_name": f"{safe_name}_optimeringar.json",
                    "label": "Optimeringsresultat",
                })

        # Rapport
        if os.path.exists(os.path.join(d, "report.md")):
            files.append({
                "filename": "report.md",
                "download_name": f"{safe_name}_rapport.md",
                "label": "Rapport",
            })

        # Konfigurationer (JSON + YAML)
        configs_dir = os.path.join(d, "configs")
        if os.path.isdir(configs_dir):
            for f in sorted(os.listdir(configs_dir)):
                if f.endswith(".json"):
                    version = f.replace(".json", "")
                    files.append({
                        "filename": f"configs/{f}",
                        "download_name": f"{safe_name}_config_v{version}.json",
                        "label": f"Konfiguration v{version} (JSON)",
                    })
                    files.append({
                        "filename": f"configs/{version}.yaml",
                        "download_name": f"{safe_name}_config_v{version}.yaml",
                        "label": f"Konfiguration v{version} (YAML)",
                        "virtual": True,
                    })

        return files

    def get_file_path(self, session_id: str, filename: str) -> Optional[str]:
        """Hämta absolut sökväg för en fil i sessionen."""
        d = os.path.join(self.base_dir, session_id)
        path = os.path.join(d, filename)
        # Säkerhet: förhindra path traversal
        real_d = os.path.realpath(d)
        real_path = os.path.realpath(path)
        if not real_path.startswith(real_d):
            return None
        if not os.path.exists(real_path):
            return None
        return real_path

    @staticmethod
    def _safe_filename(name: str) -> str:
        """Gör ett sessionsnamn filsystemssäkert."""
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in name)
        return safe.strip().replace(" ", "_")[:60] or "session"
