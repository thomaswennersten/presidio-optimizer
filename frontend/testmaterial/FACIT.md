# Testanbud för utlämnande — facit och arbetsgång

Filer: `anbud-utlamnande.docx`, `.pdf`, `.txt` — samma innehåll, byggt ur en källa.
Källa: `anbud_innehall.py`. Generator: `generera_anbud.py`.

Materialet är helt påhittat. Företag, personer och referensuppdrag finns inte.
Kommunnamnen är verkliga, men de är juridiska personer och inga personuppgifter.

🔴 **Alla person- och organisationsnummer bryter mot Luhn-kontrollen.** De kan
därför aldrig ha utfärdats till någon verklig, men mönstret är korrekt så
regexlagret känner igen dem ändå (baslinjen Luhn-kontrollerar inte). Generatorn
vägrar skriva filerna om något nummer råkar bli giltigt — den kontrollen fångade
två nummer när materialet togs fram.

### De tre formaten skiljer sig — med flit

Innehållet är detsamma, men textutvinningen ger inte samma sträng. Mätt med
dagens kedja, enbart mönsterlagret:

| Format | Träffar | Skillnad |
|---|---:|---|
| TXT | 56 | referens |
| DOCX | 56 | identisk med TXT |
| PDF | 55 | tre träffar skiljer |

I PDF:en bryts `0155-24 80 00` mellan `80` och `00` och försvinner därmed helt,
`570 12` blir `570\n12`, och `anbud@sandbackenbygg.se.` följt av radbrytning
sväljer ordet efter.

**Det är inte ett fel i materialet utan poängen med PDF-versionen.** Så beter sig
verklig PDF-textutvinning, och det är precis den situation där en personuppgift
som bryts över radslut kan gå omaskerad utan felmeddelande. Kör alla tre
formaten genom maskera och jämför — skiljer sig utfallet mer än så här finns ett
problem i radbrytningshanteringen.

---

## Varför anbud är ett eget fall

Ett anbud som lämnas ut efter tilldelningsbeslut skiljer sig från de flesta
handlingar på en punkt som avgör hela regelverket:

**Anbudsgivarens identitet ska framgå, inte maskeras.** Firmanamn,
organisationsnummer, säte och de uppgifter som visar vem som lämnat vilket bud
är själva poängen med utlämnandet. Ett anbud där parten är `<ORGANISATION>` har
förlorat sin funktion, och den som begär ut det kan inte kontrollera
tilldelningen.

**Det som ska bort är fysiska personer.** Kontaktpersoner, nyckelpersonernas
personnummer och merituppgifter, referenspersoner hos *andra* organisationer,
och anhöriguppgifter som råkat följa med i en bilaga.

**Priser är inte personuppgifter.** Timarvoden och påslag kan omfattas av
sekretess enligt 31 kap. 16 § OSL, men det är en skadeprövning som en människa
gör — inte något maskeringen ska sköta. Dokumentet innehåller därför en
sekretessbegäran från anbudsgivaren i avsnitt 10, som påminner om att den
prövningen är ett eget steg.

| Ska maskeras | Ska INTE maskeras |
|---|---|
| Personnummer, även när det står som organisationsnummer för enskild firma | Aktiebolagens organisationsnummer |
| Namn på kontaktpersoner och nyckelpersoner | Anbudsgivarens och myndighetens firmanamn |
| Personliga e-postadresser och mobilnummer | Funktionsbrevlådor (`anbud@`, `upphandling@`) och växelnummer |
| Referenspersoner hos beställare (tredje part) | Beställarnas organisationsnamn |
| Anhöriguppgifter | Diarienummer och upphandlings-ID |
| ID06-nummer, yrkesbevis, e-legitimationsreferens | Certifikatnummer för bolaget, ISO-standarder |
| | Priser (egen prövning enligt 31 kap. 16 §) |

---

## Inventering

Räknad ur källan, inte uppskattad.

| Antal | Uppgift |
|---:|---|
| 14 | unika personer, i 25 förekomster |
| 8 | personnummer — varav **ett** står som organisationsnummer (enskild firma) |
| 6 | organisationsnummer för juridiska personer |
| 15 | e-postadresser — varav 2 funktionsbrevlådor som **inte** ska maskeras |
| 11 | telefonnummer — växel, direkt, mobil och ett med anknytning |
| 5 | äkta postnummer |
| 2 | GLN/Peppol-identifierare |
| 3 | diarie- och upphandlingsnummer |
| 4 | ID06-nummer |
| 3 | certifikatnummer |
| 3 | fordonsregistreringsnummer |
| 3 | ISO-standarder och 7 lagrumshänvisningar som **inte** är personuppgifter |

Tredje part: fyra personer som inte är parter i upphandlingen — tre
referenspersoner hos Katrineholms kommun, Region Sörmland och Trosa kommun, samt
en tidigare enhetschef som nämns i förbigående.

Anhörig: `Sofia Hedlund, 070-441 20 18` i avsnitt 4. Den sortens uppgift följer
med bilagor om nödlägesrutiner oftare än man tror.

Mosaik: *"Arbetsledaren som ledde Sörmlands enda passivhusprojekt i trä 2024"*
och *"Vår tidigare platschef är sjukskriven sedan mars 2026"*. Ingen av dem
innehåller ett namn. Maskeringen kan inte ta bort dem — det är
granskningslagrets uppgift att flagga och en människas att avgöra.

Dokumentegenskaperna är medvetet ifyllda (`dc:creator = Ingrid Berg`,
`lastModifiedBy = Marcus Hedlund`, PDF-nyckelord med namn) så att materialet
också visar att metadatarensningen fungerar.

---

## Falska vänner — det materialet är byggt för

Det här är vad sessionen i optimizern egentligen ska producera. Mätt utfall med
dagens kedja (regelverk `Avtal6 v7`, enbart mönsterlagret):

### Falska positiva som redan uppstår

| Träff | Kommer från | Varför fel |
|---|---|---|
| `POSTNUMMER 00873` | diarienumret `KS 2026/00873` | diarienummer är inte personuppgifter |
| `POSTNUMMER 743 21` | artikelnumret `Art. 743 21` | ren sifferkollision |
| `POSTNUMMER 77219` | e-legitimationsreferens `BID-2026-0514-77219` | delsträng ur en längre identifierare |
| `POSTNUMMER 14001`, `45001` | `ISO 14001:2015`, `ISO 45001:2018` | standardnummer, träffar två gånger vardera |
| `POSTNUMMER 570 12`, `520 41` | slutet av telefonnumren `0150-570 12`, `0156-520 41` | två mönster slåss om samma siffror |
| `ORGANISATIONSNUMMER 212000-2941` | Nyköpings kommun | myndigheten ska framgå |
| `EPOST …se.\nSandb` | `bjorn.lund@sandbackenbygg.se.` följt av radbrytning | översvämning, se fällan nedan |

Telefonmönstret klipper dessutom av flera nummer: `0155-24 80` i stället för
`0155-24 80 00`. Svenska fasta nummer med grupperingen 0155-24 80 00 fångas bara
delvis av baslinjen.

### Falska negativa — inget mönster finns

Diarienummer (`KS 2026/00873`, `UH-2026-142`, `EA-2026-4471`), ID06-nummer,
bankgiro `5051-6142`, plusgiro `482345-6`, kontonummer, momsregistreringsnummer
`SE556914228801`, certifikatnummer `1653-QMS-2019`, försäkringsnummer
`F-4471 2208`, yrkesbevis `44-118-2007`, fordonens registreringsnummer,
fastighetsbeteckningarna `Sandbäcken 3:12` och `Väster 1:44`, anknytning `4471`.

Flera av dem **ska inte maskeras** vid ett utlämnande — men de ska kännas igen,
annars går de inte att välja bort medvetet.

### Beteckningar som inte är personidentifierare

`Byggavtalet 2025–2028` (kollektivavtal), `ISO 9001:2015`,
`lagen (2016:1145) om offentlig upphandling`, `19 kap. 3 § OSL`, ramavtalsnamn
och blankettbeteckningar identifierar en **handling eller ett regelverk**, inte
en människa. De ska stå kvar.

`OVRIGT` tog tidigare `Byggavtalet` — beskrivningen sa "enskilda identifierare"
utan att kräva att de pekar ut en *person*. Rättat 2026-08-25; verifierat över
sex körningar med noll falska positiva på de här sju beteckningarna.

**Diarie- och ärendenummer** (`KS 2026/00873`, `SN 2026/00412`) räknas också som
handlingsbeteckningar och maskeras inte. Vid utlämnande är diarienumret dessutom
det som gör handlingen möjlig att hänvisa till. En förvaltning som ändå vill
maskera sina egna ärendeserier lägger in dem i sitt **regelverk** — det är vad
gruppen Verksamhetsspecifikt finns för.

### Namn som inte är personer

`Karin Ohlssons Måleri AB` och `Andersson & Lindqvist Entreprenad AB` är företag.
`Snickeri Erik Sandell` är en enskild firma — där **är** namnet en personuppgift,
och organisationsnumret är innehavarens personnummer.

`Lund` förekommer både som efternamn (`Björn Lund`, platschef) och som ort
(`vår depå i Lund`, `Kabelvägen 3, 222 36 Lund`). `Berg` likaså. Samma sträng,
olika skyddsvärde — det går inte att lösa med en denylista, bara med sammanhang.

---

## 🔴 Fällan som materialet avslöjade

`\b` betyder **inte samma sak** i Python och JavaScript:

```
mönster: ...\.(?:[ \t]*\r?\n[ \t]*)?[A-Za-z]{2,6}\b
text:    bjorn.lund@sandbackenbygg.se.\nSandbäcken Bygg

Python (Presidio, optimizern):  träff = "bjorn.lund@sandbackenbygg.se"   rätt
JavaScript (maskeringskedjan):  träff = "…se.\nSandb"                    fel
```

Python räknar `ä` som ordtecken, så `\b` efter `Sandb` finns inte och mönstret
backar. JavaScript räknar bara ASCII som ordtecken — även med `u`-flaggan — så
`\b` gäller, och `.\nSandb` sväljs med.

**Följden: ett mönster kan se korrekt ut i optimizern och ändå svälja text i
maskeringen.** Det syns som att ord försvinner ur den maskerade handlingen.

Undvik `\b` vid svenska ordgränser i regelverk. Skriv i stället en
negativ blicksökning som räknar med å, ä och ö:

```
[A-Za-zÅÄÖåäö]{2,6}(?![A-Za-zÅÄÖåäö])
```

Detta gäller **alla** regelverk optimizern producerar, inte bara det här.

---

## Arbetsgång i optimizern

### Innan du börjar: två saker om verktyget

**Bara de första 1000 tecknen når språkmodellen som textprov**
(`text_sample=text[:1000]` i optimizerns `main.py`). Resten av dokumentet når
den bara genom de träffar du markerar, med 80 tecken kontext åt vardera hållet.
Därför ligger den tätaste samlingen uppgifter först i det här dokumentet — inte
på en gles försättssida.

**Optimizern kör riktiga Presidio, maskeringen gör inte det.** Ur sessionen
följer bara `custom_recognizers`, `exclusions` och `entity_settings` med till
regelverket. Presidios NER för namn och platser är engelsk och fungerar dåligt
på svenska — i kedjan görs det jobbet av språkmodellslagret i stället. **Lägg
alltså inte sessionen på att tvinga Presidio att hitta svenska namn.** Det är
bortkastad tid, och resultatet följer ändå inte med.

### Så gör du

1. Ladda upp `anbud-utlamnande.docx`. Namnge sessionen, t.ex. `anbud-utlamnande`.
2. Kör analys. Jämför mot listan över falska positiva ovan.
3. Markera **falska positiva** i tur och ordning: ISO-numren, artikelnumret,
   diarienumret, kommunens organisationsnummer, telefonsvansarna.
4. Markera **falska negativa** för de mönster som ska kunna kännas igen:
   diarienummer, ID06, bankgiro, plusgiro, momsregistreringsnummer,
   certifikatnummer, försäkringsnummer.
5. Optimera. Kontrollera de mönster som föreslås — särskilt om något innehåller
   `\b` nära svensk text.
6. Upprepa tills utfallet stämmer. Två till tre varv brukar räcka.
7. **Publicera till maskera.** Regelverket dyker upp i väljaren direkt, ingen
   omstart behövs.
8. Skapa en dokumenttyp i maskeras adminvy med det nya regelverket, döpt till
   något i stil med *Utlämnande av anbud*, med organisationsnamn bortvalt.

### Kontrollera i maskera efteråt

Ladda upp samma fil i maskera med det nya regelverket och kontrollera att:

- de fjorton personerna maskeras, men företagsnamnen står kvar,
- `19790412-3217` maskeras som personnummer trots att det står som
  organisationsnummer,
- funktionsbrevlådorna `anbud@` och `upphandling@` står kvar,
- ISO-numren och artikelnumret **inte** är maskerade,
- inget ord har svalts efter en e-postadress,
- granskningslagret flaggar mosaikformuleringarna och tredjepartsuppgifterna,
- dokumentegenskaperna är rensade i den nedladdade filen.
