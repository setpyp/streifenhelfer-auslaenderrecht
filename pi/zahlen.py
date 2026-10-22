"""Deutsche Zahl- und Datumswörter (wie sie Vosk ausgibt) in Zahlen bzw. Daten umwandeln."""
import datetime as dt
import re

EINER = {"null": 0, "eins": 1, "ein": 1, "eine": 1, "zwei": 2, "zwo": 2, "drei": 3, "vier": 4, "fünf": 5,
         "sechs": 6, "sieben": 7, "acht": 8, "neun": 9}
ZEHNER_SONDER = {"zehn": 10, "elf": 11, "zwölf": 12, "dreizehn": 13, "vierzehn": 14, "fünfzehn": 15,
                 "sechzehn": 16, "siebzehn": 17, "achtzehn": 18, "neunzehn": 19}
ZEHNER = {"zwanzig": 20, "dreißig": 30, "vierzig": 40, "fünfzig": 50, "sechzig": 60, "siebzig": 70,
          "achtzig": 80, "neunzig": 90}
MONATE = {"januar": 1, "jänner": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6, "juli": 7,
          "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12}


def _norm(text):
    return text.lower().replace("dreissig", "dreißig").replace("maerz", "märz").strip()


def _unter_hundert(s):
    if s == "":
        return 0
    for tab in (EINER, ZEHNER_SONDER, ZEHNER):
        if s in tab:
            return tab[s]
    if "und" in s:  # "fünfundsechzig"
        einer, _, zehner = s.partition("und")
        if einer in EINER and zehner in ZEHNER:
            return EINER[einer] + ZEHNER[zehner]
    raise ValueError(s)


def _zahl(s):
    if s.isdigit():
        return int(s)
    if "tausend" in s:
        links, _, rechts = s.partition("tausend")
        return (_zahl(links) if links else 1) * 1000 + (_zahl(rechts.removeprefix("und")) if rechts else 0)
    if "hundert" in s:
        links, _, rechts = s.partition("hundert")
        return (_unter_hundert(links) if links else 1) * 100 + (_zahl(rechts.removeprefix("und")) if rechts else 0)
    return _unter_hundert(s)


def zahl(text):
    """'fünfundsechzig' / 'hundert zwanzig' / '65' -> int, sonst None."""
    s = re.sub(r"\s+", "", _norm(text))
    try:
        return _zahl(s) if s else None
    except ValueError:
        return None


def ordinal(wort):
    """'dritter' -> 3, 'einunddreißigsten' -> 31, sonst None."""
    w = _norm(wort)
    for stamm, wert in (("erst", 1), ("dritt", 3), ("siebt", 7), ("acht", 8)):
        if w.startswith(stamm) and len(w) <= len(stamm) + 2:
            return wert
    for endung in ("sten", "ster", "stem", "ste", "ten", "ter", "tem", "te"):  # "sechster": "ste" scheitert, "ter" passt
        if w.endswith(endung) and (n := zahl(w[: -len(endung)])) is not None:
            return n
    return None


def datum(text, heute=None):
    """'dritter märz zweitausendsechsundzwanzig' -> date. Ohne Jahr: dieses Jahr. Sonst None."""
    heute = heute or dt.date.today()
    woerter = _norm(text).split()
    monat_idx = next((i for i, w in enumerate(woerter) if w in MONATE), None)
    if monat_idx is None or monat_idx == 0:
        return None
    tag = ordinal("".join(woerter[:monat_idx])) or zahl(" ".join(woerter[:monat_idx]))
    jahr = zahl(" ".join(woerter[monat_idx + 1:])) if monat_idx + 1 < len(woerter) else heute.year
    try:
        return dt.date(jahr, MONATE[woerter[monat_idx]], tag)
    except (TypeError, ValueError):
        return None
