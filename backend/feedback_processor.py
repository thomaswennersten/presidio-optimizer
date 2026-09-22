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
Strukturerar och aggregerar användarfeedback för LLM-optimering.

Tar emot raw feedback (false positives + false negatives med positioner)
och skapar strukturerad data med textkontext och mönsteraggregering.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


def process_feedback(
    text: str,
    analysis_results: List[Dict[str, Any]],
    false_positives: List[Dict[str, Any]],
    false_negatives: List[Dict[str, Any]],
    context_chars: int = 80,
) -> Dict[str, Any]:
    """Process raw feedback into structured data for LLM optimization.

    Args:
        text: The original document text
        analysis_results: Current Presidio analysis results
        false_positives: List of {"start", "end", "entity_type"} wrongly detected
        false_negatives: List of {"start", "end", "entity_type", "text"} missed PII
        context_chars: Number of chars of surrounding context to include

    Returns:
        Structured feedback dict for LLM prompt
    """
    structured = {
        "summary": {},
        "false_positives": [],
        "false_negatives": [],
        "patterns": {},
        "current_detection_stats": {},
    }

    # Count current detections by type
    type_counts = Counter()
    for r in analysis_results:
        type_counts[r["entity_type"]] += 1
    structured["current_detection_stats"] = dict(type_counts)

    # Process false positives
    fp_by_type = defaultdict(list)
    for fp in false_positives:
        start = fp.get("start", 0)
        end = fp.get("end", 0)
        entity_type = fp.get("entity_type", "UNKNOWN")
        matched_text = text[start:end] if start < len(text) and end <= len(text) else ""

        ctx_start = max(0, start - context_chars)
        ctx_end = min(len(text), end + context_chars)
        context = text[ctx_start:ctx_end]

        entry = {
            "entity_type": entity_type,
            "text": matched_text,
            "start": start,
            "end": end,
            "context": context,
            "score": fp.get("score", 0),
        }
        structured["false_positives"].append(entry)
        fp_by_type[entity_type].append(matched_text)

    # Process false negatives
    fn_by_type = defaultdict(list)
    for fn in false_negatives:
        start = fn.get("start", 0)
        end = fn.get("end", 0)
        entity_type = fn.get("entity_type", "UNKNOWN")
        missed_text = fn.get("text", text[start:end] if start < len(text) and end <= len(text) else "")

        ctx_start = max(0, start - context_chars)
        ctx_end = min(len(text), end + context_chars)
        context = text[ctx_start:ctx_end]

        entry = {
            "entity_type": entity_type,
            "text": missed_text,
            "start": start,
            "end": end,
            "context": context,
        }
        structured["false_negatives"].append(entry)
        fn_by_type[entity_type].append(missed_text)

    # Aggregate patterns
    patterns = {}

    for entity_type, texts in fp_by_type.items():
        patterns.setdefault(entity_type, {"false_positives": [], "false_negatives": []})
        common = _find_common_patterns(texts)
        patterns[entity_type]["false_positives"] = {
            "count": len(texts),
            "examples": texts[:5],
            "common_patterns": common,
        }

    for entity_type, texts in fn_by_type.items():
        patterns.setdefault(entity_type, {"false_positives": [], "false_negatives": []})
        common = _find_common_patterns(texts)
        patterns[entity_type]["false_negatives"] = {
            "count": len(texts),
            "examples": texts[:5],
            "common_patterns": common,
        }

    structured["patterns"] = patterns

    # Summary
    structured["summary"] = {
        "total_detections": len(analysis_results),
        "false_positive_count": len(false_positives),
        "false_negative_count": len(false_negatives),
        "precision_estimate": _estimate_precision(len(analysis_results), len(false_positives)),
        "affected_entity_types": list(set(
            list(fp_by_type.keys()) + list(fn_by_type.keys())
        )),
    }

    return structured


def _find_common_patterns(texts: List[str]) -> List[str]:
    """Find common patterns in a list of text strings."""
    if not texts:
        return []

    patterns = []

    # Check for common formats
    digit_patterns = Counter()
    for t in texts:
        normalized = re.sub(r'\d', 'D', t)
        normalized = re.sub(r'[a-zåäö]', 'a', normalized)
        normalized = re.sub(r'[A-ZÅÄÖ]', 'A', normalized)
        digit_patterns[normalized] += 1

    for pattern, count in digit_patterns.most_common(3):
        if count > 1:
            patterns.append(f"Format '{pattern}' ({count} occurrences)")

    # Check for common prefixes
    if len(texts) >= 2:
        prefix = _common_prefix(texts)
        if len(prefix) >= 2:
            patterns.append(f"Common prefix: '{prefix}'")

    # Check for common lengths
    lengths = Counter(len(t) for t in texts)
    for length, count in lengths.most_common(2):
        if count > 1:
            patterns.append(f"Length {length} ({count} occurrences)")

    return patterns


def _common_prefix(strings: List[str]) -> str:
    """Find common prefix of a list of strings."""
    if not strings:
        return ""
    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix


def _estimate_precision(total: int, false_positives: int) -> float:
    """Estimate precision based on false positive count."""
    if total == 0:
        return 1.0
    true_positives = max(0, total - false_positives)
    return round(true_positives / total, 3) if total > 0 else 1.0
