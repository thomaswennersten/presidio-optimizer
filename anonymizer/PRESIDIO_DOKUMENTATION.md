# Presidio Anonymizer — teknisk dokumentation

Senast uppdaterad: 2026-02-12

## Vad ar detta?

En webbtjanst for att anonymisera personuppgifter (PII) i dokument. Anvandaren laddar upp en fil (docx, xlsx, pdf, txt) via ett webbgranssnitt, och far tillbaka en anonymiserad kopia dar personuppgifter ersatts med platsmarkorer som `[PERSON]`, `[PERSONNUMMER]`, `[TELEFON]` etc.

Tjansten bygger pa Microsoft Presidio (https://github.com/microsoft/presidio) med egenutvecklade tillagg for svenska personuppgifter.

---

## Containrar

Tjansten bestar av tva containrar, definierade i `docker-compose.yml`:

### Backend (presidio-anonymizer)

| Egenskap | Varde |
|----------|-------|
| Image | Bygge fran `./presidio-anonymizer/Dockerfile` |
| Basimage | python:3.11-slim |
| Port | backend:8000 -> 8000 |
| Kommando | `uvicorn main:app --host 0.0.0.0 --port 8000 --reload` |
| Restart | always |

Volymmount (bind mount — andringer syns direkt tack vare `--reload`):

```
./presidio-anonymizer/backend  ->  /app         (Python-kod)
./presidio-anonymizer/frontend ->  /app/static  (statiska filer)
```

Miljövariabler:

```
PYTHONUNBUFFERED=1
UPLOAD_FOLDER=/tmp/uploads
OUTPUT_FOLDER=/tmp/outputs
```

### Frontend (presidio-frontend)

| Egenskap | Varde |
|----------|-------|
| Image | nginx:alpine |
| Port | localhost:8080 -> 80 |
| Restart | always |

Volymmount:

```
./presidio-anonymizer/frontend    ->  /usr/share/nginx/html
./presidio-anonymizer/nginx.conf  ->  /etc/nginx/conf.d/default.conf
```

Frontend-nginx proxar `/api/`-anrop till backend pa backend:8000.

### Extern atkomst

Nginx reverse proxy (elestio-nginx) exponerar tjansten pa:

```
http://localhost:8080/  (frontend)
```

Konfigurerat med 10 MB maxuppladdning och 300s timeout.

---

## Filstruktur

```
./
|-- Dockerfile                    # Bygger backend-imagen
|-- nginx.conf                    # Nginx-konfiguration for frontend
|-- backend/
|   |-- main.py                   # FastAPI-app, endpoints
|   |-- presidio_service.py       # Presidio-logik, NLP-motor, anonymisering
|   |-- swedish_recognizers.py    # 5 svenska custom recognizers
|   |-- document_processor.py     # Textextraktion fran docx/xlsx/pdf/txt
|   |-- requirements.txt          # Python-beroenden
|   `-- .env                      # Konfiguration (tom = lokalt lage)
`-- frontend/
    |-- index.html                # Webbgranssnitt
    |-- styles.css
    `-- app.js
```

---

## Dockerfile

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y gcc g++
RUN pip install -r requirements.txt
RUN python -m spacy download sv_core_news_sm    # Svenska NER
RUN python -m spacy download en_core_web_sm     # Engelska NER
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

Bada spaCy-modellerna installeras vid byggtid. `--reload` gor att kodandringar i bind-mounten tradar i kraft automatiskt utan omstart.

---

## Python-beroenden

| Paket | Version | Syfte |
|-------|---------|-------|
| presidio-analyzer | 2.2.354 | PII-detektering |
| presidio-anonymizer | 2.2.354 | PII-anonymisering |
| spacy | 3.8.7 | NLP-motor (NER) |
| fastapi | 0.104.1 | Webb-API |
| uvicorn | 0.24.0 | ASGI-server |
| python-docx | 1.1.0 | DOCX-lasning/skrivning |
| openpyxl | 3.1.2 | XLSX-lasning/skrivning |
| PyPDF2 | 3.0.1 | PDF-lasning |
| httpx | 0.25.2 | HTTP-klient (for remote Presidio) |
| aiofiles | 23.2.1 | Asynkron filhantering |

---

## API-endpoints

| Metod | Sokvag | Beskrivning |
|-------|--------|-------------|
| GET | `/` | Statusmeddelande |
| GET | `/health` | Halsocheck |
| GET | `/api/health` | Halsocheck (alt.) |
| POST | `/api/analyze` | Analysera fil, returnera hittade PII-entiteter (JSON) |
| POST | `/api/anonymize` | Anonymisera fil, returnera anonymiserad kopia |

Bada POST-endpoints tar emot en fil via multipart form upload (`file`-falt).

Tillatna filtyper: **docx, xlsx, pdf, txt**
Max filstorlek: **10 MB**
Uppladdade filer tas bort omedelbart. Anonymiserade filer rensas efter 5 minuter.

---

## Sprakkonfiguration

### Tvasprakig NLP-motor

Tjansten kor tva spaCy-modeller parallellt:

| Modell | Sprak | NER-etiketter |
|--------|-------|---------------|
| `en_core_web_sm` | Engelska | PER, LOC, GPE, ORG, DATE, TIME, NORP |
| `sv_core_news_sm` | Svenska | PRS, LOC, ORG, TME, EVN, MSR, OBJ, WRK |

### NER-etikettmappning

Den svenska modellen anvander andra etiketter an Presidio forutsatter. En custom `NerModelConfiguration` mappar dem:

| spaCy-etikett | Presidio-entitet | Beskrivning |
|---------------|------------------|-------------|
| PRS | PERSON | Personnamn (svenska modellen) |
| PER / PERSON | PERSON | Personnamn (engelska modellen) |
| LOC / GPE | LOCATION | Platser, lander |
| ORG | ORGANIZATION | Organisationer |
| TME | DATE_TIME | Tidsangivelser (svenska modellen) |
| DATE / TIME | DATE_TIME | Datum/tid (engelska modellen) |
| NORP | NRP | Nationalitet/religion |

Etiketter som ignoreras: EVN, MSR, OBJ, WRK, PRODUCT, ORDINAL, EVENT, PERCENT, QUANTITY, LAW, CARDINAL, MONEY, WORK_OF_ART, LANGUAGE.

### Tvasprakig analys

Nar spraket ar `sv` (standard) kors analysen i tva steg:

1. **Svensk analys** — spaCy `sv_core_news_sm` + alla svenska custom recognizers
2. **Engelsk analys** — spaCy `en_core_web_sm` (fangar internationella namn battre)

Resultaten slas ihop med en merge-algoritm som prioriterar langre namnspan framfor korta fragment vid overlappning.

---

## PII-entiteter som detekteras

### Standard (fran Presidio + spaCy NER)

| Entitet | Metod | Anonymiseras som |
|---------|-------|------------------|
| PERSON | spaCy NER (bada modeller) | `[PERSON]` |
| EMAIL_ADDRESS | Regex (inbyggd) | `[EMAIL]` |
| PHONE_NUMBER | Regex (inbyggd, internationell) | `[PHONE]` |
| CREDIT_CARD | Regex + Luhn (inbyggd) | Maskeras med `*` |
| IBAN_CODE | Regex (inbyggd) | Maskeras med `*` |
| LOCATION | spaCy NER | `[PLATS]` |
| DATE_TIME | spaCy NER | `[DATUM]` |
| IP_ADDRESS | Regex (inbyggd) | `[IP]` |
| URL | Regex (inbyggd) | `[URL]` |
| NRP | spaCy NER | `[ID]` |
| MEDICAL_LICENSE | Regex (inbyggd) | `[LICENSE]` |

### Svenska custom recognizers (swedish_recognizers.py)

#### 1. SwedishPersonnummerRecognizer

**Entitet:** `SWEDISH_PERSONNUMMER` -> `[PERSONNUMMER]`

Detekterar personnummer i formaten `YYYYMMDD-XXXX` och `YYMMDD-XXXX`.

Validering:
- Regex matchar ratt format (manad 01-12, dag 01-31)
- Luhn-checksumma pa de sista 10 siffrorna (YYMMDDXXXX)
- Score 0.85 om Luhn ar korrekt, 0.4 om inte (under troskelvardet 0.5)
- Kontextord ("personnummer", "personnr", "pnr" m.fl.) hojer scoren

#### 2. SwedishSamordningsnummerRecognizer

**Entitet:** `SWEDISH_SAMORDNINGSNUMMER` -> `[SAMORDNINGSNUMMER]`

Samma format som personnummer men dagdelen ar forhojd med 60 (dag 61-91).

#### 3. SwedishOrganisationsnummerRecognizer

**Entitet:** `SWEDISH_ORGANISATIONSNUMMER` -> `[ORGANISATIONSNUMMER]`

Format: `NNNNNN-NNNN` (10 siffror). Tredje siffran maste vara >= 2 (skiljer fran personnummer). Luhn-validering.

#### 4. SwedishPhoneNumberRecognizer

**Entitet:** `SWEDISH_PHONE_NUMBER` -> `[TELEFON]`

Tre monster:

| Monster | Exempel | Basscore |
|---------|---------|----------|
| `+46 XX XXX XX XX` | +46 70 123 45 67 | 0.7 |
| `07X-XXX XX XX` | 070-123 45 67 | 0.7 |
| `0XX-XXX XX XX` | 031-123 45 67 | 0.4 |

Kontextord ("telefon", "mobil", "tfn" m.fl.) hojer scoren.

#### 5. SwedishNameFormatRecognizer

**Entitet:** `PERSON` -> `[PERSON]`

Detekterar namn i formatet "Efternamn, Fornamn" som ar vanligt i svenska register och journaler.

Hanterar:
- Svenska namn: `Lundberg, Gun-Britt`
- Internationella namn: `Al-Rashid, Mohammed` / `Namsaenna, Amphon`
- Flerords-namn: `Nguyen, Thi Lan` / `Martinez Garcia, Carlos`

Filterar bort false positives (t.ex. "Stockholm, Sverige") genom att kontrollera mot NER-detekterade platser — om >70% av matchningen overlappar med en kand LOCATION-entitet sa skippas den.

Kontextord ("deltagare", "handlaggare", "patient" m.fl.) hojer scoren.

---

## Anonymiseringsoperatorer

Vad varje PII-typ ersatts med:

| Entitet | Operator | Resultat |
|---------|----------|----------|
| PERSON | replace | `[PERSON]` |
| EMAIL_ADDRESS | replace | `[EMAIL]` |
| PHONE_NUMBER | replace | `[PHONE]` |
| CREDIT_CARD | mask | `****XXXX****XXXX` |
| IBAN_CODE | mask | `**************XXXX` |
| LOCATION | replace | `[PLATS]` |
| DATE_TIME | replace | `[DATUM]` |
| IP_ADDRESS | replace | `[IP]` |
| URL | replace | `[URL]` |
| NRP | replace | `[ID]` |
| SWEDISH_PERSONNUMMER | replace | `[PERSONNUMMER]` |
| SWEDISH_SAMORDNINGSNUMMER | replace | `[SAMORDNINGSNUMMER]` |
| SWEDISH_ORGANISATIONSNUMMER | replace | `[ORGANISATIONSNUMMER]` |
| SWEDISH_PHONE_NUMBER | replace | `[TELEFON]` |
| Ovrigt | replace | `[REDACTED]` |

---

## Merge-algoritm (tvasprakig resultatsammanslagning)

Nar bade svensk och engelsk NER kors kan samma textstycke hittas av bada. Merge-algoritmen:

1. Sorterar alla resultat efter spannlangd (langst forst), sedan score
2. For varje resultat:
   - **Samma entitetstyp + >50% overlapp**: kortare fragmentet tas bort (langre span behalls for battre anonymisering)
   - **Olika entitetstyper**: kortare tas bort bara om det ar helt inneslutet i det langre
3. Resultatet ar en lista utan dubbletter dar langre span prioriteras

Exempel: NER hittar "Gun-Britt" (9 tecken, score 0.85) och name-format-recognizer hittar "Lundberg, Gun-Britt" (19 tecken, score 0.7). Mergen behaaller det langre "Lundberg, Gun-Britt".

---

## Luhn-algoritmen

Anvands for validering av personnummer, samordningsnummer och organisationsnummer.

Berakning pa 10 siffror (YYMMDDXXXX):

1. Multiplicera varje siffra fran vanster omvaxlande med 2 och 1
2. Om produkten ar >9, dra bort 9
3. Summera alla resultat
4. Giltig om summan ar jamnt delbar med 10

Exempel: `900101-1007`
```
Siffror:  9  0  0  1  0  1  1  0  0  7
Faktor:   2  1  2  1  2  1  2  1  2  1
Produkt: 18  0  0  1  0  1  2  0  0  7
Justerat: 9  0  0  1  0  1  2  0  0  7
Summa: 20 (20 % 10 = 0 -> giltig)
```

---

## Driftslage

### Lokalt lage (nuvarande)

Nar `.env`-filens `PRESIDIO_ANALYZER_ENDPOINT` och `PRESIDIO_ANONYMIZER_ENDPOINT` ar tomma kors allt lokalt i containern. Bada spaCy-modellerna laddas vid uppstart och alla recognizers registreras.

### Remote-lage (ej aktivt)

Om endpoints sätts i `.env` kan tjansten proxya till en extern Presidio-installation (t.ex. Azure). Stodjer Basic Auth och API-nyckel. Faller tillbaka till lokalt lage vid fel.

---

## Dokumenthantering

Textextraktion per filtyp:

| Format | Metod | Detaljer |
|--------|-------|----------|
| TXT | Direkt lasning | UTF-8 |
| DOCX | python-docx | Paragrafer + tabellceller |
| XLSX | openpyxl | Alla ark, tab-separerade celler |
| PDF | PyPDF2 | Sidvis textextraktion |

Anonymiserad utdata:
- TXT/DOCX/XLSX: aterskap i samma format
- PDF: returneras som textfil (PDF-generering stods ej)

---

## Kanda begransningar

- `sv_core_news_sm` ar en liten modell — missar ibland namn efter titlar ("Dr. Eva Sundstrom")
- Namn i formatet "Fornamn Efternamn" utan kontextord kan missas om de ar ovanliga/internationella
- PDF-anonymisering returnerar text, inte ny PDF
- Ingen OCR — skannade PDF:er utan inbaddad text kan inte anonymiseras
- Max 10 MB filstorlek

---

## Testexempel

### Analysera en fil

```bash
echo "Anna Svensson har personnummer 19850315-2408 och telefon 073-456 78 90" \
  > /tmp/test.txt

curl -s -X POST http://backend:8000/api/analyze \
  -F "file=@/tmp/test.txt" | python3 -m json.tool
```

### Anonymisera en fil

```bash
curl -s -X POST http://backend:8000/api/anonymize \
  -F "file=@/tmp/test.txt" --output /tmp/result.txt

cat /tmp/result.txt
# [PERSON] har personnummer [PERSONNUMMER] och telefon [TELEFON]
```
