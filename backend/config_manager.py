"""
Versionshanterad konfigurationshantering för Presidio Optimizer.

Hanterar:
- Datamodell (PresidioConfig) med entity_settings, custom_recognizers, tröskelvärden
- Serialisering till/från JSON
- Versionshantering (varje ändring sparas som ny version)
- Export som JSON/YAML
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from copy import deepcopy

logger = logging.getLogger(__name__)

CONFIG_DIR = os.environ.get("CONFIG_DIR", "/app/db/sessions")


@dataclass
class EntityConfig:
    enabled: bool = True
    threshold: float = 0.5
    label: str = ""


@dataclass
class RecognizerPattern:
    name: str = ""
    regex: str = ""
    score: float = 0.6


@dataclass
class RecognizerDefinition:
    name: str = ""
    entity_type: str = ""
    patterns: List[RecognizerPattern] = field(default_factory=list)
    deny_list: List[str] = field(default_factory=list)
    context_words: List[str] = field(default_factory=list)
    supported_language: str = "sv"


@dataclass
class PresidioConfig:
    version: int = 1
    created_at: str = ""
    description: str = "Initial configuration"
    entity_settings: Dict[str, EntityConfig] = field(default_factory=dict)
    custom_recognizers: List[RecognizerDefinition] = field(default_factory=list)
    score_threshold: float = 0.5
    languages: List[str] = field(default_factory=lambda: ["sv", "en"])

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "PresidioConfig":
        config = cls()
        config.version = data.get("version", 1)
        config.created_at = data.get("created_at", "")
        config.description = data.get("description", "")
        config.score_threshold = data.get("score_threshold", 0.5)
        config.languages = data.get("languages", ["sv", "en"])

        for name, ec in data.get("entity_settings", {}).items():
            if isinstance(ec, dict):
                config.entity_settings[name] = EntityConfig(**ec)
            else:
                config.entity_settings[name] = ec

        for rd in data.get("custom_recognizers", []):
            if isinstance(rd, dict):
                patterns = []
                for p in rd.get("patterns", []):
                    if isinstance(p, dict):
                        patterns.append(RecognizerPattern(**p))
                    else:
                        patterns.append(p)
                rd_obj = RecognizerDefinition(
                    name=rd.get("name", ""),
                    entity_type=rd.get("entity_type", ""),
                    patterns=patterns,
                    deny_list=rd.get("deny_list", []),
                    context_words=rd.get("context_words", []),
                    supported_language=rd.get("supported_language", "sv"),
                )
                config.custom_recognizers.append(rd_obj)
            else:
                config.custom_recognizers.append(rd)

        return config


def get_default_config() -> PresidioConfig:
    """Return default Presidio configuration with standard entity settings."""
    config = PresidioConfig(
        version=1,
        created_at=datetime.utcnow().isoformat(),
        description="Default configuration with standard Swedish + English PII detection",
        score_threshold=0.5,
        languages=["sv", "en"],
    )

    default_entities = {
        "PERSON": EntityConfig(enabled=True, threshold=0.5, label="Person"),
        "EMAIL_ADDRESS": EntityConfig(enabled=True, threshold=0.5, label="E-post"),
        "PHONE_NUMBER": EntityConfig(enabled=True, threshold=0.5, label="Telefonnummer"),
        "CREDIT_CARD": EntityConfig(enabled=True, threshold=0.5, label="Kreditkort"),
        "IBAN_CODE": EntityConfig(enabled=True, threshold=0.5, label="IBAN"),
        "NRP": EntityConfig(enabled=True, threshold=0.5, label="Nationalitet/Religion"),
        "LOCATION": EntityConfig(enabled=True, threshold=0.5, label="Plats"),
        "DATE_TIME": EntityConfig(enabled=True, threshold=0.5, label="Datum/Tid"),
        "IP_ADDRESS": EntityConfig(enabled=True, threshold=0.5, label="IP-adress"),
        "URL": EntityConfig(enabled=True, threshold=0.5, label="URL"),
        "SWEDISH_PERSONNUMMER": EntityConfig(enabled=True, threshold=0.4, label="Personnummer"),
        "SWEDISH_SAMORDNINGSNUMMER": EntityConfig(enabled=True, threshold=0.4, label="Samordningsnummer"),
        "SWEDISH_ORGANISATIONSNUMMER": EntityConfig(enabled=True, threshold=0.4, label="Organisationsnummer"),
        "SWEDISH_PHONE_NUMBER": EntityConfig(enabled=True, threshold=0.4, label="Svenskt telefonnummer"),
    }
    config.entity_settings = default_entities
    return config


class ConfigManager:
    """Manages versioned Presidio configurations per session."""

    def __init__(self, base_dir: str = CONFIG_DIR):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _session_dir(self, session_id: str) -> str:
        d = os.path.join(self.base_dir, session_id, "configs")
        os.makedirs(d, exist_ok=True)
        return d

    def save_config(self, session_id: str, config: PresidioConfig) -> str:
        """Save config as new version. Returns path to saved file."""
        d = self._session_dir(session_id)
        config.created_at = datetime.utcnow().isoformat()
        path = os.path.join(d, f"{config.version}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Saved config v{config.version} for session {session_id}")
        return path

    def load_config(self, session_id: str, version: Optional[int] = None) -> Optional[PresidioConfig]:
        """Load config by version. If version is None, load latest."""
        d = self._session_dir(session_id)
        if version is not None:
            path = os.path.join(d, f"{version}.json")
            if not os.path.exists(path):
                return None
        else:
            versions = self.list_versions(session_id)
            if not versions:
                return None
            version = max(versions)
            path = os.path.join(d, f"{version}.json")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PresidioConfig.from_dict(data)

    def list_versions(self, session_id: str) -> List[int]:
        """List all saved config versions for a session."""
        d = self._session_dir(session_id)
        versions = []
        for f in os.listdir(d):
            if f.endswith(".json"):
                try:
                    versions.append(int(f.replace(".json", "")))
                except ValueError:
                    pass
        return sorted(versions)

    def get_config_history(self, session_id: str) -> List[dict]:
        """Get summary of all config versions."""
        versions = self.list_versions(session_id)
        history = []
        for v in versions:
            config = self.load_config(session_id, v)
            if config:
                history.append({
                    "version": config.version,
                    "created_at": config.created_at,
                    "description": config.description,
                    "score_threshold": config.score_threshold,
                    "num_custom_recognizers": len(config.custom_recognizers),
                    "entity_count": len(config.entity_settings),
                })
        return history

    def create_next_version(self, session_id: str, base_config: PresidioConfig, description: str = "") -> PresidioConfig:
        """Create a new version based on existing config."""
        new_config = deepcopy(base_config)
        versions = self.list_versions(session_id)
        new_config.version = max(versions) + 1 if versions else 1
        new_config.description = description
        return new_config

    def export_config(self, session_id: str, version: Optional[int] = None, fmt: str = "json") -> Optional[str]:
        """Export config as JSON or YAML string."""
        config = self.load_config(session_id, version)
        if not config:
            return None

        data = config.to_dict()
        if fmt == "yaml":
            try:
                import yaml
                return yaml.dump(data, default_flow_style=False, allow_unicode=True)
            except ImportError:
                return json.dumps(data, ensure_ascii=False, indent=2)
        return json.dumps(data, ensure_ascii=False, indent=2)
