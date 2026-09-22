# -*- coding: utf-8 -*-
"""
Skapar testanbudet i DOCX, PDF och TXT ur anbud_innehall.py.

Körs i maskeras bakändescontainer, som har python-docx och PyMuPDF:

    docker exec -i pii-mask-dokument-backend-1 python /app/data/gen/generera_anbud.py

Skriptet VÄGRAR skriva filer om något person- eller organisationsnummer råkar
vara giltigt enligt Luhn. Testmaterial får aldrig innehålla en identifierare som
kan ha utfärdats till en verklig person — men mönstret måste vara korrekt, annars
tränas regelverket på fel sak. Baslinjen Luhn-kontrollerar inte, så ogiltiga
nummer upptäcks ändå.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anbud_innehall import BLOCK, TITEL          # noqa: E402


def luhn_ok(siffror: str) -> bool:
    # Kontrollsiffran är den sista och ska INTE dubblas. Dubbling börjar på
    # näst sista siffran. Ett fel här gör att kontrollen underkänner allt och
    # ser ut att fungera — den släpper då igenom giltiga nummer utan att märka det.
    summa, dubbla = 0, False
    for tecken in reversed(siffror):
        n = int(tecken)
        if dubbla:
            n *= 2
            if n > 9:
                n -= 9
        summa += n
        dubbla = not dubbla
    return summa % 10 == 0


def _sjalvtest():
    """Kontrollen måste känna igen GILTIGA nummer, annars godkänner den allt."""
    for nummer, vantat in (("8112189876", True), ("8112189875", False),
                           ("5560360793", True), ("5567891234", False)):
        if luhn_ok(nummer) is not vantat:
            raise SystemExit(f"AVBRYTER: luhn_ok() är trasig — {nummer} gav "
                             f"{luhn_ok(nummer)}, väntat {vantat}.")


def all_text() -> str:
    delar = []
    for typ, innehall in BLOCK:
        if typ == "table":
            for rad in innehall:
                delar.append("\t".join(rad))
        else:
            delar.append(innehall)
    return "\n".join(delar)


def kontrollera_nummer(text: str):
    """Varje nummer i personnummer- eller organisationsnummerform måste vara ogiltigt."""
    giltiga = []
    for m in re.finditer(r"\b(?:19|20)?(\d{6})[-+](\d{4})\b", text):
        siffror = m.group(1) + m.group(2)
        if luhn_ok(siffror):
            giltiga.append(m.group(0))
    _sjalvtest()
    if giltiga:
        raise SystemExit(
            "AVBRYTER: följande nummer är giltiga enligt Luhn och kan därför ha "
            "utfärdats på riktigt. Ändra dem innan filerna skapas:\n  "
            + "\n  ".join(sorted(set(giltiga)))
        )
    antal = len(re.findall(r"\b(?:19|20)?\d{6}[-+]\d{4}\b", text))
    print(f"  {antal} nummer i personnummer-/orgnr-form, samtliga ogiltiga enligt Luhn")


# --- TXT ---------------------------------------------------------------------

def skriv_txt(sokvag: str):
    rader = []
    for typ, innehall in BLOCK:
        if typ == "h1":
            rader += [innehall, "=" * len(innehall), ""]
        elif typ == "h2":
            rader += ["", innehall, "-" * len(innehall), ""]
        elif typ in ("p", "note"):
            rader += [innehall, ""]
        elif typ == "li":
            rader += ["  - " + innehall]
        elif typ == "table":
            bredder = [max(len(r[i]) for r in innehall) for i in range(len(innehall[0]))]
            for i, rad in enumerate(innehall):
                rader.append("  " + "  ".join(c.ljust(bredder[j]) for j, c in enumerate(rad)).rstrip())
                if i == 0:
                    rader.append("  " + "  ".join("-" * b for b in bredder))
            rader.append("")
    with open(sokvag, "w", encoding="utf-8") as f:
        f.write("\n".join(rader).rstrip() + "\n")


# --- DOCX --------------------------------------------------------------------

def skriv_docx(sokvag: str):
    from docx import Document
    from docx.shared import Pt

    d = Document()
    d.core_properties.title = TITEL
    # Dokumentegenskaperna lämnas medvetet ifyllda: en maskerad Word-fil bar
    # tidigare den registrerades namn i dc:creator medan brödtexten var perfekt
    # maskerad. Materialet ska kunna visa att metadatarensningen fungerar.
    d.core_properties.author = "Ingrid Berg"
    d.core_properties.last_modified_by = "Marcus Hedlund"
    d.core_properties.comments = "Anbud sammanställt av Nadia Fahlgren"

    for typ, innehall in BLOCK:
        if typ == "h1":
            d.add_heading(innehall, level=1)
        elif typ == "h2":
            d.add_heading(innehall, level=2)
        elif typ == "p":
            for i, stycke in enumerate(innehall.split("\n")):
                d.add_paragraph(stycke)
        elif typ == "note":
            p = d.add_paragraph()
            r = p.add_run(innehall)
            r.italic = True
        elif typ == "li":
            d.add_paragraph(innehall, style="List Bullet")
        elif typ == "table":
            t = d.add_table(rows=len(innehall), cols=len(innehall[0]))
            t.style = "Table Grid"
            for i, rad in enumerate(innehall):
                for j, cell in enumerate(rad):
                    ruta = t.cell(i, j)
                    ruta.text = cell
                    if i == 0:
                        for p in ruta.paragraphs:
                            for r in p.runs:
                                r.bold = True
                                r.font.size = Pt(10)
            d.add_paragraph()
    d.save(sokvag)


# --- PDF ---------------------------------------------------------------------

def skriv_pdf(sokvag: str):
    import fitz

    BREDD, HOJD, MARG = 595, 842, 56
    doc = fitz.open()
    sida = doc.new_page(width=BREDD, height=HOJD)
    y = MARG

    def ny_sida_vid_behov(behov):
        nonlocal sida, y
        if y + behov > HOJD - MARG:
            sida = doc.new_page(width=BREDD, height=HOJD)
            y = MARG

    def skriv(text, storlek=10, fet=False, indrag=0):
        nonlocal y
        font = "hebo" if fet else "helv"
        maxbredd = BREDD - 2 * MARG - indrag
        ord_ = text.split()
        rad = ""
        rader = []
        for o in ord_:
            forslag = (rad + " " + o).strip()
            if fitz.get_text_length(forslag, fontname=font, fontsize=storlek) > maxbredd:
                rader.append(rad)
                rad = o
            else:
                rad = forslag
        rader.append(rad)
        for r in rader:
            ny_sida_vid_behov(storlek + 4)
            sida.insert_text((MARG + indrag, y + storlek), r, fontname=font, fontsize=storlek)
            y += storlek + 4

    for typ, innehall in BLOCK:
        if typ == "h1":
            ny_sida_vid_behov(40)
            y += 6
            skriv(innehall, 16, True)
            y += 8
        elif typ == "h2":
            ny_sida_vid_behov(34)
            y += 12
            skriv(innehall, 12.5, True)
            y += 4
        elif typ in ("p", "note"):
            for stycke in innehall.split("\n"):
                skriv(stycke, 10, False)
            y += 6
        elif typ == "li":
            skriv("• " + innehall, 10, False, indrag=12)
        elif typ == "table":
            kolumner = len(innehall[0])
            STORLEK = 8.5

            # Kolumnbredd efter innehåll, inte lika delar. Med lika breda
            # kolumner hamnade e-postadresserna i en smal spalt och bröts mitt
            # itu, varpå mönsterlagret bara hittade 8 av 15 i PDF:en medan
            # DOCX och TXT hade alla. Samma uppgifter måste finnas i alla tre
            # formaten, annars gäller facit bara för några av dem.
            langder = [max(fitz.get_text_length(rad[j], fontname="helv", fontsize=STORLEK)
                           for rad in innehall) for j in range(kolumner)]
            tillgangligt = BREDD - 2 * MARG
            summa = sum(langder) or 1
            bredder = [max(46.0, tillgangligt * l / summa) for l in langder]
            # Skala ned om minimibredderna tillsammans spränger sidan.
            if sum(bredder) > tillgangligt:
                bredder = [b * tillgangligt / sum(bredder) for b in bredder]
            x_start = [MARG + sum(bredder[:j]) for j in range(kolumner)]

            def bryt(cell, font, kolbredd):
                """Radbryt inuti cellen.

                Första versionen TRUNKERADE i stället, för att slippa skriva
                över nästa kolumn. Det gjorde att 8 av 15 e-postadresser föll
                bort ur PDF:en medan DOCX och TXT hade kvar dem — facit hade
                då gällt två av tre format. Tyst bortfall i testmaterial är
                värre än ful layout.
                """
                rader, rad = [], ""
                for ord_ in cell.split(" "):
                    forslag = (rad + " " + ord_).strip()
                    if (fitz.get_text_length(forslag, fontname=font, fontsize=STORLEK)
                            > kolbredd - 8 and rad):
                        rader.append(rad)
                        rad = ord_
                    else:
                        rad = forslag
                    # Ett enda långt ord (e-postadress) måste brytas hårt,
                    # annars går det ut i marginalen.
                    while fitz.get_text_length(rad, fontname=font, fontsize=STORLEK) > kolbredd - 8:
                        kvar = rad
                        while (fitz.get_text_length(kvar, fontname=font, fontsize=STORLEK)
                               > kolbredd - 8 and len(kvar) > 1):
                            kvar = kvar[:-1]
                        rader.append(kvar)
                        rad = rad[len(kvar):]
                rader.append(rad)
                return [r for r in rader if r]

            for i, rad in enumerate(innehall):
                font = "hebo" if i == 0 else "helv"
                celler = [bryt(c, font, bredder[j]) for j, c in enumerate(rad)]
                hojd = max(len(c) for c in celler) * (STORLEK + 2.5) + 4
                ny_sida_vid_behov(hojd)
                for j, cellrader in enumerate(celler):
                    for k, r in enumerate(cellrader):
                        sida.insert_text((x_start[j],
                                          y + 9 + k * (STORLEK + 2.5)),
                                         r, fontname=font, fontsize=STORLEK)
                y += hojd
            y += 8

    doc.set_metadata({"title": TITEL, "author": "Ingrid Berg",
                      "keywords": "anbud, Sandbäcken Bygg, Marcus Hedlund",
                      "subject": "Anbud UH-2026-142"})
    doc.save(sokvag, garbage=4, clean=True)
    doc.close()


if __name__ == "__main__":
    ut = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(ut, exist_ok=True)
    text = all_text()
    print("Kontrollerar identifierare…")
    kontrollera_nummer(text)
    skriv_txt(os.path.join(ut, "anbud-utlamnande.txt"))
    skriv_docx(os.path.join(ut, "anbud-utlamnande.docx"))
    skriv_pdf(os.path.join(ut, "anbud-utlamnande.pdf"))
    print(f"Klart. Textprovet optimizern ser (första 1000 tecknen) slutar med:\n"
          f"  …{text[900:1000]!r}")
    for namn in ("txt", "docx", "pdf"):
        f = os.path.join(ut, f"anbud-utlamnande.{namn}")
        print(f"  {os.path.basename(f):28s} {os.path.getsize(f):>8d} byte")
