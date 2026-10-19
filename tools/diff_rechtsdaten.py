#!/usr/bin/env python3
"""
Vergleicht zwei Rechtsdatenpakete und schreibt einen Markdown-Bericht.

Aufruf:  python tools/diff_rechtsdaten.py ALT.json NEU.json [BERICHT.md]
Exit-Code: 0 = keine inhaltliche Änderung, 10 = Änderungen (PR sinnvoll), 1 = Fehler im neuen Paket
Inhaltlich = Wortlaut/Titel von Normen, Wegfall, Fassungen der Quellen. Reine Versions-/Datumsänderungen zählen nicht.
"""
import difflib
import json
import sys


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def short_diff(a, b, limit=40):
    lines = list(difflib.unified_diff(a.splitlines(), b.splitlines(), "alt", "neu", lineterm="", n=1))[2:]
    if len(lines) > limit:
        lines = lines[:limit] + [f"… ({len(lines) - limit} weitere Zeilen)"]
    return "\n".join(lines)


def main():
    alt, neu = load(sys.argv[1]), load(sys.argv[2])
    out_path = sys.argv[3] if len(sys.argv) > 3 else None
    A, N = alt.get("normen", {}), neu.get("normen", {})

    zit_geaendert, sonst_geaendert, weggefallen, neu_zitiert, entfallen, verloren = [], [], [], [], [], []
    for k, n in N.items():
        a = A.get(k)
        if a is None:
            if n.get("zitiert"):
                neu_zitiert.append(k)
            continue
        if a.get("text") and not (n.get("text") or "").strip():
            verloren.append(k)
            continue
        if (a.get("text"), a.get("titel")) != (n.get("text"), n.get("titel")):
            (zit_geaendert if n.get("zitiert") else sonst_geaendert).append(k)
        if n.get("weggefallen") and not a.get("weggefallen"):
            weggefallen.append(k)
    for k, a in A.items():
        if a.get("zitiert") and k not in N:
            entfallen.append(k)

    fassungen = []
    for law, g in neu.get("gesetze", {}).items():
        ga = alt.get("gesetze", {}).get(law, {})
        if g.get("fassung") and g.get("fassung") != ga.get("fassung"):
            fassungen.append(f"{law}: {ga.get('fassung', '–')} → {g['fassung']}")

    bericht_neu = neu.get("bericht", {})
    fehler = bericht_neu.get("weggefallen", []) + bericht_neu.get("nicht_gefunden", []) + [f"{k} (Wortlaut verloren)" for k in verloren]
    quellfehler = bericht_neu.get("quelle_fehler", []) + bericht_neu.get("wortlaut_behalten", [])

    L = [f"## Rechtsdaten-Update {alt['meta']['version']} → {neu['meta']['version']}", ""]
    if fehler:
        L += ["### ⚠️ Zitierte Normen weggefallen, nicht auffindbar oder ohne Wortlaut", "Regelwerk (`app/regelwerk.js`) bzw. Einlesen im Build prüfen:", ""]
        L += [f"- `{k}`" for k in fehler] + [""]
    if quellfehler:
        L += ["### ⚠️ Quellen nicht erreichbar (Wortlaut evtl. veraltet)", ""] + [f"- {q}" for q in quellfehler] + [""]
    if zit_geaendert:
        L += [f"### Geänderte, vom Regelwerk zitierte Normen ({len(zit_geaendert)})",
              "Fachlich prüfen, ob Aussagen im Regelwerk noch zutreffen:", ""]
        for k in sorted(zit_geaendert):
            L += [f"<details><summary><code>{k}</code> – {N[k].get('titel', '')}</summary>", "", "```diff",
                  short_diff(A[k].get("text", ""), N[k].get("text", "")), "```", "</details>", ""]
    if weggefallen:
        L += ["### Neu weggefallene Normen", ""] + [f"- `{k}`" for k in sorted(weggefallen)] + [""]
    if neu_zitiert or entfallen:
        L += ["### Geänderte Zitatbasis", ""] + [f"- neu zitiert: `{k}`" for k in neu_zitiert] + [f"- nicht mehr enthalten: `{k}`" for k in entfallen] + [""]
    if fassungen:
        L += ["### Neue konsolidierte EU-Fassungen", ""] + [f"- {f}" for f in fassungen] + [""]
    if sonst_geaendert:
        L += [f"### Sonstige geänderte Normen (nicht zitiert): {len(sonst_geaendert)}", "",
              ", ".join(f"`{k}`" for k in sorted(sonst_geaendert)[:80]) + (" …" if len(sonst_geaendert) > 80 else ""), ""]

    inhaltlich = bool(zit_geaendert or sonst_geaendert or weggefallen or neu_zitiert or entfallen or fassungen or fehler)
    if not inhaltlich:
        L += ["Keine inhaltlichen Änderungen."]
    L += ["", "---", "_Automatisch erzeugt. Vor dem Mergen fachlich prüfen; amtlich verbindlich sind allein BGBl. und ABl. EU._"]
    text = "\n".join(L)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)
    if fehler:
        return 1
    return 10 if inhaltlich else 0


if __name__ == "__main__":
    sys.exit(main())
