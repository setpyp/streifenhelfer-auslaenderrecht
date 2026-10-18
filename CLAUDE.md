# Regeln für Agenten in diesem Repository

Streifenhelfer Aufenthalt: offlinefähige PWA (Entscheidungshilfe Aufenthaltsrecht für Polizeistreifen).
Live über GitHub Pages aus `app/`. Sprache in Code-Kommentaren, Commits und PRs: **Deutsch**.

## Aufbau
- `app/regelwerk.js` – Prüflogik (`evaluate(s)`), reine Funktionen, jede Aussage mit Normzitaten
- `app/index.html` – Oberfläche, Zitat-Parser, Weisungsimport, Norm-Dialog
- `app/rechtsdaten.js/.json` – **erzeugt** von `tools/build_rechtsdaten.py`, nie von Hand ändern
- `app/sw.js` – Service Worker (Netz zuerst, Offline-Fallback); neue App-Dateien in `ASSETS` eintragen
- `daten/` – Gesetzeskatalog und Länderliste (Quellen für das Paket)
- `tests/faelle.json` + `tests/run_tests.mjs` – Regressionstests mit fachlich festgelegten Erwartungen

## Pflichtprüfungen vor jedem PR
```
node tests/run_tests.mjs
python tools/build_rechtsdaten.py --pruefen
```
Beide müssen mit Exit-Code 0 enden.

## Harte Regeln
1. **Nur Pull Requests**, nie direkt auf `main` pushen, nie selbst mergen.
2. **Keine inhaltlichen Rechtsaussagen ändern** (Bewertungen, Maßnahmen, Normzitate in `regelwerk.js`),
   außer ein Rechtsdaten-Update macht es zwingend erforderlich. Dann: eigener PR, Begründung mit
   wörtlichem Zitat der geänderten Norm, Label `rechtsdaten`, Hinweis „fachliche Prüfung erforderlich“.
3. **Erwartungen in `tests/faelle.json` nie anpassen, um Tests grün zu bekommen.** Schlägt ein Test fehl,
   ist der Code falsch – oder die Rechtslage hat sich geändert (dann Regel 2 und im PR ausdrücklich erläutern).
4. Performance-Änderungen dürfen das Verhalten nicht ändern: gleiche Testergebnisse, Offline-Betrieb
   (alle Dateien in `sw.js`-`ASSETS`), Funktion unter `file://` (keine ES-Module/Fetch für Pflichtdaten).
5. Keine externen Laufzeit-Abhängigkeiten (CDNs, Tracking, Fonts). Die App muss vollständig offline laufen.
6. Niemals echte interne Weisungen, Personendaten oder Zugangsdaten ins Repository.
7. Keine Bibliotheken/Build-Ketten einführen, die das Projekt für Nicht-Entwickler schwer wartbar machen.
