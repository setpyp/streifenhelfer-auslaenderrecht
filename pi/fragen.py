"""Fragenkatalog und geführter Dialog – ohne Audio/GPIO, damit testbar.

Der Dialog füllt ein Fall-Objekt mit denselben Feldern wie collect() in app/index.html.
Sprechen und Hören werden als Funktionen übergeben (Pi: espeak/Vosk, Simulation: print/input).
"""
import datetime as dt
import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import zahlen

ROOT = Path(__file__).resolve().parent.parent
LAENDER = json.loads((ROOT / "daten" / "laender.json").read_text("utf-8"))["kategorien"]
SONDER = json.loads((ROOT / "daten" / "sonderregelungen.json").read_text("utf-8"))["regeln"]
FREIZUEGIG = {"DE", "EU", "EUN", "EWR", "CH"}

JA = ["ja", "jawohl", "richtig", "korrekt", "stimmt", "genau"]
NEIN = ["nein", "falsch", "nicht", "negativ"]
KOMMANDOS = {"wiederholen": "wiederholen", "zurück": "zurueck", "überspringen": "ueberspringen", "abbrechen": "abbrechen"}


def norm(text):
    """Kleinschreibung, Satzzeichen weg, Mehrfach-Leerzeichen zusammenfassen."""
    return " ".join(re.sub(r"[^a-zäöüß0-9 ]", " ", text.lower()).split())


def kategorie(nat):
    return next((k for k, l in LAENDER.items() if nat in l), "X")


# ---------------------------------------------------------------- Auswahllisten
# (Wert, vorgelesene Bezeichnung, gesprochene Varianten)
ORTE = [("internal_border", "Binnengrenze", ["binnengrenze", "grenzkontrolle", "einreisekontrolle"]),
        ("external_border", "Außengrenze", ["außengrenze", "flughafen außengrenze", "seehafen"]),
        ("border_area", "Grenzgebiet", ["grenzgebiet", "dreißig kilometer"]),
        ("rail", "Zug oder Bahnhof", ["zug", "bahnhof", "bahn", "bahnanlage"]),
        ("airport_inland", "Flughafen Binnenflug", ["binnenflug", "flughafen inland", "inlandsflug"]),
        ("exit", "Ausreisekontrolle", ["ausreise", "ausreisekontrolle"]),
        ("inland", "Inland", ["inland", "sonstige lage"])]
HERKUNFT = [("schengen", "Schengen-Staat", ["schengen", "schengen staat", "schengenstaat"]),
            ("nonschengen", "Drittstaat", ["drittstaat", "nicht schengen", "irland", "zypern"]),
            ("unknown", "unbekannt", ["unbekannt", "weiß nicht"])]
ZWECK = [("tourism", "Besuch oder Tourismus", ["besuch", "tourismus", "urlaub", "geschäftsreise"]),
         ("transit", "Durchreise", ["durchreise", "transit"]),
         ("work", "Erwerbstätigkeit", ["arbeit", "erwerbstätigkeit", "beschäftigung"]),
         ("study", "Studium oder Ausbildung", ["studium", "ausbildung"]),
         ("family", "Familie oder Wohnsitz", ["familie", "familiennachzug", "wohnsitz"]),
         ("protection", "Schutzsuche", ["schutzsuche", "schutz", "asyl"]),
         ("unknown", "unklar", ["unklar", "keine angabe", "unbekannt"])]
DOKUMENTE = [("pass", "gültiger Nationalpass", ["pass", "reisepass", "nationalpass", "gültiger pass"]),
             ("pass_nonbio", "Pass nicht biometrisch", ["nicht biometrisch", "alter pass"]),
             ("idcard", "Personalausweis", ["personalausweis", "ausweis", "identitätskarte"]),
             ("passersatz", "Passersatz", ["passersatz", "reiseausweis", "flüchtlingsausweis"]),
             ("expired", "Dokument abgelaufen", ["abgelaufen", "abgelaufener pass"]),
             ("forged", "Fälschungsverdacht", ["fälschung", "gefälscht", "fälschungsverdacht", "fremdes dokument"]),
             ("none", "kein Dokument", ["kein dokument", "keins", "keine papiere", "nichts"])]
TITEL = [("none", "kein Titel", ["kein titel", "keiner", "kein visum", "nichts"]),
         ("visa_c", "Schengen-Visum", ["schengen visum", "visum c", "schengen"]),
         ("visa_ltv", "räumlich beschränktes Visum", ["räumlich beschränkt", "beschränktes visum"]),
         ("visa_d_de", "nationales Visum Deutschland", ["nationales visum deutschland", "visum d deutschland"]),
         ("visa_d_other", "nationales Visum anderer Staat", ["nationales visum anderer staat", "visum d anderer staat"]),
         ("at_de", "deutscher Aufenthaltstitel", ["aufenthaltstitel deutschland", "aufenthaltserlaubnis", "niederlassungserlaubnis", "blaue karte"]),
         ("at_other", "Aufenthaltstitel anderer Schengen-Staat", ["aufenthaltstitel anderer staat", "titel anderer staat"]),
         ("fiktion", "Fiktionsbescheinigung", ["fiktionsbescheinigung", "fiktion"]),
         ("p24", "vorübergehender Schutz", ["vorübergehender schutz", "paragraph vierundzwanzig"]),
         ("gestattung", "Aufenthaltsgestattung", ["aufenthaltsgestattung", "gestattung", "ankunftsnachweis"]),
         ("duldung", "Duldung", ["duldung"]),
         ("eu_card", "Aufenthaltskarte EU-Familienangehöriger", ["aufenthaltskarte", "familienangehöriger"]),
         ("grenzgaenger", "Grenzgängerkarte", ["grenzgängerkarte", "daueraufenthaltskarte"])]

SYNONYME = {"Vereinigte Staaten": ["amerika", "usa", "vereinigte staaten von amerika"],
            "Vereinigtes Königreich": ["england", "großbritannien", "britannien"],
            "Niederlande": ["holland"], "Belarus": ["weißrussland"], "Moldau": ["moldawien", "republik moldau"],
            "Côte d'Ivoire": ["elfenbeinküste"], "Südkorea": ["korea"], "Republik Kongo": ["kongo"],
            "DR Kongo": ["demokratische republik kongo"], "Palästinensische Gebiete": ["palästina"],
            "Tschechien": ["tschechische republik"], "staatenlos": ["keine staatsangehörigkeit"],
            "ungeklärt": ["unbekannt", "unklar"]}


def _gesprochen(name):
    n = re.sub(r"\(.*?\)", "", name).replace("St. ", "sankt ").replace("-", " ")
    return norm(n)


STAATEN = [(n, n, [_gesprochen(n)] + SYNONYME.get(n, [])) for l in LAENDER.values() for n in l]

SONDER_WORTE = {"tr-fahrpersonal": ["fahrpersonal", "lkw fahrer", "fahrer", "lastwagenfahrer"],
                "anlage-a-sichtvermerk": ["sichtvermerksabkommen", "älteres abkommen"],
                "fluechtlings-reiseausweis": ["flüchtlingsreiseausweis", "reiseausweis"],
                "dienstpass": ["dienstpass", "dienstlicher pass"],
                "flugpersonal": ["flugpersonal", "flugbesatzung"],
                "seeleute": ["seeleute", "seemann", "seelotse", "schiffspersonal"],
                "binnenschifffahrt": ["binnenschifffahrt", "binnenschiff"],
                "schuelerliste": ["schülerliste", "schülergruppe"],
                "daueraufenthalt-eu-dienstleistung": ["daueraufenthalt", "langfristig aufenthaltsberechtigt"],
                "durchbefoerderung": ["durchbeförderung"],
                "bilaterale-abkommen-anderer-staaten": ["anderer staat", "bilaterales abkommen"]}


def sonder_fuer(nat):
    """Wie sonderFuer() in app/index.html: spezifische Regeln zuerst."""
    if not nat or kategorie(nat) in FREIZUEGIG:
        return []
    r = [x for x in SONDER if "*" in x["staaten"] or nat in x["staaten"]]
    return [x for x in r if "*" not in x["staaten"]] + [x for x in r if "*" in x["staaten"]]


# ---------------------------------------------------------------- Erkennung -> Wert
def waehle(text, optionen):
    """Gesprochenen Text der passendsten Option zuordnen -> (Wert, Bezeichnung) oder None."""
    t = norm(text)
    if not t:
        return None
    treffer = [(len(p), w, l) for w, l, ps in optionen for p in ps if re.search(rf"\b{re.escape(p)}\b", t)]
    if treffer:
        _, w, l = max(treffer)
        return w, l
    alle = {p: (w, l) for w, l, ps in optionen for p in ps}
    nah = difflib.get_close_matches(t, alle, n=1, cutoff=0.8)
    return alle[nah[0]] if nah else None


def janein(text):
    w = norm(text).split()
    if any(x in w for x in NEIN):
        return False
    if any(x in w for x in JA):
        return True
    return None


def kommando(text):
    t = norm(text)
    return next((v for k, v in KOMMANDOS.items() if t == k or t.startswith(k + " ")), None)


def grammatik(frage):
    """Phrasenliste für Vosk (eingeschränkte Erkennung) oder None für freie Erkennung."""
    worte = list(KOMMANDOS)
    if frage.typ == "auswahl":
        worte += [p for _, _, ps in frage.optionen for p in ps]
    elif frage.typ == "janein":
        worte += JA + NEIN
    else:
        return None
    return sorted(set(worte)) + ["[unk]"]


# ---------------------------------------------------------------- Fragenkatalog
@dataclass
class Frage:
    id: str
    text: str
    typ: str  # auswahl | zahl | datum | janein | frei
    feld: str
    optionen: list = field(default_factory=list)
    wenn: Callable = lambda f: True
    bestaetigen: bool = True


def _drittstaat(f):
    return f["nat"] and kategorie(f["nat"]) not in FREIZUEGIG


def _nicht_deutsch(f):
    return f["nat"] and kategorie(f["nat"]) != "DE"


def katalog(fall):
    """Fragen in Formular-Reihenfolge; Sonderregel-Fragen hängen von der Staatsangehörigkeit ab."""
    fr = [
        Frage("nat", "Welche Staatsangehörigkeit hat die Person?", "auswahl", "nat", STAATEN),
        Frage("age", "Wie alt ist die Person?", "zahl", "age"),
        Frage("acc", "Ist die minderjährige Person unbegleitet?", "janein", "unaccompanied",
              wenn=lambda f: f["age"] is not None and f["age"] < 18, bestaetigen=False),
        Frage("place", "Wo findet die Kontrolle statt? Zum Beispiel Binnengrenze, Zug oder Inland.", "auswahl", "place", ORTE),
        Frage("from", "Woher ist die Person eingereist? Schengen-Staat, Drittstaat oder unbekannt.", "auswahl", "from", HERKUNFT,
              wenn=_nicht_deutsch),
        Frage("iddoc", "Welches Dokument liegt vor? Zum Beispiel Pass, Personalausweis oder kein Dokument.", "auswahl", "iddoc",
              DOKUMENTE),
        Frage("title", "Welcher Aufenthaltstitel oder welches Visum liegt vor? Sagen Sie kein Titel, wenn keiner vorliegt.",
              "auswahl", "title", TITEL, wenn=_drittstaat),
        Frage("validUntil", "Bis wann ist der Titel gültig? Zum Beispiel dritter März zweitausendsiebenundzwanzig.", "datum",
              "validUntil", wenn=lambda f: _drittstaat(f) and f["title"] not in ("none", "gestattung")),
        Frage("visaDays", "Wie viele Aufenthaltstage erlaubt das Visum?", "zahl", "visaDays",
              wenn=lambda f: _drittstaat(f) and f["title"] in ("visa_c", "visa_ltv")),
        Frage("ltvDE", "Gilt das räumlich beschränkte Visum für Deutschland?", "janein", "ltvDE",
              wenn=lambda f: _drittstaat(f) and f["title"] == "visa_ltv", bestaetigen=False),
        Frage("restrictViol", "Liegt ein Verstoß gegen eine räumliche Beschränkung vor?", "janein", "restrictViol",
              wenn=lambda f: _drittstaat(f) and f["title"] in ("gestattung", "duldung"), bestaetigen=False),
        Frage("restrictRepeat", "Ist ein früherer Verstoß bekannt?", "janein", "restrictRepeat",
              wenn=lambda f: f["restrictViol"], bestaetigen=False),
        Frage("days", "Wie viele Tage war die Person in den letzten hundertachtzig Tagen im Schengen-Raum?", "zahl", "days",
              wenn=_drittstaat),
        Frage("purpose", "Welcher Aufenthaltszweck wird angegeben?", "auswahl", "purpose", ZWECK, wenn=_drittstaat),
    ]
    for fid, text in [("asylum", "Wurde ein Asyl- oder Schutzgesuch geäußert?"),
                      ("warrant", "Gibt es einen Fahndungstreffer, Haftbefehl oder eine Aufenthaltsermittlung?"),
                      ("sisRefusal", "Gibt es ein Einreise- und Aufenthaltsverbot oder eine Einreiseverweigerung im SIS?"),
                      ("working", "Wurde eine Erwerbstätigkeit festgestellt?"),
                      ("smuggling", "Gibt es Anhaltspunkte für eine Schleusung?"),
                      ("nomeans", "Fehlen ausreichende Mittel für Lebensunterhalt oder Rückreise?"),
                      ("identityUnclear", "Ist die Identität zweifelhaft oder sind die Angaben widersprüchlich?")]:
        fr.append(Frage(fid, text, "janein", fid, wenn=_nicht_deutsch if fid != "warrant" else (lambda f: bool(f["nat"])),
                        bestaetigen=False))
    fr.append(Frage("beschaeftigung", "Beschreiben Sie bitte kurz die Beschäftigung.", "frei", "beschaeftigung",
                    wenn=lambda f: f["working"], bestaetigen=False))

    regeln = sonder_fuer(fall["nat"])
    if regeln:
        spezifisch = [r["titel"] for r in regeln if "*" not in r["staaten"]]
        hinweis = (" In Betracht kommt insbesondere: " + "; ".join(spezifisch) + ".") if spezifisch else ""
        opts = [("", "keine Sonderregelung", ["keine", "keine sonderregelung", "nein"])] + \
               [(r["id"], r["titel"], SONDER_WORTE.get(r["id"], [])) for r in regeln]
        fr.append(Frage("sonder", "Kommt eine Sonderregelung in Betracht? Sagen Sie keine oder nennen Sie die Regelung." + hinweis,
                        "auswahl", "sonder_id", opts))
        regel = next((r for r in regeln if r["id"] == fall.get("sonder_id")), None)
        if regel:
            for i, v in enumerate(regel["voraussetzungen"]):
                fr.append(Frage(f"sv{i}", f"Voraussetzung: {v}. Ist das festgestellt?", "janein", f"sv{i}", bestaetigen=False))
    fr.append(Frage("bemerkung", "Möchten Sie eine Bemerkung aufnehmen? Sprechen Sie sie, oder sagen Sie nein.", "frei",
                    "bemerkung", bestaetigen=False))
    return [f for f in fr if f.wenn(fall)]


def neuer_fall(heute=None):
    return {"nat": "", "age": None, "unaccompanied": False, "eufam": False,
            "date": (heute or dt.date.today()).isoformat(), "place": "inland", "from": "unknown", "nearEntry": False,
            "purpose": "unknown", "iddoc": "pass", "title": "none", "validUntil": None, "visaDays": 90, "ltvDE": False,
            "restrictViol": False, "restrictRepeat": False, "days": None, "entryDE": None, "asylum": False,
            "sisRefusal": False, "warrant": False, "working": False, "smuggling": False, "nomeans": False,
            "identityUnclear": False, "beschaeftigung": "", "bemerkung": "", "sonder_id": ""}


def auswerten(frage, text, heute=None):
    """Antworttext -> (Wert, vorzulesende Bezeichnung) oder None, wenn nicht verstanden."""
    if frage.typ == "auswahl":
        return waehle(text, frage.optionen)
    if frage.typ == "zahl":
        n = zahlen.zahl(text)
        return (n, str(n)) if n is not None else None
    if frage.typ == "datum":
        d = zahlen.datum(text, heute)
        return (d.isoformat(), d.strftime("%d.%m.%Y")) if d else None
    if frage.typ == "janein":
        j = janein(text)
        return (j, "ja" if j else "nein") if j is not None else None
    if frage.typ == "frei":
        return ("", "keine") if janein(text) is False else (text.strip(), text.strip())
    raise ValueError(frage.typ)


def fall_fuer_bewertung(fall):
    """Dialogfelder -> Sachverhalt wie collect() (Sonderregel mit Voraussetzungen)."""
    s = {k: v for k, v in fall.items() if k != "sonder_id" and not k.startswith("sv")}
    regel = next((r for r in SONDER if r["id"] == fall.get("sonder_id")), None)
    if regel:
        offen = [v for i, v in enumerate(regel["voraussetzungen"]) if not fall.get(f"sv{i}")]
        s["sonder"] = {"id": regel["id"], "erfuellt": bool(regel["voraussetzungen"]) and not offen, "offen": offen}
    else:
        s["sonder"] = None
    return s


class Dialog:
    """Geführte Abfrage. sprich(text) gibt aus, hoere(grammatik) liefert erkannten Text."""

    def __init__(self, sprich: Callable[[str], None], hoere: Callable[[Optional[list]], str], heute=None, max_versuche=3):
        self.sprich, self.hoere, self.heute, self.max_versuche = sprich, hoere, heute, max_versuche

    def ablauf(self):
        fall, beantwortet, alt = neuer_fall(self.heute), [], {}
        self.sprich("Streifenhelfer bereit. Drücken Sie zum Antworten die Sprechtaste.")
        while True:
            offen = [f for f in katalog(fall) if f.id not in beantwortet]
            if not offen:
                return fall
            frage = offen[0]
            ergebnis = self._frage(frage)
            if ergebnis == "abbrechen":
                self.sprich("Abgebrochen. Keine Daten gespeichert.")
                return None
            if ergebnis == "zurueck":
                if beantwortet:
                    fid = beantwortet.pop()
                    feld, wert = alt.pop(fid)
                    fall[feld] = wert
                continue
            alt[frage.id] = (frage.feld, fall.get(frage.feld))  # sv*-Felder existieren erst nach Beantwortung
            if ergebnis != "ueberspringen":
                fall[frage.feld] = ergebnis
            beantwortet.append(frage.id)

    def _frage(self, frage):
        for _ in range(self.max_versuche):
            self.sprich(frage.text)
            text = self.hoere(grammatik(frage))
            k = kommando(text)
            if k == "wiederholen":
                continue
            if k:
                return k
            wert = auswerten(frage, text, self.heute)
            if wert is None:
                self.sprich("Nicht verstanden.")
                continue
            if not frage.bestaetigen:
                return wert[0]
            self.sprich(f"{wert[1]}. Richtig?")
            antwort = self.hoere(grammatik(Frage("b", "", "janein", "")))
            if kommando(antwort) == "abbrechen":
                return "abbrechen"
            if janein(antwort):
                return wert[0]
        self.sprich("Frage wird übersprungen.")
        return "ueberspringen"


def kurzfassung(R, max_punkte=3):
    """Bewertung (Ergebnis von evaluate) -> kurzer Text zum Vorlesen."""
    teile = [f"Ergebnis: {R['head']}."]
    mass = [i["t"] for i in R["meas"] if i["lvl"] in ("bad", "warn")][:max_punkte]
    if mass:
        teile.append("Maßnahmen: " + "; ".join(mass) + ".")
    straf = [i["t"] for i in R["crim"] if i["lvl"] in ("bad", "warn")][:max_punkte]
    if straf:
        teile.append("Straf- und Bußgeldrecht: " + "; ".join(straf) + ".")
    n = sum(1 for k in ("find", "meas", "crim", "notify", "notes") for i in R[k] if i.get("v"))
    if n:
        teile.append(f"{n} Punkte sind zu verifizieren.")
    teile.append("Einzelheiten auf dem Handy.")
    return " ".join(teile)
