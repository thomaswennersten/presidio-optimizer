# Presidio Anonymizer
# Copyright (C) 2026 Sambruk
#
# Detta program är fri programvara; du får sprida och ändra det enligt
# villkoren i GNU General Public License version 2, som den publicerats av
# Free Software Foundation.
#
# Programmet distribueras i hopp om att det ska vara användbart, men UTAN
# NÅGON GARANTI. Se GNU General Public License för fler detaljer.
# Se filen LICENSE.

import os
import httpx
import logging
import base64
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider, SpacyNlpEngine, NerModelConfiguration
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from swedish_recognizers import get_swedish_recognizers

load_dotenv()

logger = logging.getLogger(__name__)

class PresidioService:
    def __init__(self):
        # Analyzer configuration
        self.analyzer_endpoint = os.getenv("PRESIDIO_ANALYZER_ENDPOINT")
        self.analyzer_username = os.getenv("PRESIDIO_ANALYZER_USERNAME")
        self.analyzer_password = os.getenv("PRESIDIO_ANALYZER_PASSWORD")
        self.analyzer_api_key = os.getenv("PRESIDIO_ANALYZER_API_KEY")
        
        # Anonymizer configuration
        self.anonymizer_endpoint = os.getenv("PRESIDIO_ANONYMIZER_ENDPOINT")
        self.anonymizer_username = os.getenv("PRESIDIO_ANONYMIZER_USERNAME")
        self.anonymizer_password = os.getenv("PRESIDIO_ANONYMIZER_PASSWORD")
        self.anonymizer_api_key = os.getenv("PRESIDIO_ANONYMIZER_API_KEY")
        
        if self.analyzer_endpoint and self.anonymizer_endpoint:
            self.use_remote = True
            
            # Setup analyzer headers
            self.analyzer_headers = {}
            if self.analyzer_username and self.analyzer_password:
                # Basic Auth for Analyzer
                credentials = f"{self.analyzer_username}:{self.analyzer_password}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                self.analyzer_headers["Authorization"] = f"Basic {encoded_credentials}"
            elif self.analyzer_api_key:
                # API Key auth for Analyzer
                self.analyzer_headers["Authorization"] = f"Bearer {self.analyzer_api_key}"
            
            # Setup anonymizer headers
            self.anonymizer_headers = {}
            if self.anonymizer_username and self.anonymizer_password:
                # Basic Auth for Anonymizer
                credentials = f"{self.anonymizer_username}:{self.anonymizer_password}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                self.anonymizer_headers["Authorization"] = f"Basic {encoded_credentials}"
            elif self.anonymizer_api_key:
                # API Key auth for Anonymizer
                self.anonymizer_headers["Authorization"] = f"Bearer {self.anonymizer_api_key}"
                
            logger.info(f"Using remote Presidio engines - Analyzer: {self.analyzer_endpoint}, Anonymizer: {self.anonymizer_endpoint}")
        else:
            self.use_remote = False
            try:
                # Custom NER label mapping for Swedish spaCy model
                # sv_core_news_sm uses: PRS, LOC, ORG, TME, EVN, MSR, OBJ, WRK
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
                    labels_to_ignore={"EVN", "MSR", "OBJ", "WRK", "O",
                                      "PRODUCT", "ORDINAL", "EVENT", "PERCENT",
                                      "QUANTITY", "LAW", "CARDINAL", "MONEY",
                                      "WORK_OF_ART", "LANGUAGE"},
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
                self.anonymizer = AnonymizerEngine()

                # Register Swedish recognizers
                for recognizer in get_swedish_recognizers():
                    self.analyzer.registry.add_recognizer(recognizer)
                    logger.info(f"Registered Swedish recognizer: {recognizer.name}")

            except Exception as e:
                logger.error(f"Error initializing bilingual Presidio engines: {str(e)}")
                # Fallback to English-only
                try:
                    fallback_config = {
                        "nlp_engine_name": "spacy",
                        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
                    }
                    provider = NlpEngineProvider(nlp_configuration=fallback_config)
                    nlp_engine = provider.create_engine()
                    self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
                    self.anonymizer = AnonymizerEngine()
                    logger.warning("Fell back to English-only Presidio engines")
                except Exception as e2:
                    logger.error(f"Error initializing fallback engines: {str(e2)}")
                    raise
            logger.info("Using local Presidio engines")
    
    async def analyze_text(self, text: str, language: str = "sv") -> List[Dict[str, Any]]:
        """Analyze text for PII entities"""
        if self.use_remote:
            return await self._analyze_remote(text, language)
        else:
            return self._analyze_local(text, language)
    
    async def anonymize_text(self, text: str, analyzer_results: List[Dict[str, Any]]) -> str:
        """Anonymize text based on analyzer results"""
        if self.use_remote:
            return await self._anonymize_remote(text, analyzer_results)
        else:
            return self._anonymize_local(text, analyzer_results)
    
    async def _analyze_remote(self, text: str, language: str) -> List[Dict[str, Any]]:
        """Analyze text using remote Presidio service"""
        async with httpx.AsyncClient(verify=False) as client:  # Disable SSL verification for self-signed certs
            payload = {
                "text": text,
                "language": language
            }
            
            try:
                response = await client.post(
                    f"{self.analyzer_endpoint}/analyze",
                    json=payload,
                    headers=self.analyzer_headers,
                    timeout=30.0
                )
                response.raise_for_status()
                results = response.json()
                
                # Convert remote response to expected format
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        "entity_type": result.get("entity_type"),
                        "start": result.get("start"),
                        "end": result.get("end"),
                        "score": result.get("score", 0.0)
                    })
                
                return formatted_results
            except httpx.HTTPError as e:
                logger.error(f"Error calling Presidio Analyzer: {str(e)}")
                logger.error(f"Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
                return self._analyze_local(text, language)
    
    def _analyze_local(self, text: str, language: str) -> List[Dict[str, Any]]:
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

        all_results = []

        if language == "sv":
            # 1) Swedish analysis — NER + custom recognizers
            try:
                sv_results = self.analyzer.analyze(
                    text=text,
                    language="sv",
                    entities=sv_entities,
                    score_threshold=0.5,
                )
                all_results.extend(sv_results)
            except Exception as e:
                logger.error(f"Error in Swedish analysis: {str(e)}")

            # 2) English analysis — catches international names better
            try:
                en_results = self.analyzer.analyze(
                    text=text,
                    language="en",
                    entities=base_entities,
                    score_threshold=0.5,
                )
                all_results.extend(en_results)
            except Exception as e:
                logger.error(f"Error in English analysis: {str(e)}")

            # Merge: keep highest score for overlapping spans
            results = self._merge_results(all_results)
        else:
            try:
                results = self.analyzer.analyze(
                    text=text,
                    language=language,
                    entities=base_entities,
                    score_threshold=0.5,
                )
            except Exception as e:
                logger.error(f"Error in local analysis with language '{language}': {str(e)}")
                results = self.analyzer.analyze(
                    text=text,
                    language="en",
                    entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IP_ADDRESS", "URL"],
                    score_threshold=0.5,
                )

        return [
            {
                "entity_type": result.entity_type,
                "start": result.start,
                "end": result.end,
                "score": result.score,
            }
            for result in results
        ]

    @staticmethod
    def _merge_results(results: list) -> list:
        """Merge results from dual-language analysis.

        Strategy: for overlapping entities of the same type, prefer the
        LONGER span (covers more PII). For different types, keep both.
        Subsume short fragments that are fully contained in a longer entity.
        """
        if not results:
            return []

        # Sort by span length descending, then score descending
        # Process longest spans first so they "claim" territory
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
                    continue  # No overlap

                overlap_len = overlap_end - overlap_start
                r_len = r_end - r_start
                k_len = k_end - k_start

                # Same entity type: shorter fragment is subsumed by longer
                if result.entity_type == kept.entity_type:
                    if overlap_len >= r_len * 0.5:
                        subsumed = True
                        break
                else:
                    # Different types: shorter is subsumed if fully contained
                    if r_start >= k_start and r_end <= k_end:
                        subsumed = True
                        break

            if not subsumed:
                merged.append(result)

        return merged
    
    async def _anonymize_remote(self, text: str, analyzer_results: List[Dict[str, Any]]) -> str:
        """Anonymize text using remote Presidio service"""
        async with httpx.AsyncClient(verify=False) as client:  # Disable SSL verification for self-signed certs
            # Format analyzer results for remote API
            formatted_results = []
            for result in analyzer_results:
                formatted_results.append({
                    "start": result["start"],
                    "end": result["end"],
                    "score": result["score"],
                    "entity_type": result["entity_type"]
                })
            
            # Format operators for remote API
            anonymizers = {
                "DEFAULT": {"type": "replace", "new_value": "[REDACTED]"},
                "PERSON": {"type": "replace", "new_value": "[PERSON]"},
                "EMAIL_ADDRESS": {"type": "replace", "new_value": "[EMAIL]"},
                "PHONE_NUMBER": {"type": "mask", "masking_char": "*", "chars_to_mask": 4, "from_end": True},
                "CREDIT_CARD": {"type": "mask", "masking_char": "*", "chars_to_mask": 12, "from_end": False},
                "IBAN_CODE": {"type": "mask", "masking_char": "*", "chars_to_mask": 14, "from_end": False},
                "LOCATION": {"type": "replace", "new_value": "[PLATS]"},
                "DATE_TIME": {"type": "replace", "new_value": "[DATUM]"},
                "IP_ADDRESS": {"type": "replace", "new_value": "[IP]"},
                "URL": {"type": "replace", "new_value": "[URL]"},
                "SWEDISH_PERSONNUMMER": {"type": "replace", "new_value": "[PERSONNUMMER]"},
                "SWEDISH_SAMORDNINGSNUMMER": {"type": "replace", "new_value": "[SAMORDNINGSNUMMER]"},
                "SWEDISH_ORGANISATIONSNUMMER": {"type": "replace", "new_value": "[ORGANISATIONSNUMMER]"},
                "SWEDISH_PHONE_NUMBER": {"type": "replace", "new_value": "[TELEFON]"},
            }
            
            payload = {
                "text": text,
                "analyzer_results": formatted_results,
                "anonymizers": anonymizers
            }
            
            try:
                response = await client.post(
                    f"{self.anonymizer_endpoint}/anonymize",
                    json=payload,
                    headers=self.anonymizer_headers,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return result.get("text", text)
            except httpx.HTTPError as e:
                logger.error(f"Error calling Presidio Anonymizer: {str(e)}")
                logger.error(f"Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
                return self._anonymize_local(text, analyzer_results)
    
    def _anonymize_local(self, text: str, analyzer_results: List[Dict[str, Any]]) -> str:
        """Anonymize text using local Presidio engine"""
        recognizer_results = [
            RecognizerResult(
                entity_type=result["entity_type"],
                start=result["start"],
                end=result["end"],
                score=result["score"]
            )
            for result in analyzer_results
        ]
        
        operators = self._get_operators_config()
        
        result = self.anonymizer.anonymize(
            text=text,
            analyzer_results=recognizer_results,
            operators=operators
        )
        
        return result.text
    
    def _get_operators_config(self) -> Dict[str, OperatorConfig]:
        """Get anonymization operators configuration"""
        return {
            "PERSON": OperatorConfig("replace", {"new_value": "[PERSON]"}),
            "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL]"}),
            "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
            "CREDIT_CARD": OperatorConfig("mask", {"type": "mask", "masking_char": "*", "chars_to_mask": 12, "from_end": False}),
            "IBAN_CODE": OperatorConfig("mask", {"type": "mask", "masking_char": "*", "chars_to_mask": 14, "from_end": False}),
            "NRP": OperatorConfig("replace", {"new_value": "[ID]"}),
            "LOCATION": OperatorConfig("replace", {"new_value": "[PLATS]"}),
            "DATE_TIME": OperatorConfig("replace", {"new_value": "[DATUM]"}),
            "IP_ADDRESS": OperatorConfig("replace", {"new_value": "[IP]"}),
            "MEDICAL_LICENSE": OperatorConfig("replace", {"new_value": "[LICENSE]"}),
            "URL": OperatorConfig("replace", {"new_value": "[URL]"}),
            "SWEDISH_PERSONNUMMER": OperatorConfig("replace", {"new_value": "[PERSONNUMMER]"}),
            "SWEDISH_SAMORDNINGSNUMMER": OperatorConfig("replace", {"new_value": "[SAMORDNINGSNUMMER]"}),
            "SWEDISH_ORGANISATIONSNUMMER": OperatorConfig("replace", {"new_value": "[ORGANISATIONSNUMMER]"}),
            "SWEDISH_PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[TELEFON]"}),
            "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
        }