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
Skapar Presidio-recognizers dynamiskt från konfigurationsdicts.

Används av presidio_service för att bygga om AnalyzerEngine
baserat på LLM-optimerade konfigurationer.
"""

import logging
from typing import List
from presidio_analyzer import Pattern, PatternRecognizer, EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts
from config_manager import RecognizerDefinition

logger = logging.getLogger(__name__)


class DynamicPatternRecognizer(PatternRecognizer):
    """A pattern recognizer created dynamically from config."""
    pass


class DynamicDenyListRecognizer(PatternRecognizer):
    """A deny-list recognizer created dynamically from config."""
    pass


def create_recognizer_from_definition(definition: RecognizerDefinition):
    """Create a Presidio recognizer from a RecognizerDefinition.

    Supports:
    - Pattern-based recognizers (regex patterns with scores)
    - Deny-list recognizers (exact string matches)
    - Combined pattern + deny-list recognizers
    """
    if not definition.name or not definition.entity_type:
        logger.warning(f"Skipping recognizer with missing name or entity_type: {definition}")
        return None

    patterns = []
    for p in definition.patterns:
        try:
            patterns.append(Pattern(
                name=p.name or f"{definition.name}_pattern",
                regex=p.regex,
                score=p.score,
            ))
        except Exception as e:
            logger.error(f"Invalid pattern in {definition.name}: {e}")

    deny_list = definition.deny_list or []
    context = definition.context_words or []
    lang = definition.supported_language or "sv"

    if patterns:
        try:
            recognizer = DynamicPatternRecognizer(
                supported_entity=definition.entity_type,
                supported_language=lang,
                patterns=patterns,
                context=context if context else None,
                name=definition.name,
            )
            if deny_list:
                recognizer.deny_list = deny_list
            logger.info(f"Created pattern recognizer: {definition.name} for {definition.entity_type}")
            return recognizer
        except Exception as e:
            logger.error(f"Error creating pattern recognizer {definition.name}: {e}")
            return None

    elif deny_list:
        try:
            recognizer = DynamicDenyListRecognizer(
                supported_entity=definition.entity_type,
                supported_language=lang,
                deny_list=deny_list,
                context=context if context else None,
                name=definition.name,
            )
            logger.info(f"Created deny-list recognizer: {definition.name} for {definition.entity_type}")
            return recognizer
        except Exception as e:
            logger.error(f"Error creating deny-list recognizer {definition.name}: {e}")
            return None

    else:
        logger.warning(f"Recognizer {definition.name} has no patterns or deny_list - skipping")
        return None


def create_recognizers_from_config(definitions: List[RecognizerDefinition]) -> list:
    """Create all recognizers from a list of definitions."""
    recognizers = []
    for defn in definitions:
        rec = create_recognizer_from_definition(defn)
        if rec:
            recognizers.append(rec)
    return recognizers
