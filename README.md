# Streifenhelfer Aufenthalt

Offlinefähige Entscheidungshilfe zur aufenthaltsrechtlichen Bewertung bei Kontrollen.
**Keine verbindliche Rechtsauskunft.**

## Aufbau

| Pfad | Inhalt |
|---|---|
| `app/` | auszuliefernde Web-App (PWA): `index.html` (Oberfläche + Regelwerk), `rechtsdaten.js/.json` (erzeugt), `sw.js` (Offline-Cache) |
| `daten/gesetze.json` | Katalog der öffentlichen Rechtsquellen (Quelle, Aliase, ob vollständig aufzunehmen) |
| `daten/laender.json` | Staaten nach Visumkategorie (VO (EU) 2018/1806) mit Hinweisen |
| `tools/build_rechtsdaten.py` | erzeugt das Rechtsdatenpaket aus amtlichen Quellen und prüft die Zitate |
| `weisungen-muster/` | Muster für interne Weisungspakete |
| `WEISUNGEN-FORMAT.md` | Format und Serveranforderungen für interne Weisungen |

## Rechtsdaten aktualisieren

```
python tools/build_rechtsdaten.py
```

- Lädt die zitierten Normen (und Kerngesetze vollständig) von gesetze-im-internet.de und
  EUR-Lex (neueste konsolidierte Fassung).
- Prüft jedes Zitat im Regelwerk: **Exit-Code 1**, wenn eine zitierte Norm weggefallen oder
  nicht auffindbar ist. Dann vor der Auslieferung das Regelwerk anpassen.
- Setzt die Cache-Version im Service Worker, damit Geräte das neue Paket laden.
- Die App warnt, wenn das Paket älter als 120 Tage ist.

Für den Betrieb empfiehlt sich ein regelmäßiger Lauf (z. B. wöchentlich) mit fachlicher
Freigabe vor dem Ausrollen.

## Veröffentlichung (GitHub Pages)

Live: **https://setpyp.github.io/streifenhelfer-auslaenderrecht/**

Jeder Push auf `main` veröffentlicht den Ordner `app/` automatisch
(Workflow [.github/workflows/pages.yml](.github/workflows/pages.yml)). Update-Ablauf:

```
python tools/build_rechtsdaten.py
git add -A
git commit -m "Rechtsdaten aktualisiert"
git push
```

Installierte Apps holen sich die neue Fassung beim nächsten Öffnen mit Netz.
Icons neu erzeugen: `powershell -File tools/make_icons.ps1`.

## Automatisierung

| Was | Wann | Ergebnis |
|---|---|---|
| [Rechtsdaten-Update](.github/workflows/rechtsdaten-update.yml) | montags 03:00 UTC | PR mit Änderungsbericht (geänderte zitierte Normen als Diff), nur bei inhaltlichen Änderungen |
| Claude-Agent (Cloud-Routine) | montags nach dem Update | prüft den Rechtsdaten-PR fachlich, misst/optimiert Performance, Wartung – alles als PR |
| [Dependabot](.github/dependabot.yml) | wöchentlich | PRs für veraltete GitHub-Actions |
| [CI](.github/workflows/ci.yml) | bei jedem Push/PR | Regressionstests (`tests/`) und Zitatprüfung |

Regeln für Agenten: [CLAUDE.md](CLAUDE.md). Gemergt wird immer von Hand nach Prüfung.

## Betrieb

- **Webserver (empfohlen):** Inhalt von `app/` über HTTPS ausliefern → installierbar, offline per Service Worker.
- **Einzeldatei:** `streifenhelfer-offline.html` (wird beim Veröffentlichen erzeugt, Download unter
  ⚙ in der App bzw. `…/streifenhelfer-offline.html`) enthält alles in einer Datei, ohne automatische
  Aktualisierung. Nur `index.html` allein zu kopieren reicht **nicht** – die App braucht
  `regelwerk.js` und `rechtsdaten.js` daneben.
- Empfohlene HTTP-Header: `Content-Security-Policy` (u. a. `connect-src` auf App- und Weisungsserver beschränken).
