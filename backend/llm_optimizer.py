"""
Claude API-integration för LLM-driven Presidio-konfigurationsoptimering.

Skickar strukturerad feedback till Claude och parsar JSON-svar med
konfigurationsändringar (add_recognizer, adjust_threshold, etc.).
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """Du är en expert på Microsoft Presidio, ett ramverk för PII-detektion (Personally Identifiable Information). Du hjälper till att optimera Presidio-konfigurationer för svensk text.

## Presidio-arkitektur
- **AnalyzerEngine** kör recognizers mot text och returnerar entiteter med start/end/score
- **Recognizers** kan vara:
  - Pattern-baserade (regex med score)
  - NER-baserade (spaCy-modeller)
  - Deny-list-baserade (exakta strängmatchningar)
- Varje recognizer har **context_words** som höjer score vid närhet till nyckelord
- **score_threshold** (global) filtrerar bort resultat under tröskeln

## Tillgängliga konfigurationsändringar
Du kan föreslå följande ändringar i JSON-format:

1. **add_recognizer** - Lägg till en ny pattern/deny-list-recognizer
   ```json
   {"action": "add_recognizer", "target": "recognizer_name", "details": {
     "entity_type": "ENTITY_TYPE",
     "patterns": [{"name": "pattern_name", "regex": "regex_pattern", "score": 0.7}],
     "deny_list": ["ord1", "ord2"],
     "context_words": ["kontext1", "kontext2"],
     "supported_language": "sv"
   }}
   ```

2. **modify_recognizer** - Ändra en befintlig custom recognizer
   ```json
   {"action": "modify_recognizer", "target": "recognizer_name", "details": {
     "patterns": [...],
     "deny_list": [...],
     "context_words": [...]
   }}
   ```

3. **adjust_threshold** - Justera tröskelvärde för en entitetstyp
   ```json
   {"action": "adjust_threshold", "target": "ENTITY_TYPE", "details": {
     "new_threshold": 0.65
   }}
   ```

4. **toggle_entity** - Aktivera/avaktivera en entitetstyp
   ```json
   {"action": "toggle_entity", "target": "ENTITY_TYPE", "details": {
     "enabled": false
   }}
   ```

5. **adjust_global_threshold** - Ändra globalt tröskelvärde
   ```json
   {"action": "adjust_global_threshold", "details": {
     "new_threshold": 0.45
   }}
   ```

## Svenska PII-regler
- **Personnummer**: YYYYMMDD-XXXX, valideras med Luhn-checksumma
- **Samordningsnummer**: Som personnummer men dag+60 (61-91)
- **Organisationsnummer**: 10 siffror, 3:e siffran >= 2, Luhn-validering
- **Telefonnummer**: +46..., 07X-..., 0XX-...
- **Namn**: "Efternamn, Förnamn"-format vanligt i svenska register

## Regler för dina förslag
- Var konservativ - ändra inte mer än nödvändigt
- Förklara varje ändring och varför den behövs
- Regex-mönster måste vara giltiga Python-regex
- Testa inte mönster som skulle matcha halva alfabetet
- Om false positives dominerar: höj tröskelvärden eller lägg till mer specifika mönster
- Om false negatives dominerar: sänk tröskelvärden eller lägg till nya recognizers
- Context words ska vara svenska ord som ofta förekommer nära PII

## Svarsformat
Svara ALLTID med giltig JSON i exakt detta format:
```json
{
  "reasoning": "Din analys av feedbackmönstren...",
  "changes": [
    {"action": "...", "target": "...", "details": {...}}
  ],
  "expected_improvements": "Vad som bör förbättras efter dessa ändringar..."
}
```"""


async def optimize_config(
    current_config: dict,
    feedback: Dict[str, Any],
    text_sample: str = "",
) -> Dict[str, Any]:
    """Call Claude API to optimize Presidio config based on feedback.

    Args:
        current_config: Current PresidioConfig as dict
        feedback: Structured feedback from feedback_processor
        text_sample: Optional text excerpt for context

    Returns:
        Dict with reasoning, changes list, expected_improvements
    """
    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed")
        return _error_response("Anthropic SDK not installed")

    if not ANTHROPIC_API_KEY:
        return _error_response("ANTHROPIC_API_KEY not set")

    user_prompt = _build_user_prompt(current_config, feedback, text_sample)

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = message.content[0].text
        return _parse_response(response_text)

    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return _error_response(f"API error: {str(e)}")


def _build_user_prompt(config: dict, feedback: Dict[str, Any], text_sample: str) -> str:
    """Build the user prompt with config, feedback, and text context."""
    parts = []

    parts.append("## Nuvarande konfiguration")
    parts.append("```json")
    parts.append(json.dumps(config, ensure_ascii=False, indent=2)[:3000])
    parts.append("```")

    parts.append("\n## Feedback-sammanfattning")
    summary = feedback.get("summary", {})
    parts.append(f"- Totalt detekterade: {summary.get('total_detections', 0)}")
    parts.append(f"- False positives: {summary.get('false_positive_count', 0)}")
    parts.append(f"- False negatives: {summary.get('false_negative_count', 0)}")
    parts.append(f"- Uppskattad precision: {summary.get('precision_estimate', 'N/A')}")

    if feedback.get("false_positives"):
        parts.append("\n## False positives (felaktigt detekterade)")
        for fp in feedback["false_positives"][:10]:
            parts.append(f"- Typ: {fp['entity_type']}, Text: \"{fp['text']}\", Score: {fp.get('score', 'N/A')}")
            parts.append(f"  Kontext: ...{fp['context']}...")

    if feedback.get("false_negatives"):
        parts.append("\n## False negatives (missade PII)")
        for fn in feedback["false_negatives"][:10]:
            parts.append(f"- Typ: {fn['entity_type']}, Text: \"{fn['text']}\"")
            parts.append(f"  Kontext: ...{fn['context']}...")

    if feedback.get("patterns"):
        parts.append("\n## Aggregerade mönster")
        for entity_type, data in feedback["patterns"].items():
            parts.append(f"\n### {entity_type}")
            if isinstance(data.get("false_positives"), dict) and data["false_positives"].get("count"):
                fp_data = data["false_positives"]
                parts.append(f"  False positives: {fp_data['count']} st")
                if fp_data.get("common_patterns"):
                    for p in fp_data["common_patterns"]:
                        parts.append(f"    - {p}")
            if isinstance(data.get("false_negatives"), dict) and data["false_negatives"].get("count"):
                fn_data = data["false_negatives"]
                parts.append(f"  False negatives: {fn_data['count']} st")
                if fn_data.get("common_patterns"):
                    for p in fn_data["common_patterns"]:
                        parts.append(f"    - {p}")

    if text_sample:
        parts.append("\n## Textexempel (utdrag)")
        parts.append(f"```\n{text_sample[:2000]}\n```")

    parts.append("\n## Uppgift")
    parts.append("Analysera feedbacken ovan och föreslå konfigurationsändringar i JSON-format.")
    parts.append("Svara ENBART med JSON-objektet (reasoning, changes, expected_improvements).")

    return "\n".join(parts)


def _parse_response(text: str) -> Dict[str, Any]:
    """Parse Claude's response, extracting JSON from potential markdown."""
    # Try to find JSON block
    json_match = None

    # Try ```json ... ``` block first
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        json_match = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        json_match = text[start:end].strip()
    elif text.strip().startswith("{"):
        json_match = text.strip()

    if json_match:
        try:
            result = json.loads(json_match)
            if "reasoning" in result and "changes" in result:
                return result
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")

    # Fallback: try to parse the whole text as JSON
    try:
        result = json.loads(text)
        return result
    except json.JSONDecodeError:
        pass

    return {
        "reasoning": "Could not parse LLM response as JSON",
        "changes": [],
        "expected_improvements": "",
        "raw_response": text[:2000],
    }


def _error_response(msg: str) -> Dict[str, Any]:
    return {
        "reasoning": f"Error: {msg}",
        "changes": [],
        "expected_improvements": "",
    }
