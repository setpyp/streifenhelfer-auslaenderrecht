#!/usr/bin/env python3
"""
Erzeugt das öffentliche Rechtsdatenpaket der App (app/rechtsdaten.json + app/rechtsdaten.js).

Ablauf:
  1. Alle Normzitate aus app/index.html einsammeln und in Schlüssel zerlegen
     (z. B. "§ 57 Abs. 1, 2 AufenthG" -> "AufenthG § 57").
  2. Wortlaut der zitierten Normen aus amtlichen Quellen laden:
       - gesetze-im-internet.de (XML-Download je Gesetz)
       - EUR-Lex (HTML, neueste konsolidierte Fassung, sonst Amtsblattfassung)
  3. Länderliste (daten/laender.json) und Gesetzeskatalog (daten/gesetze.json) beilegen.
  4. Prüfbericht ausgeben: nicht gefundene / weggefallene Normen, unbekannte Quellen.

Aufruf:  python tools/build_rechtsdaten.py
Nur Standardbibliothek, Python >= 3.9.
"""
import datetime as dt
import html
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
DATEN = ROOT / "daten"
UA = {"User-Agent": "Streifenhelfer-Build/1.0 (+offline Rechtsdatenpaket)"}

# --------------------------------------------------------------------------
# Zitat-Parser — muss mit parseCitation() in app/index.html übereinstimmen!
# --------------------------------------------------------------------------
NUM_RE = re.compile(r"(§§?|Art\.)\s*(\d+[a-z]?)((?:\s*(?:ff\.)?\s*,\s*\d+[a-z]?)*)")
SPLIT_RE = re.compile(r";| i\.V\.m\. | / ")
ANLAGE_RE = re.compile(r"Anlage\s+([A-Z])\b")


def build_alias_index(gesetze):
    idx = []
    for abbr, g in gesetze.items():
        for a in g["aliase"]:
            idx.append((a, abbr))
    idx.sort(key=lambda x: -len(x[0]))
    return [(re.compile(r"(?<![A-Za-zÄÖÜäöüß])" + re.escape(a) + r"(?![A-Za-zÄÖÜäöüß])"), abbr) for a, abbr in idx]


def find_law(seg, alias_index):
    best = None
    for rx, abbr in alias_index:
        m = rx.search(seg)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), abbr)
    return best[1] if best else None


def parse_citation(cit, alias_index, gesetze):
    keys = []
    for seg in SPLIT_RE.split(cit):
        law = find_law(seg, alias_index)
        if not law:
            continue
        gl = gesetze[law]["gliederung"]
        found = False
        for m in NUM_RE.finditer(seg):
            nums = [m.group(2)] + re.findall(r"\d+[a-z]?", m.group(3))
            for n in nums:
                keys.append(f"{law} {gl} {n}")
                found = True
        for m in ANLAGE_RE.finditer(seg):
            keys.append(f"{law} Anlage {m.group(1)}")
            found = True
        if not found:
            keys.append(law)
    return list(dict.fromkeys(keys))


def law_of(key):
    """'AufenthV § 16' / 'SGK Art. 6' / 'AufenthV Anlage A' / 'EuGH Soysal' -> Gesetzeskürzel"""
    return re.split(r" (?:§|Art\.|Anlage) ", key)[0]


def num_of(key, law):
    """Teil des Schlüssels nach dem Gesetz: '57', 'Anlage A' oder '' (ganzes Dokument)"""
    rest = key[len(law):].strip()
    return rest if rest.startswith("Anlage") or not rest else rest.split(" ", 1)[1]


# --------------------------------------------------------------------------
# Hilfen
# --------------------------------------------------------------------------
HOST_FEHLER = {}  # Host -> Anzahl endgültig fehlgeschlagener Abrufe


def get(url, timeout=45, versuche=2, headers=None):
    """Abruf mit Wiederholung. Ist ein Host bereits zweimal ausgefallen, sofort abbrechen
    (spart bei gesperrtem Host viele Minuten Wartezeit)."""
    host = urllib.parse.urlsplit(url).netloc
    if HOST_FEHLER.get(host, 0) >= 2:
        raise OSError(f"{host} nicht erreichbar (übersprungen)")
    for i in range(versuche):
        try:
            if "eur-lex.europa.eu" in host:
                time.sleep(2)  # höflich abrufen – EUR-Lex sperrt bei zu vielen Anfragen
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                # EUR-Lex-Bot-Schutz antwortet mit 202 und leerem Inhalt – das ist KEIN Erfolg
                if r.status != 200 or len(body) < 500:
                    raise OSError(f"HTTP {r.status}, {len(body)} Bytes (Bot-Schutz/Sperre?)")
                return body
        except urllib.error.HTTPError:
            raise  # 404 o. Ä.: Wiederholen zwecklos
        except Exception:
            if i == versuche - 1:
                HOST_FEHLER[host] = HOST_FEHLER.get(host, 0) + 1
                raise
            time.sleep(5)


def strip_tags(s):
    s = re.sub(r"<(br|BR)\s*/?>", "\n", s)
    s = re.sub(r"</(p|P|div|tr|li|dd|dt|table)>", "\n", s)
    s = re.sub(r"<td[^>]*>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    lines = [re.sub(r"[ \t ]+", " ", l).strip() for l in s.split("\n")]
    out, blank = [], False
    for l in lines:
        if not l:
            blank = True
            continue
        if blank and out:
            out.append("")
        out.append(l)
        blank = False
    return "\n".join(out).strip()


# --------------------------------------------------------------------------
# gesetze-im-internet.de
# --------------------------------------------------------------------------
def load_gii(slug):
    data = get(f"https://www.gesetze-im-internet.de/{slug}/xml.zip")
    z = zipfile.ZipFile(io.BytesIO(data))
    xml = z.read([n for n in z.namelist() if n.endswith(".xml")][0]).decode("utf-8")
    normen = {}
    for m in re.finditer(r"<norm\b.*?</norm>", xml, re.S):
        block = m.group(0)
        enbez = re.search(r"<enbez>(.*?)</enbez>", block)
        if not enbez:
            continue
        anlage = re.match(r"\s*Anlage\s+([A-Z])\b", enbez.group(1))
        num = re.search(r"(\d+[a-z]?)", enbez.group(1))
        if anlage:
            num_key = f"Anlage {anlage.group(1)}"
        elif num and re.match(r"\s*(§|Art)", enbez.group(1)):
            num_key = num.group(1)
        else:
            continue
        titel = re.search(r"<titel[^>]*>(.*?)</titel>", block, re.S)
        content = re.search(r"<Content>(.*?)</Content>", block, re.S)
        text = strip_tags(content.group(1)) if content else ""
        normen.setdefault(num_key, {
            "bez": strip_tags(enbez.group(1)),
            "titel": strip_tags(titel.group(1)) if titel else "",
            "text": text,
        })
    stand = [strip_tags(s) for s in re.findall(r"<standkommentar>(.*?)</standkommentar>", xml[:20000], re.S)]
    build = re.search(r'builddate="(\d{8})', xml)
    return normen, {"stand": stand, "abrufdatum": build.group(1) if build else None}


# --------------------------------------------------------------------------
# EUR-Lex
# --------------------------------------------------------------------------
def eurlex_html(celex):
    """Dokument-HTML von EUR-Lex; bei Sperre/Ausfall über den Cellar-Dienst des Amts für Veröffentlichungen
    (gleicher amtlicher Inhalt, anderer Zugang)."""
    try:
        return get(f"https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:{celex}")
    except urllib.error.HTTPError:
        raise  # 404 o. Ä.: Dokument/Fassung existiert nicht
    except Exception as e1:
        try:
            return get("http://publications.europa.eu/resource/celex/" + urllib.parse.quote(celex, safe=""),
                       headers={"Accept": "application/xhtml+xml, text/html;q=0.9", "Accept-Language": "deu"})
        except Exception as e2:
            raise OSError(f"EUR-Lex: {e1}; Cellar: {e2}")


def eurlex_latest_consolidated(celex):
    if not re.match(r"^3\d{4}[RL]\d{4}$", celex):
        return None
    page = get(f"https://eur-lex.europa.eu/legal-content/DE/ALL/?uri=CELEX:{celex}").decode("utf-8", "replace")
    base = "0" + celex[1:]
    today = dt.date.today().strftime("%Y%m%d")
    dates = sorted(set(d for d in re.findall(re.escape(base) + r"-(\d{8})", page) if d <= today))
    return f"{base}-{dates[-1]}" if dates else None


def split_articles_by_text(page):
    """Fallback für ältere EUR-Lex-Formate ohne id="art_N": Trennung an Zeilen 'Artikel N'.
    Inhaltsverzeichnisse erzeugen kurze Treffer – je Artikel gewinnt der längste Abschnitt."""
    text = strip_tags(page)
    parts = re.split(r"\n(?:Artikel|Art\.)\s+(\d+[a-z]?)\s*\n", "\n" + text)
    normen = {}
    for num, body in zip(parts[1::2], parts[2::2]):
        cut = re.search(r"\n(ANHANG|Anhang)\b|\nSchlussakte\b", body)
        if cut:
            body = body[:cut.start()]
        lines = [l for l in body.strip().split("\n")]
        titel = ""
        if lines and len(lines[0]) < 140 and not re.match(r"^\(?\d", lines[0]):
            titel, lines = lines[0], lines[1:]
        entry = {"bez": f"Art. {num}", "titel": titel, "text": "\n".join(lines).strip()}
        if num not in normen or len(entry["text"]) > len(normen[num]["text"]):
            normen[num] = entry
    return normen


def load_eurlex(celex, original_erlaubt=False):
    """original_erlaubt: Ist die Suche nach konsolidierten Fassungen nicht möglich, darf die
    Amtsblattfassung verwendet werden – nur wenn es noch keine (konsolidierte) Vorfassung gibt."""
    try:
        cons = eurlex_latest_consolidated(celex)
    except Exception:
        if not original_erlaubt:
            raise
        cons = None
    used = cons or celex
    try:
        page = eurlex_html(used).decode("utf-8", "replace")
    except urllib.error.HTTPError:
        if not cons:
            raise
        cons, used = None, celex  # angebliche konsolidierte Fassung existiert nicht
        page = eurlex_html(used).decode("utf-8", "replace")
    if 'id="art_' not in page:
        return split_articles_by_text(page), {"fassung": used, "konsolidiert": bool(cons)}
    normen = {}
    starts = [(m.start(), m.group(1)) for m in re.finditer(r'id="art_(\d+[a-z]?)"', page)]
    for i, (pos, num) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(page)
        # Rest der Seite (Anhänge) nach letztem Artikel abschneiden
        chunk = page[pos:end]
        cut = re.search(r'id="anx_|class="oj-doc-ti"[^>]*>\s*ANHANG', chunk)
        if cut:
            chunk = chunk[:cut.start()]
        text = strip_tags(chunk.split(">", 1)[1] if ">" in chunk else chunk)
        lines = text.split("\n")
        if lines and re.match(r"^Artikel\s+\d", lines[0]):
            lines = lines[1:]
        while lines and not lines[0]:
            lines = lines[1:]
        titel = ""
        if lines and len(lines[0]) < 140 and not re.match(r"^\(?\d", lines[0]):
            titel, lines = lines[0], lines[1:]
        normen.setdefault(num, {"bez": f"Art. {num}", "titel": titel, "text": "\n".join(lines).strip()})
    return normen, {"fassung": used, "konsolidiert": bool(cons)}


# --------------------------------------------------------------------------
QUELLDATEIEN = ["regelwerk.js", "index.html"]  # hier werden Normzitate gesucht


def load_sonderregelungen():
    return json.loads((DATEN / "sonderregelungen.json").read_text("utf-8"))


def collect_citations(gesetze, alias_index):
    src = "\n".join((APP / f).read_text("utf-8") for f in QUELLDATEIEN)
    literals = set(re.findall(r'"((?:[^"\\\n]|\\.)*)"', src))
    for r in load_sonderregelungen()["regeln"]:  # Quellen der Sonderregelungen sind ebenfalls Zitate
        literals.update(r.get("quellen", []))
    citations = [l for l in literals if find_law(l, alias_index)]
    keys = set()
    for c in citations:
        keys.update(parse_citation(c, alias_index, gesetze))
    return citations, keys


def pruefen():
    """Offline-Prüfung ohne Download: sind alle Zitate im vorhandenen Paket mit Wortlaut aufgelöst?"""
    gesetze = json.loads((DATEN / "gesetze.json").read_text("utf-8"))["gesetze"]
    paket = json.loads((APP / "rechtsdaten.json").read_text("utf-8"))
    _, keys = collect_citations(gesetze, build_alias_index(gesetze))
    fehler = []
    for k in sorted(keys):
        law = law_of(k)
        if gesetze[law]["quelle"] == "link" or (k == law and gesetze[law]["quelle"] != "eurlex_dok"):
            continue
        n = paket["normen"].get(k)
        if not n:
            fehler.append(f"{k}: nicht im Paket (Paket neu bauen)")
        elif n.get("weggefallen"):
            fehler.append(f"{k}: weggefallen")
        elif not n.get("text"):
            fehler.append(f"{k}: ohne Wortlaut")
    print(f"{len(keys)} zitierte Normen geprüft, {len(fehler)} Befunde")
    for f in fehler:
        print("  " + f)
    return 1 if fehler else 0


def main():
    if "--pruefen" in sys.argv:
        return pruefen()
    gesetze = json.loads((DATEN / "gesetze.json").read_text("utf-8"))["gesetze"]
    laender = json.loads((DATEN / "laender.json").read_text("utf-8"))
    alias_index = build_alias_index(gesetze)
    citations, keys = collect_citations(gesetze, alias_index)
    by_law = {}
    for k in keys:
        by_law.setdefault(law_of(k), set()).add(k)
    # Kerngesetze vollständig aufnehmen (für Weisungsverweise und Volltextsuche)
    for law, g in gesetze.items():
        if g.get("vollstaendig"):
            by_law.setdefault(law, set())

    report = {"nicht_gefunden": [], "weggefallen": [], "quelle_fehler": [], "wortlaut_behalten": [], "nur_link": []}
    out_gesetze, out_normen = {}, {}
    # Bisheriges Paket als Rückfallebene: fällt eine Quelle aus, bleibt der alte Wortlaut erhalten
    try:
        vorher = json.loads((APP / "rechtsdaten.json").read_text("utf-8"))
    except (OSError, ValueError):
        vorher = {"gesetze": {}, "normen": {}}
    for law, g in gesetze.items():  # Katalog vollständig mitliefern (Aliase für den Zitat-Parser der App)
        out_gesetze[law] = {"name": g["name"], "quelle": g["quelle"], "gliederung": g["gliederung"],
                            "aliase": g["aliase"], "url": g.get("url", "")}

    for law in sorted(by_law):
        g = gesetze[law]
        meta = out_gesetze[law]
        normen = {}
        try:
            if g["quelle"] == "gii":
                meta["url"] = f"https://www.gesetze-im-internet.de/{g['slug']}/"
                normen, info = load_gii(g["slug"])
                if not normen:
                    raise RuntimeError("keine Paragrafen erkannt")
                meta.update(info)
            elif g["quelle"] == "eurlex_dok":
                meta["url"] = f"https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:{g['celex']}"
                text = strip_tags(eurlex_html(g["celex"]).decode("utf-8", "replace"))
                if len(text) < 1000:
                    raise RuntimeError("Dokument ohne Inhalt (Seite geändert oder gesperrt?)")
                normen = {"": {"bez": g["name"], "titel": g.get("titel", ""), "text": text}}
                meta["fassung"] = g["celex"]
            elif g["quelle"] == "eurlex":
                meta["url"] = f"https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:{g['celex']}"
                alt_fassung = vorher.get("gesetze", {}).get(law, {}).get("fassung") or ""
                normen, info = load_eurlex(g["celex"], original_erlaubt=not alt_fassung)
                if not normen:
                    raise RuntimeError("keine Artikel erkannt (Seite geändert oder gesperrt?)")
                # bisher konsolidiert -> neue Fassung muss ebenfalls konsolidiert und mindestens gleich neu sein
                if alt_fassung.startswith("0") and (not info["konsolidiert"] or info["fassung"] < alt_fassung):
                    raise RuntimeError(f"abgerufene Fassung {info['fassung']} ist älter als bisherige {alt_fassung}")
                meta.update(info)
                if info.get("konsolidiert"):
                    meta["url"] = f"https://eur-lex.europa.eu/legal-content/DE/TXT/?uri=CELEX:{info['fassung']}"
            else:
                meta["url"] = g["url"]
                report["nur_link"].append(law)
        except Exception as e:  # Quelle nicht erreichbar -> bisherigen Wortlaut übernehmen
            meta["url"] = meta.get("url") or g.get("url", "")
            alt_meta = vorher.get("gesetze", {}).get(law, {})
            normen = {n["nr"]: {"bez": n["bez"], "titel": n.get("titel", ""), "text": n.get("text", "")}
                      for n in vorher.get("normen", {}).values() if n.get("gesetz") == law}
            for f in ("fassung", "konsolidiert", "abrufdatum", "stand"):
                if f in alt_meta:
                    meta[f] = alt_meta[f]
            meta["nicht_aktualisiert"] = True
            report["quelle_fehler"].append(
                f"{law}: {e} – " + (f"bisheriger Wortlaut übernommen ({len(normen)} Normen)" if normen else "KEIN Wortlaut verfügbar"))
        print(f"  {law:14s} {len(normen):5d} Normen geladen  ({meta.get('fassung') or meta.get('abrufdatum') or g['quelle']})")

        wanted = set(by_law[law])
        if g.get("vollstaendig"):
            wanted |= {f"{law} {n}" if n.startswith("Anlage") else f"{law} {g['gliederung']} {n}" for n in normen}
        if g["quelle"] == "eurlex_dok":
            wanted = {law}
        for k in sorted(wanted):
            if k == law and g["quelle"] != "eurlex_dok":
                continue
            num = num_of(k, law)
            n = normen.get(num)
            if not num:
                bez = g["name"]
            elif num.startswith("Anlage"):
                bez = f"{num} {law}"
            else:
                bez = f"{g['gliederung']} {num} {law}"
            entry = {"gesetz": law, "nr": num, "bez": bez, "url": meta["url"]}
            if k in by_law[law]:
                entry["zitiert"] = True  # vom Regelwerk zitiert -> Änderungen sind fachlich zu prüfen
            alt_n = vorher.get("normen", {}).get(k) or {}
            if alt_n.get("text") and not alt_n.get("weggefallen") and (not n or not n["text"].strip()):
                n = {"titel": alt_n.get("titel", ""), "text": alt_n["text"]}
                entry["nicht_aktualisiert"] = True
                report["wortlaut_behalten"].append(f"{k}: neuer Wortlaut leer/fehlend – bisheriger übernommen (Einlesefehler?)")
            if n:
                entry.update({"titel": n["titel"], "text": n["text"]})
                gone = re.fullmatch(r"\(?\s*(weggefallen|aufgehoben)\s*\)?", n["text"].strip() or "", re.I) or \
                    re.search(r"weggefallen|aufgehoben", n["titel"], re.I)
                if gone:
                    entry["weggefallen"] = True
                    if k in by_law[law]:  # nur zitierte Normen sind ein Befund
                        report["weggefallen"].append(k)
            elif g["quelle"] in ("gii", "eurlex") and normen:
                report["nicht_gefunden"].append(k)
            out_normen[k] = entry

    paket = {
        "meta": {
            "typ": "streifenhelfer-rechtsdaten",
            "version": dt.datetime.now().strftime("%Y%m%d%H%M"),
            "erstellt": dt.datetime.now().isoformat(timespec="minutes"),
            "hinweis": "Öffentliche Rechtsquellen: Bundesrecht von gesetze-im-internet.de (amtliche Werke, § 5 UrhG); "
                       "EU-Recht von EUR-Lex, © Europäische Union, https://eur-lex.europa.eu/. "
                       "Amtlich verbindlich sind allein BGBl. und ABl. EU.",
        },
        "gesetze": out_gesetze,
        "normen": out_normen,
        "laender": laender,
        "sonderregelungen": load_sonderregelungen(),
        "bericht": report,
    }
    js = json.dumps(paket, ensure_ascii=False, separators=(",", ":"))
    (APP / "rechtsdaten.json").write_text(js, "utf-8")
    (APP / "rechtsdaten.js").write_text("window.RECHTSDATEN=" + js + ";\n", "utf-8")
    # Service-Worker-Cache an Datenversion koppeln, damit Geräte das neue Paket laden
    sw = APP / "sw.js"
    sw.write_text(re.sub(r'const CACHE = "[^"]*";', f'const CACHE = "streifenhelfer-{paket["meta"]["version"]}";',
                         sw.read_text("utf-8")), "utf-8")

    print(f"\n{len(citations)} Zitate -> {len(out_normen)} Normen aus {len(out_gesetze)} Quellen, "
          f"Paket {len(js)//1024} KB, Version {paket['meta']['version']}")
    for k, v in report.items():
        if v:
            print(f"\n{k.upper()} ({len(v)}):\n  " + "\n  ".join(sorted(v)))
    # 1 = Regelwerk betroffen, 2 = Quelle(n) nicht erreichbar (Paket enthält alten Wortlaut), 0 = ok
    if report["nicht_gefunden"] or report["weggefallen"]:
        return 1
    return 2 if report["quelle_fehler"] or report["wortlaut_behalten"] else 0


if __name__ == "__main__":
    sys.exit(main())
