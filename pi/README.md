# Sprachsteuerung auf dem Raspberry Pi (Prototyp)

Der Pi stellt die Fragen per Sprachausgabe, hört **nur bei gedrückter Sprechtaste** zu, erkennt die
Antworten **offline** und liest eine Kurzfassung der Bewertung vor. Die vollständige Bewertung
(mit Normen und Wortlauten) zeigt das Handy über das WLAN des Pi an.

> Prototyp – keine dienstliche Freigabe. Es spricht nur der Beamte; das Gespräch mit der kontrollierten
> Person wird nicht aufgenommen (§ 201 StGB). Audio und erkannter Text werden nicht gespeichert.

## Hardware

| Teil | Empfehlung |
|---|---|
| Rechner | Raspberry Pi 3 B/B+ mit Raspberry Pi OS Lite 64-bit (Bookworm), Powerbank |
| Audio – USB | USB-Headset nach USB Audio Class mit Kabelfernbedienung (getestet: „Generic AB13X USB Audio“) |
| Sprechtaste (Standard) | **Play/Pause-Taste am Headset-Kabel** – sie meldet echtes Drücken/Loslassen (Lauter/Leiser melden beim Halten nur Wiederholungen und eignen sich nicht) |
| Audio – Klinke | Headset/Lautsprechermikrofon mit 4-poligem 3,5-mm-Stecker (Belegung **CTIA**) an einem USB-Soundadapter mit Kombibuchse (Chip C-Media CM108/CM119). Die Klinkenbuchse des Pi ist **nur Ausgang**. |
| Sprechtaste (Alternative) | Drucktaster (Schließer) zwischen **GPIO 17 (Pin 11)** und **GND (Pin 9)**, Start mit `--taste-art gpio` |
| Anzeige (optional) | LED mit 330-Ω-Vorwiderstand zwischen **GPIO 27 (Pin 13)** und **GND (Pin 14)**, Start mit `--led 27` |

Welche Taste ein Headset meldet, zeigt `sudo evtest` (Gerät wählen, Taste halten): geeignet ist eine Taste, die
`value 1` beim Drücken und `value 0` erst beim Loslassen meldet. Andere Taste/Gerät: `--taste-code` / `--taste-geraet`.
Tasten analoger Handy-Headsets (Klinke) eignen sich **nicht**: Sie schließen nur die Mikrofonleitung kurz.
Ältere Headsets mit Belegung **OMTP** vertauschen Mikrofon und Masse und funktionieren am CTIA-Adapter nicht.

## Einrichtung

```
sudo apt install -y git
git clone https://github.com/setpyp/streifenhelfer-auslaenderrecht.git
cd streifenhelfer-auslaenderrecht
bash pi/install.sh --hotspot Streifenhelfer EinSicheresPasswort
```

Das Skript installiert espeak-ng, Node.js und Vosk, lädt das deutsche Sprachmodell (ca. 45 MB) und
richtet den Autostart ein. Mit `--hotspot` öffnet der Pi ein eigenes WLAN für das Handy.

Audiogeräte prüfen: `arecord -l` und `aplay -l`. Standardmäßig wird das erste USB-Gerät verwendet;
abweichend z. B. `--mikrofon plughw:1,0 --lautsprecher plughw:1,0` in der Dienstdatei
`/etc/systemd/system/streifenhelfer.service` ergänzen.

## Mikrofon-Test (vor dem ersten Einsatz)

1. Ohne Tastendruck darf kein Aufnahmeprozess laufen: `pgrep -a arecord` liefert **nichts**.
2. Sprechtaste drücken und halten: `pgrep -a arecord` zeigt **einen** Prozess (ggf. leuchtet die LED); nach dem Loslassen wieder keinen.
3. Hat das Gerät einen Stummschalter: stumm schalten, testweise aufnehmen und anhören – es darf nur Stille zu hören sein:
   ```
   arecord -D plughw:1,0 -f S16_LE -r 16000 -d 5 /tmp/test.wav && aplay /tmp/test.wav && rm /tmp/test.wav
   ```

## Bedienung

1. Der Pi sagt „Streifenhelfer bereit“ und stellt die erste Frage.
2. **Sprechtaste (Play/Pause) drücken und halten, antworten, loslassen.** Der Pi liest das Erkannte vor („Türkei. Richtig?“) – mit „ja“ oder „nein“ bestätigen.
3. Jederzeit möglich: **„wiederholen“**, **„zurück“**, **„überspringen“**, **„abbrechen“**.
4. Am Ende liest der Pi Ergebnis, wichtigste Maßnahmen und Straftatbestände vor.
5. Einzelheiten: Handy mit dem Pi-WLAN verbinden und `http://10.42.0.1:8080/index.html?quelle=pi` öffnen.

Gefragt wird wie im Formular: Staatsangehörigkeit, Alter, Ort, Einreise aus, Dokument, Aufenthaltstitel
(mit Gültigkeit, Visumstagen), Aufenthaltstage, Zweck, Ja/Nein-Feststellungen, Sonderregelungen mit
Voraussetzungen und eine optionale Bemerkung. Zahlen und Daten werden gesprochen
(„fünfundsechzig“, „dritter März zweitausendsiebenundzwanzig“).

## Ohne Pi ausprobieren

```
python pi/streifenhelfer_pi.py --simulation --einmal
```
Fragen erscheinen als Text, Antworten werden getippt. Für die vorgelesene Bewertung wird Node.js benötigt.
Auf dem Pi zeigt `--anzeigen` zusätzlich Fragen und erkannten Text in der Konsole (nur zum Testen, nicht im Dienst verwenden).

## Grenzen des Prototyps

- Sprachausgabe mit espeak-ng (gut verständlich, aber synthetisch). Eine natürlichere Stimme (z. B. Piper) lässt sich in `Sprachausgabe` austauschen.
- Das kleine Sprachmodell erkennt Ländernamen und feste Antworten zuverlässig, freien Text (Bemerkungen) nur eingeschränkt.
- Bei starkem Umgebungslärm ein Headset mit Nahbesprechungsmikrofon verwenden.
- Rechtsdaten und Regelwerk entsprechen dem Stand des Repositorys; zum Aktualisieren `git pull` und Dienst neu starten.
