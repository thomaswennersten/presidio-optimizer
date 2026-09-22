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
# claude-sonnet-4-20250514 är avvecklad och gav 404 på varje optimering
# (upptäckt 2026-08-19). Håll denna aktuell — felet syns annars bara i loggen.
MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """Du är en expert på Microsoft Presidio, ett ramverk för PII-detektion (Personally Identifiable Information). Du hjälper till att optimera Presidio-konfigurationer för svensk text.

## Presidio-arkitektur
- **AnalyzerEngine** kör recognizers mot text och returnerar entiteter med start/end/score
- **Recognizers** kan vara:
  - Pattern-baserade (regex med score)
  - NER-baserade (spaCy-modeller)
  - Deny-list-baserade (exakta strängmatchningar som LÄGGER TILL träffar)
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

6. **add_exclusion** - Undanta ett enskilt ord från en entitetstyp
   ```json
   {"action": "add_exclusion", "target": "Användningspart", "details": {
     "text": "Användningspart",
     "entity_type": "PERSON"
   }}
   ```
   Sätt `entity_type` till null för att undanta ordet oavsett typ.
   Motsatsen är `remove_exclusion` med samma form.

## VIKTIGT om falska positiva från NER-modellen

Detta är den vanligaste feltypen och den har bara **en** korrekt lösning.

- `deny_list` är **ADDITIV** — den SKAPAR träffar (score 1.0). Att lägga ett ord
  i en deny_list för att bli av med det gör tvärtom: ordet blir garanterat
  flaggat varje gång. Använd den ALDRIG för att ta bort en falsk positiv.
- `adjust_threshold` hjälper **inte** mot NER-träffar. Presidio ger varje
  spaCy-träff den fasta poängen **0.85** oavsett säkerhet. En tröskel över 0.85
  tar bort ALLA namn, även de riktiga.
- `toggle_entity` stänger av hela entitetstypen — aldrig rätt för ett enskilt ord.

**Rätt åtgärd för ett felaktigt markerat ord är `add_exclusion`.**
Tröskeljustering är däremot rätt för MÖNSTER-baserade träffar, som har
varierande poäng.

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
            # 🔴 Tanketokens räknas mot max_tokens. Med 8192 hann adaptivt
            # tankeläge äta upp hela utrymmet på ett stort regelverk, och svaret
            # innehöll BARA ett thinking-block — HTTP 200, stop_reason
            # "max_tokens", noll textblock. Det såg ut som ett tomt svar från
            # modellen men var en för snäv gräns.
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            # Adaptivt tankeläge — uppgiften är en avvägning mellan feedbackmönster
            # och konfigurationsåtgärder, inte en uppslagning. Notera att
            # budget_tokens avvisas av Sonnet 5; adaptive är rätt form.
            thinking={"type": "adaptive"},
            # Uppgiften är avgränsad: läs feedback, föreslå konfigurationsändringar.
            # Standard är "high", vilket lägger mer i tankeledet än den behöver
            # och tränger undan själva svaret.
            output_config={"effort": "medium"},
        )

        logger.info("Optimering: stop_reason=%s, block=%s, tokens in/ut=%s/%s",
                    getattr(message, "stop_reason", "?"),
                    [getattr(b, "type", "?") for b in (message.content or [])],
                    getattr(getattr(message, "usage", None), "input_tokens", "?"),
                    getattr(getattr(message, "usage", None), "output_tokens", "?"))

        response_text = _text_ur_svaret(message)
        if not response_text:
            # Skilj på "tog slut på utrymme" och "svarade tomt". Det första går
            # att åtgärda, det andra inte — och tidigare såg de likadana ut.
            if getattr(message, "stop_reason", None) == "max_tokens":
                logger.error("Svaret tog slut vid max_tokens innan något textblock "
                             "hann skrivas; blocktyper: %s",
                             [getattr(b, "type", "?") for b in (message.content or [])])
                return _error_response(
                    "Svaret nådde tokengränsen innan modellen hann skriva något "
                    "förslag. Regelverket eller feedbacken är för stor för en "
                    "omgång — markera färre träffar åt gången och försök igen."
                )
            logger.error("Inget textblock i svaret; blocktyper: %s",
                         [getattr(b, "type", "?") for b in (message.content or [])])
            return _error_response("Modellen returnerade inget textinnehåll")
        return _parse_response(response_text)

    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return _error_response(f"API error: {str(e)}")


def _text_ur_svaret(message) -> str:
    """Plocka ut textinnehållet ur ett Messages-svar.

    Tidigare läste koden `message.content[0].text` rakt av. Med adaptivt
    tankeläge är det första blocket ofta ett ThinkingBlock, som saknar `.text` —
    därav felet "'ThinkingBlock' object has no attribute 'text'". Felet var
    dessutom sporadiskt, eftersom tankeläget slår till beroende på uppgiften.
    """
    delar = []
    for block in (message.content or []):
        if getattr(block, "type", None) == "text":
            delar.append(block.text)
    return "\n".join(delar).strip()


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

    # Markera misslyckandet uttryckligen. Utan flaggan blev "kunde inte tolka
    # svaret" visuellt identiskt med "inga ändringar behövdes" i gränssnittet.
    return {
        "fel": "Modellens svar gick inte att tolka som JSON.",
        "reasoning": "Svaret från modellen kunde inte tolkas som JSON. "
                     "Konfigurationen är oförändrad.",
        "changes": [],
        "expected_improvements": "",
        "raw_response": text[:2000],
    }


def _error_response(msg: str) -> Dict[str, Any]:
    return {
        "fel": msg,
        "reasoning": f"Optimeringen kunde inte genomföras: {msg}. "
                     "Konfigurationen är oförändrad.",
        "changes": [],
        "expected_improvements": "",
    }
