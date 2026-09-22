# -*- coding: utf-8 -*-
"""
Innehållet i testanbudet — EN källa för alla tre filformaten.

Skälet att hålla texten här och inte i tre generatorer: facit räknar förekomster,
och DOCX, PDF och TXT måste innehålla exakt samma uppgifter. Driver de isär blir
facit fel för minst ett format, och då är hela testmaterialet opålitligt.

Alla person- och organisationsnummer är KONSTRUERADE och bryter medvetet mot
Luhn-kontrollen (verifieras i generera_anbud.py). De kan därför aldrig ha
utfärdats till en verklig person eller ett verkligt företag — men mönstret är
korrekt, så regexlagret känner igen dem ändå. Baslinjen Luhn-kontrollerar inte.
"""

TITEL = "Anbud – Ramavtal byggservice och mindre entreprenader"

# Blocktyper: h1, h2, p, li, table (rubrikrad först), note
BLOCK = [
 ("h1", "ANBUD – Ramavtal byggservice och mindre entreprenader"),

 # ---------------------------------------------------------------------------
 # De första ~1000 tecknen är det ENDA textprov optimizerns språkmodell får se
 # (text[:1000] i backend/main.py). Därför ligger den tätaste och svåraste
 # samlingen uppgifter först, i stället för en gles försättssida.
 # ---------------------------------------------------------------------------
 ("p", "Upphandlande myndighet: Nyköpings kommun, org.nr 212000-2941, "
       "upphandling@nykoping.se, växel 0155-24 80 00."),
 ("p", "Diarienummer KS 2026/00873. Upphandlings-ID UH-2026-142. "
       "Annonserad enligt lagen (2016:1145) om offentlig upphandling."),
 ("p", "Anbudsgivare: Sandbäcken Bygg & Entreprenad AB, org.nr 556914-2288, "
       "Verkstadsgatan 14, 611 32 Nyköping. Momsreg.nr SE556914228801. "
       "Bankgiro 5051-6142. Peppol-ID 0007:5569142288, GLN 7365569142288."),
 ("p", "Kontaktperson för anbudet: Marcus Hedlund, "
       "marcus.hedlund@sandbackenbygg.se, direkt 0155-21 44 90, "
       "mobil 070-918 44 21. Anbud kan även skickas till anbud@sandbackenbygg.se."),
 ("p", "Behörig företrädare: Ingrid Berg, personnummer 19710322-4588, "
       "ingrid.berg@sandbackenbygg.se."),
 ("p", "Anbudet lämnades 2026-05-14 via e-Avrop, referens EA-2026-4471. "
       "Anbudets giltighetstid är 90 dagar från sista anbudsdag 2026-05-15."),

 ("h2", "1. Anbudsgivarens uppgifter"),
 ("table", [
    ["Uppgift", "Värde"],
    ["Firma", "Sandbäcken Bygg & Entreprenad AB"],
    ["Organisationsnummer", "556914-2288"],
    ["Säte", "Nyköping"],
    ["Besöksadress", "Verkstadsgatan 14, 611 32 Nyköping"],
    ["Postadress", "Box 1142, 611 25 Nyköping"],
    ["Depå", "Kabelvägen 3, 222 36 Lund"],
    ["Telefon växel", "0155-24 11 00, anknytning 4471"],
    ["Fakturaadress", "Sandbäcken Bygg & Entreprenad AB, FE 4471, 831 90 Östersund"],
    ["Referensnummer faktura", "Art. 743 21"],
    ["Plusgiro", "482345-6"],
    ["Kontonummer", "8327-9, 143 267 891-2"],
    ["F-skatt", "Godkänd för F-skatt sedan 2009-03-01"],
    ["Antal anställda", "34"],
    ["Kollektivavtal", "Byggavtalet 2025–2028"],
 ]),

 ("h2", "2. Anbudets omfattning"),
 ("p", "Anbudet omfattar byggservice och mindre entreprenader upp till ett "
       "kontraktsvärde om 2 000 000 kronor per avrop inom Nyköpings kommun, "
       "Oxelösunds kommun och Trosa kommun. Ramavtalets takvolym är "
       "12 500 000 kronor per år."),
 ("p", "Arbeten utförs från vår depå i Lund samt från huvudkontoret i Nyköping. "
       "Utrustning finns registrerad på fastigheten Sandbäcken 3:12 och på "
       "Väster 1:44."),
 ("p", "Servicebilar: reg.nr YHL 421, reg.nr XKD 883 och reg.nr RTP 194."),

 ("h2", "3. Behörig företrädare och underskrift"),
 ("p", "Anbudet undertecknas av Ingrid Berg, verkställande direktör, i egenskap "
       "av behörig firmatecknare enligt registreringsbevis daterat 2026-01-12. "
       "Underskrift har skett med e-legitimation, referens "
       "BID-2026-0514-77219, utfärdad på personnummer 19710322-4588."),
 ("p", "Ingrid Berg nås på ingrid.berg@sandbackenbygg.se och 070-441 20 17. "
       "Vid förhinder företräds bolaget av Marcus Hedlund enligt fullmakt."),

 ("h2", "4. Nyckelpersoner"),
 ("p", "Följande personer avses utföra uppdraget. Fullständiga meritförteckningar "
       "bifogas som bilaga 3."),
 ("table", [
    ["Namn", "Roll", "Personnummer", "ID06", "Kontakt"],
    ["Björn Lund", "Platschef", "19850914-3372",
     "ID06-2019-448 219", "bjorn.lund@sandbackenbygg.se"],
    ["Aisha Karlsson", "Arbetsledare", "19930227-6615",
     "ID06-2021-551 077", "aisha.karlsson@sandbackenbygg.se"],
    ["Tomas Wikander", "KMA-ansvarig", "19660708-1120",
     "ID06-2017-330 462", "tomas.wikander@sandbackenbygg.se"],
    ["Nadia Fahlgren", "Kalkylator", "20010119-8845",
     "ID06-2023-702 118", "nadia.fahlgren@sandbackenbygg.se"],
 ]),
 # E-post sist på raden följd av versalt ord — den kända fällan i
 # email_with_linebreak, som svalde ordet efter meningsslutet.
 ("p", "Platschefen kan vid frågor om utförandet nås direkt på "
       "bjorn.lund@sandbackenbygg.se.\nSandbäcken Bygg tillämpar rotation av "
       "arbetsledare mellan objekten."),
 ("p", "Björn Lund har yrkesbevis nr 44-118-2007 och heta arbeten-certifikat "
       "giltigt till 2027-04-30. Aisha Karlsson innehar behörighet BAS-U och "
       "BAS-P sedan 2022."),
 ("p", "Vår tidigare platschef är sjukskriven sedan mars 2026 och ersätts av "
       "Björn Lund under hela avtalsperioden."),
 ("p", "Arbetsledaren som ledde Sörmlands enda passivhusprojekt i trä 2024 "
       "ingår i teamet och ansvarar för de energitekniska momenten."),
 ("p", "Anhörig vid nödläge för platschefen: Sofia Hedlund, 070-441 20 18, "
       "sofia.hedlund@telia.com."),

 ("h2", "5. Underleverantörer"),
 ("p", "Följande underleverantörer avses anlitas. Samtliga har kontrollerats "
       "mot Skatteverket avseende skatter och avgifter."),
 ("table", [
    ["Företag", "Organisationsnummer", "Åtagande", "Kontaktperson"],
    ["Karin Ohlssons Måleri AB", "556482-7711", "Måleri", "Jonas Ek, 0155-19 22 41"],
    ["Andersson & Lindqvist Entreprenad AB", "559102-4463", "Mark och grund",
     "Petra Lindqvist, petra@al-entreprenad.se"],
    ["Snickeri Erik Sandell", "19790412-3217", "Inredningssnickeri",
     "Erik Sandell, 073-284 91 05"],
    ["El & Kraft i Sörmland AB", "556731-9902", "Elinstallation",
     "Servicedesk, 0155-33 00 10"],
 ]),
 ("note", "Snickeri Erik Sandell är en enskild firma. Organisationsnumret är "
          "därmed innehavarens personnummer och är en personuppgift, till "
          "skillnad från aktiebolagens organisationsnummer."),

 ("h2", "6. Referensuppdrag"),
 ("p", "Tre referensuppdrag redovisas enligt upphandlingsdokumentets punkt 4.3. "
       "Angivna referenspersoner är kontaktade och har lämnat samtycke till att "
       "vidimera uppgifterna."),
 ("table", [
    ["Uppdrag", "Beställare", "Referensperson", "Kontakt", "År"],
    ["Ombyggnad Nyhemsskolan", "Katrineholms kommun", "Petra Nyström, fastighetschef",
     "petra.nystrom@katrineholm.se, 0150-570 12", "2024"],
    ["Ventilationsbyte vårdcentral", "Region Sörmland", "Hans-Olof Ek, projektledare",
     "hans-olof.ek@regionsormland.se, 0155-24 51 88", "2025"],
    ["Ramavtal fastighetsservice", "Trosa kommun", "Lena Åkerblom, förvaltningschef",
     "lena.akerblom@trosa.se, 0156-520 41", "2023–2025"],
 ]),
 ("p", "Referensuppdraget i Katrineholm genomfördes tillsammans med "
       "Andersson & Lindqvist Entreprenad AB. Beställarens dåvarande "
       "enhetschef Anna Wiik kan lämna kompletterande upplysningar."),

 ("h2", "7. Priser"),
 ("p", "Priserna är fasta till och med 2027-12-31 och anges exklusive "
       "mervärdesskatt."),
 ("table", [
    ["Yrkeskategori", "Timarvode", "Övertid enkel", "Övertid kvalificerad"],
    ["Snickare", "685 kr", "1 028 kr", "1 370 kr"],
    ["Elektriker", "745 kr", "1 118 kr", "1 490 kr"],
    ["Målare", "640 kr", "960 kr", "1 280 kr"],
    ["Arbetsledare", "895 kr", "1 343 kr", "1 790 kr"],
    ["Platschef", "1 185 kr", "–", "–"],
 ]),
 ("p", "Påslag på material 8 procent. Framkörningsavgift 450 kr per objekt inom "
       "zon 1. Utanför zon 1 tillämpas kilometerersättning enligt "
       "Skatteverkets schablon."),

 ("h2", "8. Kvalitet, miljö och arbetsmiljö"),
 ("p", "Bolaget är certifierat enligt ISO 9001:2015, ISO 14001:2015 och "
       "ISO 45001:2018. Certifikatnummer 1653-QMS-2019, 1653-EMS-2019 och "
       "1653-OHS-2021, utfärdade av ackrediterat certifieringsorgan."),
 ("p", "KMA-ansvarig Tomas Wikander ansvarar för egenkontroll och för att "
       "avvikelser rapporteras enligt rutin R-04. Arbetsmiljöansvaret enligt "
       "arbetsmiljölagen (1977:1160) kap. 3 vilar på platschefen."),
 ("p", "Ansvarsförsäkring hos Länsförsäkringar, försäkringsnummer F-4471 2208, "
       "med försäkringsbelopp 10 000 000 kronor."),

 ("h2", "9. Sanningsförsäkran"),
 ("p", "Sandbäcken Bygg & Entreprenad AB försäkrar att bolaget inte omfattas av "
       "någon uteslutningsgrund enligt 13 kap. lagen (2016:1145) om offentlig "
       "upphandling, att skatter och socialförsäkringsavgifter är betalda, och "
       "att lämnade uppgifter är riktiga."),
 ("p", "Nyköping den 14 maj 2026"),
 ("p", "Ingrid Berg, verkställande direktör, personnummer 19710322-4588"),

 ("h2", "10. Begäran om sekretess"),
 ("p", "Anbudsgivaren begär med stöd av 31 kap. 16 § offentlighets- och "
       "sekretesslagen (2009:400) att uppgifterna i avsnitt 7 om timarvoden och "
       "påslag samt metodbeskrivningen i bilaga 5 ska omfattas av sekretess. "
       "Ett röjande skulle enligt anbudsgivaren medföra skada, eftersom "
       "kalkylunderlaget kan användas av konkurrenter vid kommande "
       "upphandlingar."),
 ("p", "Anbudsgivaren är införstådd med att den upphandlande myndigheten gör en "
       "självständig skadeprövning och att uppgifterna omfattas av absolut "
       "sekretess enligt 19 kap. 3 § andra stycket samma lag fram till dess att "
       "tilldelningsbeslut fattats."),
 ("p", "Frågor om sekretessbegäran besvaras av Marcus Hedlund, 070-918 44 21."),

 ("h2", "11. Bilageförteckning"),
 ("li", "Bilaga 1 – Registreringsbevis Bolagsverket, daterat 2026-01-12"),
 ("li", "Bilaga 2 – Årsredovisning 2025"),
 ("li", "Bilaga 3 – Meritförteckningar för nyckelpersoner"),
 ("li", "Bilaga 4 – Certifikat ISO 9001, 14001 och 45001"),
 ("li", "Bilaga 5 – Metodbeskrivning (sekretess begärd)"),
 ("li", "Bilaga 6 – Försäkringsbrev, försäkringsnummer F-4471 2208"),
]
