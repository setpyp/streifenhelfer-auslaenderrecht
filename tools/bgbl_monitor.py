#!/usr/bin/env python3
"""
Frühwarnung aus dem Bundesgesetzblatt (recht.bund.de): prüft neue Ausgaben von Teil I im Volltext
darauf, ob sie Gesetze aus daten/gesetze.json ändern, neu fassen oder aufheben. Titel allein reichen
nicht, weil Mantelgesetze weitere Gesetze mitändern. Das BGBl ist die amtliche Quelle für Änderungen
und Inkrafttreten; den Wortlaut liefert weiterhin die konsolidierte Fassung (build_rechtsdaten.py).

Aufruf:  python tools/bgbl_monitor.py [--tage 8] [--bericht BERICHT.md]
         python tools/bgbl_monitor.py --jahr 2026 --von 200 --bis 327     (Nachprüfung eines Bereichs)
Benötigt pdftotext (poppler-utils).
Exit-Code: 0 = keine Treffer, 10 = Treffer, 3 = BGBl nicht erreichbar
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RSS = "https://www.recht.bund.de/rss/feeds/rss_bgbl-1.xml"
UA = {"User-Agent": "Streifenhelfer-Frühwarnung/1.0"}
MONATE = "Januar Februar März April Mai Juni Juli August September Oktober November Dezember".split()


def get(url, timeout=45):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def neue_ausgaben(tage):
    """(Jahr, Nummer, Datum, Titel) aller Ausgaben der letzten Tage aus dem RSS-Feed"""
    xml = get(RSS).decode("utf-8", "replace")
    grenze = (dt.date.today() - dt.timedelta(days=tage)).isoformat()
    out = []
    for item in re.findall(r"<item>.*?</item>", xml, re.S):
        link = re.search(r"bgbl-1/(\d{4})/([^<\s/]+)", item)
        datum = re.search(r"<pubDate>([\d-]{10})", item)
        titel = re.search(r"<title>(.*?)</title>", item, re.S)
        if link and datum and datum.group(1) >= grenze:
            out.append((link.group(1), link.group(2), datum.group(1), titel.group(1).strip() if titel else ""))
    return out


def volltext(jahr, nr):
    pdf = get(f"https://www.recht.bund.de/bgbl/1/{jahr}/{nr}/regelungstext.pdf?__blob=publicationFile")
    if pdf[:4] != b"%PDF":
        raise OSError("keine PDF-Datei")
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "x.pdf"
        f.write_bytes(pdf)
        subprocess.run(["pdftotext", "-enc", "UTF-8", str(f), str(f.with_suffix(".txt"))], check=True, capture_output=True)
        text = f.with_suffix(".txt").read_text("utf-8", "replace")
    text = re.sub("­\\s*", "", text)  # Silbentrennung
    return re.sub(r"\s+", " ", text)


def treffer(text, titel, stamm):
    """Art des Treffers für ein Gesetz oder None. Bloße Erwähnungen zählen nicht."""
    s = f"(?:{stamm})\\w*(?:/EU)?"
    if re.search(s, titel):
        return "im Titel"
    if re.search(rf"(?:Änderung|Aufhebung) (?:des|der) {s}", text):
        return "Änderung"
    if re.search(rf"{s}(?:(?!\bArtikel \d).){{0,400}}?geändert worden ist, wird", text):
        return "Änderung"
    if re.search(rf"{s}.{{0,400}}?(?:tritt|treten) (?:am|mit).{{0,60}}?außer Kraft", text):
        return "Außerkrafttreten"
    return None


def termine(text):
    """Künftige Daten aus Sätzen zum Inkrafttreten"""
    heute = dt.date.today()
    out = set()
    for tag, monat, jahr in re.findall(r"(?:tritt|treten) (?:am|mit Wirkung vom) (\d{1,2})\. (" + "|".join(MONATE) + r") (\d{4}) in Kraft", text):
        d = dt.date(int(jahr), MONATE.index(monat) + 1, int(tag))
        if d > heute:
            out.add(d)
    return sorted(out)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--tage", type=int, default=8)
    a.add_argument("--jahr", default=str(dt.date.today().year))
    a.add_argument("--von", type=int)
    a.add_argument("--bis", type=int)
    a.add_argument("--bericht")
    o = a.parse_args()

    gesetze = json.loads((ROOT / "daten" / "gesetze.json").read_text("utf-8"))["gesetze"]
    stämme = {k: g["bgbl"] for k, g in gesetze.items() if g.get("bgbl")}
    paket = json.loads((ROOT / "app" / "rechtsdaten.json").read_text("utf-8"))["gesetze"]

    try:
        if o.von:
            ausgaben = [(o.jahr, str(n), "", "") for n in range(o.von, (o.bis or o.von) + 1)]
        else:
            ausgaben = neue_ausgaben(o.tage)
    except OSError as e:
        print(f"BGBl nicht erreichbar: {e}")
        if o.bericht:
            Path(o.bericht).write_text(f"### ⚠️ Bundesgesetzblatt nicht erreichbar\n\n{e}\n", "utf-8")
        return 3

    zeilen, fehler, geprüft = [], [], 0
    for jahr, nr, datum, titel in ausgaben:
        try:
            text = volltext(jahr, nr)
        except (OSError, subprocess.CalledProcessError) as e:
            fehler.append(f"Nr. {nr}: {e}")
            continue
        geprüft += 1
        for law, stamm in stämme.items():
            art = treffer(text, titel, stamm)
            if not art:
                continue
            drin = f"Nr. {nr}" in " ".join(paket.get(law, {}).get("stand") or [])
            zeilen.append((jahr, nr, law, art, datum, "ja" if drin else "**nein**", termine(text)))

    L = [f"## Bundesgesetzblatt: {geprüft} Ausgabe(n) geprüft", ""]
    if zeilen:
        L += ["| BGBl. I | Gesetz | Art | Datum | im Rechtsdatenpaket vermerkt | künftiges Inkrafttreten |", "|---|---|---|---|---|---|"]
        for jahr, nr, law, art, datum, drin, t in zeilen:
            url = f"https://www.recht.bund.de/bgbl/1/{jahr}/{nr}/VO.html"
            L.append(f"| [Nr. {nr}]({url}) | {law} | {art} | {datum} | {drin} | {', '.join(d.strftime('%d.%m.%Y') for d in t) or '–'} |")
        L += ["", "Vor der Übernahme prüfen: Betrifft die Änderung zitierte Normen, und ist sie schon in Kraft?"]
    else:
        L += ["Keine Änderungen an Gesetzen aus dem Katalog gefunden."]
    if fehler:
        L += ["", "### ⚠️ Nicht lesbar", ""] + [f"- {f}" for f in fehler]
    bericht = "\n".join(L)
    if o.bericht:
        Path(o.bericht).write_text(bericht + "\n", "utf-8")
    print(bericht)
    return 10 if zeilen else (3 if fehler else 0)


if __name__ == "__main__":
    sys.exit(main())
