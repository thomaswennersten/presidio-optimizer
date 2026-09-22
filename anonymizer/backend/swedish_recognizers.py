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

"""
Svenska PII-recognizers för Presidio Analyzer.

Innehåller recognizers för:
- Personnummer (YYYYMMDD-XXXX)
- Samordningsnummer (dag+60)
- Organisationsnummer (3:e siffran >= 2)
- Svenska telefonnummer (+46, 07X, 0XX)
"""

import re
import logging
from typing import List, Optional
from presidio_analyzer import Pattern, PatternRecognizer, EntityRecognizer, RecognizerResult, AnalysisExplanation
from presidio_analyzer.nlp_engine import NlpArtifacts

logger = logging.getLogger(__name__)


def _make_explanation(recognizer_name: str, pattern_name: str, original_score: float) -> AnalysisExplanation:
    """Skapa AnalysisExplanation som krävs för context enrichment."""
    return AnalysisExplanation(
        recognizer=recognizer_name,
        pattern_name=pattern_name,
        pattern="",
        original_score=original_score,
    )


def _luhn_checksum(digits: str) -> bool:
    """Validera Luhn-checksumma för 10 siffror (YYMMDDXXXX)."""
    if len(digits) != 10 or not digits.isdigit():
        return False
    total = 0
    for i, d in enumerate(digits):
        n = int(d)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


class SwedishPersonnummerRecognizer(EntityRecognizer):
    """Detekterar svenska personnummer (YYYYMMDD-XXXX eller YYMMDD-XXXX)."""

    PATTERNS = [
        re.compile(r"\b(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[-\s]?\d{4}\b"),
        re.compile(r"\b\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[-\s]?\d{4}\b"),
    ]

    CONTEXT_WORDS = [
        "personnummer", "personnr", "persnr", "pnr",
        "födelsedatum", "född", "födelsenummer",
        "ssn", "personal identity", "id-nummer", "identitetsnummer",
    ]

    def __init__(self):
        super().__init__(
            supported_entities=["SWEDISH_PERSONNUMMER"],
            supported_language="sv",
            name="SwedishPersonnummerRecognizer",
            context=self.CONTEXT_WORDS,
        )

    def load(self):
        pass

    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: Optional[NlpArtifacts] = None
    ) -> List[RecognizerResult]:
        results = []
        for pattern in self.PATTERNS:
            for match in pattern.finditer(text):
                raw = match.group().replace("-", "").replace(" ", "")
                # Normalisera till 10 siffror för Luhn (YYMMDDXXXX)
                if len(raw) == 12:
                    digits10 = raw[2:]
                elif len(raw) == 10:
                    digits10 = raw
                else:
                    continue

                month = int(digits10[2:4])
                day = int(digits10[4:6])
                if month < 1 or month > 12 or day < 1 or day > 31:
                    continue

                if not _luhn_checksum(digits10):
                    score = 0.4
                else:
                    score = 0.85

                results.append(
                    RecognizerResult(
                        entity_type="SWEDISH_PERSONNUMMER",
                        start=match.start(),
                        end=match.end(),
                        score=score,
                        analysis_explanation=_make_explanation(
                            self.name, "personnummer", score
                        ),
                    )
                )
        return results


class SwedishSamordningsnummerRecognizer(EntityRecognizer):
    """Detekterar svenska samordningsnummer (dag + 60, dvs. dag 61-91)."""

    PATTERNS = [
        re.compile(r"\b(19|20)\d{2}(0[1-9]|1[0-2])(6[1-9]|[78]\d|9[01])[-\s]?\d{4}\b"),
        re.compile(r"\b\d{2}(0[1-9]|1[0-2])(6[1-9]|[78]\d|9[01])[-\s]?\d{4}\b"),
    ]

    CONTEXT_WORDS = [
        "samordningsnummer", "samordningsnr",
        "coordination number", "tilldelat nummer",
    ]

    def __init__(self):
        super().__init__(
            supported_entities=["SWEDISH_SAMORDNINGSNUMMER"],
            supported_language="sv",
            name="SwedishSamordningsnummerRecognizer",
            context=self.CONTEXT_WORDS,
        )

    def load(self):
        pass

    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: Optional[NlpArtifacts] = None
    ) -> List[RecognizerResult]:
        results = []
        for pattern in self.PATTERNS:
            for match in pattern.finditer(text):
                raw = match.group().replace("-", "").replace(" ", "")
                if len(raw) == 12:
                    digits10 = raw[2:]
                elif len(raw) == 10:
                    digits10 = raw
                else:
                    continue

                day = int(digits10[4:6])
                if day < 61 or day > 91:
                    continue

                if not _luhn_checksum(digits10):
                    score = 0.4
                else:
                    score = 0.85

                results.append(
                    RecognizerResult(
                        entity_type="SWEDISH_SAMORDNINGSNUMMER",
                        start=match.start(),
                        end=match.end(),
                        score=score,
                        analysis_explanation=_make_explanation(
                            self.name, "samordningsnummer", score
                        ),
                    )
                )
        return results


class SwedishOrganisationsnummerRecognizer(EntityRecognizer):
    """Detekterar svenska organisationsnummer (3:e siffran >= 2)."""

    PATTERN = re.compile(r"\b\d{6}[-\s]?\d{4}\b")

    CONTEXT_WORDS = [
        "organisationsnummer", "organisationsnr", "orgnr", "org.nr",
        "org nr", "bolagsnummer", "företagsnummer",
        "organization number", "corporate identity",
    ]

    def __init__(self):
        super().__init__(
            supported_entities=["SWEDISH_ORGANISATIONSNUMMER"],
            supported_language="sv",
            name="SwedishOrganisationsnummerRecognizer",
            context=self.CONTEXT_WORDS,
        )

    def load(self):
        pass

    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: Optional[NlpArtifacts] = None
    ) -> List[RecognizerResult]:
        results = []
        for match in self.PATTERN.finditer(text):
            raw = match.group().replace("-", "").replace(" ", "")
            if len(raw) != 10 or not raw.isdigit():
                continue

            # 3:e siffran måste vara >= 2 (skiljer från personnummer)
            if int(raw[2]) < 2:
                continue

            if not _luhn_checksum(raw):
                score = 0.4
            else:
                score = 0.85

            results.append(
                RecognizerResult(
                    entity_type="SWEDISH_ORGANISATIONSNUMMER",
                    start=match.start(),
                    end=match.end(),
                    score=score,
                    analysis_explanation=_make_explanation(
                        self.name, "organisationsnummer", score
                    ),
                )
            )
        return results


class SwedishPhoneNumberRecognizer(PatternRecognizer):
    """Detekterar svenska telefonnummer (+46, 07X-mobil, 0XX-fast)."""

    PATTERNS = [
        Pattern(
            "swedish_phone_intl",
            r"\+46[\s-]?\d{1,3}[\s-]?\d{2,3}[\s-]?\d{2}[\s-]?\d{2}",
            0.7,
        ),
        Pattern(
            "swedish_phone_mobile",
            r"\b07[0-9][\s-]?\d{2,3}[\s-]?\d{2}[\s-]?\d{2}\b",
            0.7,
        ),
        Pattern(
            "swedish_phone_landline",
            r"\b0[1-9]\d{0,2}[\s-]?\d{2,3}[\s-]?\d{2}[\s-]?\d{2}\b",
            0.4,
        ),
    ]

    CONTEXT_WORDS = [
        "telefon", "telefonnummer", "tfn", "tel", "tel.",
        "mobil", "mobilnummer", "mobilnr",
        "ring", "kontakta", "nås på",
        "phone", "mobile", "cell",
    ]

    def __init__(self):
        super().__init__(
            supported_entity="SWEDISH_PHONE_NUMBER",
            supported_language="sv",
            patterns=self.PATTERNS,
            context=self.CONTEXT_WORDS,
            name="SwedishPhoneNumberRecognizer",
        )


class SwedishNameFormatRecognizer(EntityRecognizer):
    """Detekterar namn i formatet 'Efternamn, Förnamn' (vanligt i svenska register).

    Hanterar:
    - Bindestreck-namn: Lundberg, Gun-Britt
    - Internationella namn: Namsaenna, Amphon / Al-Rashid, Mohammed
    - Flerords-namn: Nguyen, Thi Lan / Martinez Garcia, Carlos

    Filtrerar bort false positives genom att kolla mot NER-platser
    (t.ex. 'Stockholm, Sverige').
    """

    PATTERN = re.compile(
        r"[A-ZÅÄÖÉÈÜ][a-zåäöéèüñ]+(?:[\s-][A-ZÅÄÖÉÈÜ][a-zåäöéèüñ]+)*"
        r",\s*"
        r"[A-ZÅÄÖÉÈÜ][a-zåäöéèüñ]+(?:[\s-][A-ZÅÄÖÉÈÜ][a-zåäöéèüñ]+)*"
    )

    CONTEXT_WORDS = [
        "deltagare", "handläggare", "patient", "klient",
        "medarbetare", "kontaktperson", "ansvarig", "ombud",
        "namn", "undertecknad", "närvarande", "anmälare",
        "granskare", "beslutande", "inbjuden", "mottagare",
    ]

    def __init__(self):
        super().__init__(
            supported_entities=["PERSON"],
            supported_language="sv",
            name="SwedishNameFormatRecognizer",
            context=self.CONTEXT_WORDS,
        )

    def load(self):
        pass

    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: Optional[NlpArtifacts] = None
    ) -> List[RecognizerResult]:
        results = []

        # Samla platsnamn från NER för att filtrera false positives
        location_spans = set()
        if nlp_artifacts and nlp_artifacts.entities:
            for ent in nlp_artifacts.entities:
                if ent.label_ in ("LOCATION", "LOC", "GPE"):
                    location_spans.add((ent.start_char, ent.end_char))

        for match in self.PATTERN.finditer(text):
            start, end = match.start(), match.end()
            match_len = end - start

            # Skippa om platsentiteter täcker >70% av matchningen
            # (t.ex. "Stockholm, Sverige" filtreras bort, men
            #  "Al-Rashid, Mohammed" behålls trots att en del flaggas som LOC)
            loc_overlap = 0
            for ls, le in location_spans:
                o_start = max(start, ls)
                o_end = min(end, le)
                if o_start < o_end:
                    loc_overlap += o_end - o_start
            if loc_overlap > match_len * 0.7:
                continue

            results.append(
                RecognizerResult(
                    entity_type="PERSON",
                    start=start,
                    end=end,
                    score=0.7,
                    analysis_explanation=_make_explanation(
                        self.name, "lastname_firstname", 0.7
                    ),
                )
            )
        return results


def get_swedish_recognizers() -> list:
    """Returnera alla svenska recognizers."""
    return [
        SwedishPersonnummerRecognizer(),
        SwedishSamordningsnummerRecognizer(),
        SwedishOrganisationsnummerRecognizer(),
        SwedishPhoneNumberRecognizer(),
        SwedishNameFormatRecognizer(),
    ]
