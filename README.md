# Presidio-verktyg

Två verktyg för att hitta och maskera personuppgifter i svenska dokument,
byggda kring [Microsoft Presidio](https://microsoft.github.io/presidio/).

| Katalog | Verktyg | Vad det gör |
|---|---|---|
| [`optimizer/`](optimizer/) | Presidio Optimizer | Ta fram och finjustera regelverk för PII-igenkänning. Ladda upp dokument, markera felaktiga och missade träffar, och låt en språkmodell föreslå ändringar i konfigurationen. |
| [`anonymizer/`](anonymizer/) | Presidio Anonymizer | Maskera personuppgifter i enskilda dokument (DOCX, XLSX, PDF, TXT) med färdiga regler. |

Verktygen körs var för sig och har varsin `docker-compose.yml`. Se respektive
katalogs dokumentation för hur man kommer igång.

## Svenska personuppgifter

Båda innehåller egna igenkännare för personnummer, samordningsnummer,
organisationsnummer och svenska telefonnummer, med Luhn-kontroll. Analysen är
tvåspråkig (`sv_core_news_sm` + `en_core_web_sm`).

🔴 **Verktygen maskerar — de anonymiserar inte.** Personuppgifter ersätts med
platshållare som `[PERSON]` och `[PERSONNUMMER]`. Det är inte anonymisering i
dataskyddsförordningens mening. Bedöm själva om resultatet räcker för ert ändamål,
och granska alltid utfallet: den svenska språkmodellen är liten och missar ibland
namn som saknar omgivande kontext.

## Delad kod

`optimizer/backend/document_processor.py` och `swedish_recognizers.py` är i dag
identiska med sina motsvarigheter under `anonymizer/backend/`. De bör på sikt
brytas ut till en gemensam modul — en rättning i det ena når i nuläget inte det andra.

## Licens

GPL-2.0, se [LICENSE](LICENSE). Copyright (C) 2026 Sambruk.
