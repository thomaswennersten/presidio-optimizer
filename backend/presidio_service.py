"""
Presidio-analystjänst med dynamisk konfiguration.

Anpassad från presidio-anonymizer: borttaget remote-läge och anonymisering.
Tillagd: analyze_with_config() och rebuild_engine() för dynamisk konfiguration.
"""

import logging
from typing import List, Dict, Any, Optional
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import SpacyNlpEngine, NerModelConfiguration
from swedish_recognizers import get_swedish_recognizers
from custom_recognizer_factory import create_recognizers_from_config
from config_manager import PresidioConfig, EntityConfig

logger = logging.getLogger(__name__)


class PresidioService:
    def __init__(self):
        self.analyzer = None
        self._init_engine()

    def _init_engine(self):
        """Initialize the Presidio analyzer engine with bilingual NLP."""
        try:
            sv_ner_config = NerModelConfiguration(
                model_to_presidio_entity_mapping={
                    "PRS": "PERSON",
                    "PER": "PERSON",
                    "PERSON": "PERSON",
                    "LOC": "LOCATION",
                    "LOCATION": "LOCATION",
                    "GPE": "LOCATION",
                    "ORG": "ORGANIZATION",
                    "TME": "DATE_TIME",
                    "DATE": "DATE_TIME",
                    "TIME": "DATE_TIME",
                    "NORP": "NRP",
                },
                labels_to_ignore={
                    "EVN", "MSR", "OBJ", "WRK", "O",
                    "PRODUCT", "ORDINAL", "EVENT", "PERCENT",
                    "QUANTITY", "LAW", "CARDINAL", "MONEY",
                    "WORK_OF_ART", "LANGUAGE",
                },
            )
            nlp_engine = SpacyNlpEngine(
                models=[
                    {"lang_code": "en", "model_name": "en_core_web_sm"},
                    {"lang_code": "sv", "model_name": "sv_core_news_sm"},
                ],
                ner_model_configuration=sv_ner_config,
            )
            self.analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine,
                supported_languages=["en", "sv"],
            )

            for recognizer in get_swedish_recognizers():
                self.analyzer.registry.add_recognizer(recognizer)
                logger.info(f"Registered: {recognizer.name}")

            logger.info("Presidio analyzer engine initialized (sv + en)")

        except Exception as e:
            logger.error(f"Error initializing bilingual engine: {e}")
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            fallback_config = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            }
            provider = NlpEngineProvider(nlp_configuration=fallback_config)
            nlp_engine = provider.create_engine()
            self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
            logger.warning("Fell back to English-only engine")

    def rebuild_engine(self, config: PresidioConfig):
        """Rebuild the analyzer engine with custom recognizers from config."""
        self._init_engine()

        # Add dynamic recognizers from config
        if config.custom_recognizers:
            dynamic_recs = create_recognizers_from_config(config.custom_recognizers)
            for rec in dynamic_recs:
                self.analyzer.registry.add_recognizer(rec)
                logger.info(f"Added dynamic recognizer: {rec.name}")

    def analyze_text(self, text: str, language: str = "sv", config: Optional[PresidioConfig] = None) -> List[Dict[str, Any]]:
        """Analyze text for PII entities, optionally using a specific config."""
        score_threshold = 0.5
        entity_settings = {}

        if config:
            score_threshold = config.score_threshold
            entity_settings = config.entity_settings

        return self._analyze_local(text, language, score_threshold, entity_settings)

    def analyze_with_config(self, text: str, config: PresidioConfig) -> List[Dict[str, Any]]:
        """Analyze text using a specific configuration. Rebuilds engine if needed."""
        self.rebuild_engine(config)
        return self.analyze_text(text, config.languages[0] if config.languages else "sv", config)

    def _analyze_local(self, text: str, language: str, score_threshold: float = 0.5,
                       entity_settings: Dict[str, EntityConfig] = None) -> List[Dict[str, Any]]:
        """Analyze text using local Presidio engine with dual-language NER."""
        base_entities = [
            "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
            "CREDIT_CARD", "IBAN_CODE", "NRP",
            "LOCATION", "DATE_TIME", "IP_ADDRESS",
            "MEDICAL_LICENSE", "URL",
        ]

        sv_entities = base_entities + [
            "SWEDISH_PERSONNUMMER",
            "SWEDISH_SAMORDNINGSNUMMER",
            "SWEDISH_ORGANISATIONSNUMMER",
            "SWEDISH_PHONE_NUMBER",
        ]

        # Filter entities based on config
        if entity_settings:
            sv_entities = [e for e in sv_entities
                          if e not in entity_settings or entity_settings[e].enabled]
            base_entities = [e for e in base_entities
                            if e not in entity_settings or entity_settings[e].enabled]

        all_results = []

        if language == "sv":
            try:
                sv_results = self.analyzer.analyze(
                    text=text, language="sv",
                    entities=sv_entities,
                    score_threshold=score_threshold,
                )
                all_results.extend(sv_results)
            except Exception as e:
                logger.error(f"Swedish analysis error: {e}")

            try:
                en_results = self.analyzer.analyze(
                    text=text, language="en",
                    entities=base_entities,
                    score_threshold=score_threshold,
                )
                all_results.extend(en_results)
            except Exception as e:
                logger.error(f"English analysis error: {e}")

            results = self._merge_results(all_results)
        else:
            try:
                results = self.analyzer.analyze(
                    text=text, language=language,
                    entities=base_entities,
                    score_threshold=score_threshold,
                )
            except Exception as e:
                logger.error(f"Analysis error for '{language}': {e}")
                results = []

        # Apply per-entity threshold filtering
        if entity_settings:
            filtered = []
            for r in results:
                et = r.entity_type
                if et in entity_settings:
                    ec = entity_settings[et]
                    if isinstance(ec, dict):
                        ec = EntityConfig(**ec)
                    if ec.enabled and r.score >= ec.threshold:
                        filtered.append(r)
                else:
                    if r.score >= score_threshold:
                        filtered.append(r)
            results = filtered

        return [
            {
                "entity_type": r.entity_type,
                "start": r.start,
                "end": r.end,
                "score": round(r.score, 4),
                "recognizer_name": getattr(r, 'recognition_metadata', {}).get('recognizer_name', '') if hasattr(r, 'recognition_metadata') else '',
            }
            for r in results
        ]

    @staticmethod
    def _merge_results(results: list) -> list:
        """Merge results from dual-language analysis."""
        if not results:
            return []

        sorted_results = sorted(
            results, key=lambda r: (-(r.end - r.start), -r.score)
        )
        merged = []

        for result in sorted_results:
            r_start, r_end = result.start, result.end
            subsumed = False

            for kept in merged:
                k_start, k_end = kept.start, kept.end
                overlap_start = max(r_start, k_start)
                overlap_end = min(r_end, k_end)

                if overlap_start >= overlap_end:
                    continue

                overlap_len = overlap_end - overlap_start
                r_len = r_end - r_start

                if result.entity_type == kept.entity_type:
                    if overlap_len >= r_len * 0.5:
                        subsumed = True
                        break
                else:
                    if r_start >= k_start and r_end <= k_end:
                        subsumed = True
                        break

            if not subsumed:
                merged.append(result)

        return merged
