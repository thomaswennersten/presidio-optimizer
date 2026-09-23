# Presidio Anonymizer - Svensk PII-konfiguration

## Oversikt

Presidio Anonymizer detekterar och anonymiserar personuppgifter (PII) i text. Systemet stodjer bade engelska och svenska med hjalp av spaCy NLP-modeller och egenutvecklade recognizers for svenska PII-typer.

## Sprakstod

| Sprak   | NLP-modell        | Beskrivning                         |
|---------|-------------------|-------------------------------------|
| English | `en_core_web_sm`  | Engelska NER (standard i Presidio)  |
| Svenska | `sv_core_news_sm` | Svenska NER (namnigenkanning m.m.)  |

Spraket valjs via `language`-parametern i API-anropet. Standard ar `sv`.

## Entitetstyper

### Standard (engelska + svenska via NER)

| Entitetstyp       | Beskrivning                      | Anonymiseras som  |
|-------------------|----------------------------------|-------------------|
| PERSON            | Personnamn                       | `[PERSON]`        |
| EMAIL_ADDRESS     | E-postadresser                   | `[EMAIL]`         |
| PHONE_NUMBER      | Internationella telefonnummer    | `[PHONE]`         |
| CREDIT_CARD       | Kreditkortsnummer                | Maskeras med `*`  |
| IBAN_CODE         | IBAN-konton                      | Maskeras med `*`  |
| LOCATION          | Platser och adresser             | `[PLATS]`         |
| DATE_TIME         | Datum och tider                  | `[DATUM]`         |
| IP_ADDRESS        | IP-adresser                      | `[IP]`            |
| URL               | Webbadresser                     | `[URL]`           |
| NRP               | Nationalitet/religion/politik    | `[ID]`            |
| MEDICAL_LICENSE   | Medicinska licenser              | `[LICENSE]`       |

### Svenska (custom recognizers)

| Entitetstyp                    | Beskrivning              | Anonymiseras som         |
|--------------------------------|--------------------------|--------------------------|
| SWEDISH_PERSONNUMMER           | Personnummer             | `[PERSONNUMMER]`         |
| SWEDISH_SAMORDNINGSNUMMER      | Samordningsnummer        | `[SAMORDNINGSNUMMER]`    |
| SWEDISH_ORGANISATIONSNUMMER    | Organisationsnummer      | `[ORGANISATIONSNUMMER]`  |
| SWEDISH_PHONE_NUMBER           | Svenska telefonnummer    | `[TELEFON]`              |

## Personnummer-validering

Personnummer valideras i flera steg:

1. **Format**: `YYYYMMDD-XXXX` eller `YYMMDD-XXXX` (bindestreck valfritt)
2. **Datumvalidering**: Manad 01-12, dag 01-31
3. **Luhn-checksumma**: De sista 10 siffrorna (YYMMDDXXXX) valideras med Luhn-algoritmen

### Luhn-algoritmen
Varje siffra multipliceras omvaxlande med 2 och 1 (fran vanster). Om produkten ar >9 dras 9 bort. Summan av alla siffror ska vara delbar med 10.

## Samordningsnummer
Samma format som personnummer men dagdelen ar forhojd med 60 (dag 61-91). Samma Luhn-validering.

## Organisationsnummer
Format: `NNNNNN-NNNN` (10 siffror). Tredje siffran maste vara >= 2 for att skilja fran personnummer. Luhn-validering pa alla 10 siffror.

## Telefonformat som stods

| Format                 | Exempel            | Typ     |
|------------------------|--------------------|---------|
| `+46 XX XXX XX XX`     | +46 70 123 45 67   | Mobil   |
| `07X-XXX XX XX`        | 070-123 45 67      | Mobil   |
| `0XX-XXX XX XX`        | 031-123 45 67      | Fast    |

Mellanslag och bindestreck ar valfria.

## API-anvandning

### Analysera text

```bash
curl -X POST http://localhost:8080/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Erik Johansson har personnummer 19900101-1234 och telefon 070-123 45 67",
    "language": "sv"
  }'
```

### Anonymisera text

```bash
curl -X POST http://localhost:8080/api/anonymize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Erik Johansson har personnummer 19900101-1234 och telefon 070-123 45 67",
    "language": "sv"
  }'
```

Forvantad output:
```
[PERSON] har personnummer [PERSONNUMMER] och telefon [TELEFON]
```

## Konfigurationsfiler

| Fil                           | Syfte                                    |
|-------------------------------|------------------------------------------|
| `backend/presidio_service.py` | Huvudtjanst med NLP-motor och operatorer |
| `backend/swedish_recognizers.py` | Svenska custom recognizers            |
| `Dockerfile`                  | Installerar spaCy-modeller               |

## Framtida forbattringsmojligheter

- Stod for svenska bankkortsnummer
- Forbattrad adressigenkanning for svenska gatuadresser
- Stod for svenska registeringsnummer (fordon)
- Integration med Skatteverkets API for personnummer-validering
- Stod for fler nordiska sprak (norska, danska, finska)
