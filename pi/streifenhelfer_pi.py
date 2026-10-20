#!/usr/bin/env python3
"""Sprachgesteuerter Streifenhelfer für Raspberry Pi (Prototyp).

Der Pi stellt die Fragen per Sprachausgabe (espeak-ng), hört NUR bei gedrückter Sprechtaste zu
(GPIO 17), erkennt die Antwort offline (Vosk) und bewertet mit app/regelwerk.js (Node.js).
Die vollständige Bewertung ist im Pi-Netz unter http://<pi>:8080/index.html?quelle=pi abrufbar.

Datenschutz: Audio wird nur während des Tastendrucks gelesen und nur im Arbeitsspeicher verarbeitet;
weder Audio noch erkannter Text werden gespeichert oder protokolliert.

  python3 pi/streifenhelfer_pi.py                 # Pi mit Sprechtaste, Mikrofon, Lautsprecher
  python3 pi/streifenhelfer_pi.py --simulation    # PC: Tastatur statt Taste/Mikrofon, Text statt Sprache
"""
import argparse
import json
import re
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import fragen

ROOT = fragen.ROOT
LETZTER_FALL = {"fall": None}  # nur im Arbeitsspeicher, für die Handy-Ansicht


def usb_geraet(befehl):
    """Erstes USB-Audiogerät aus 'arecord -l' bzw. 'aplay -l' als ALSA-Name, sonst 'default'."""
    try:
        ausgabe = subprocess.run([befehl, "-l"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return "default"
    # Zeilenformat: "card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]"
    m = re.search(r"^card (\d+):[^\n]*USB[^\n]*device (\d+)", ausgabe, re.M)
    return f"plughw:{m.group(1)},{m.group(2)}" if m else "default"


def bewerten(sachverhalt):
    r = subprocess.run(["node", str(ROOT / "pi" / "bewerten.mjs")], input=json.dumps(sachverhalt),
                       capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(r.stdout)


class Sprachausgabe:
    def __init__(self, geraet):
        self.geraet = geraet

    def __call__(self, text):
        espeak = subprocess.Popen(["espeak-ng", "-v", "de", "-s", "165", "--stdout", text], stdout=subprocess.PIPE)
        subprocess.run(["aplay", "-q", "-D", self.geraet], stdin=espeak.stdout)
        espeak.wait()


class Sprechtaste:
    """Mikrofon wird nur ausgelesen, solange die Taste gedrückt ist (arecord läuft nur dann)."""

    def __init__(self, modell, geraet, pin_taste, pin_led):
        from gpiozero import LED, Button
        from vosk import KaldiRecognizer, Model, SetLogLevel
        SetLogLevel(-1)
        self.model, self.Recognizer, self.geraet = Model(str(modell)), KaldiRecognizer, geraet
        self.taste, self.led = Button(pin_taste, pull_up=True, bounce_time=0.05), LED(pin_led)

    def warten(self):
        self.taste.wait_for_press()
        self.taste.wait_for_release()

    def __call__(self, grammatik):
        self.taste.wait_for_press()
        rec = (self.Recognizer(self.model, 16000, json.dumps(grammatik, ensure_ascii=False)) if grammatik
               else self.Recognizer(self.model, 16000))
        self.led.on()
        aufnahme = subprocess.Popen(["arecord", "-q", "-D", self.geraet, "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw"],
                                    stdout=subprocess.PIPE)
        try:
            while self.taste.is_pressed:
                daten = aufnahme.stdout.read(4000)  # 125 ms
                if not daten:
                    break
                rec.AcceptWaveform(daten)
        finally:
            aufnahme.terminate()
            aufnahme.wait()
            self.led.off()
        return json.loads(rec.FinalResult()).get("text", "")


class Simulation:
    def __call__(self, grammatik):
        return input("Antwort> ")

    def warten(self):
        input("[Enter = Sprechtaste für neuen Fall]")


class Handyansicht(SimpleHTTPRequestHandler):
    """Liefert die App aus app/ und unter /api/fall den letzten Fall (nur im Arbeitsspeicher)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT / "app"), **kw)

    def do_GET(self):
        if self.path.split("?")[0] != "/api/fall":
            return super().do_GET()
        body = json.dumps(LETZTER_FALL["fall"]).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keine Zugriffsprotokolle
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--simulation", action="store_true", help="Tastatur und Textausgabe statt Pi-Hardware")
    ap.add_argument("--einmal", action="store_true", help="nach einem Fall beenden")
    ap.add_argument("--modell", default=str(ROOT / "pi" / "modell"), help="Vosk-Modellordner")
    ap.add_argument("--mikrofon", default=None, help="ALSA-Aufnahmegerät (Standard: erstes USB-Gerät)")
    ap.add_argument("--lautsprecher", default=None, help="ALSA-Wiedergabegerät (Standard: erstes USB-Gerät)")
    ap.add_argument("--taste", type=int, default=17, help="GPIO der Sprechtaste")
    ap.add_argument("--led", type=int, default=27, help="GPIO der Anzeige 'Mikrofon aktiv'")
    ap.add_argument("--port", type=int, default=8080, help="Port der Handy-Ansicht (0 = aus)")
    a = ap.parse_args()

    if a.simulation:
        sprich, hoere = (lambda text: print(f"[Pi] {text}")), Simulation()
    else:
        sprich = Sprachausgabe(a.lautsprecher or usb_geraet("aplay"))
        hoere = Sprechtaste(a.modell, a.mikrofon or usb_geraet("arecord"), a.taste, a.led)

    if a.port:
        server = ThreadingHTTPServer(("0.0.0.0", a.port), Handyansicht)
        threading.Thread(target=server.serve_forever, daemon=True).start()

    while True:
        fall = fragen.Dialog(sprich, hoere).ablauf()
        LETZTER_FALL["fall"] = fragen.fall_fuer_bewertung(fall) if fall else None
        if fall:
            try:
                sprich(fragen.kurzfassung(bewerten(LETZTER_FALL["fall"])))
            except (OSError, subprocess.CalledProcessError, ValueError):
                sprich("Bewertung nicht möglich. Bitte Node.js prüfen. Der Fall ist auf dem Handy abrufbar.")
        if a.einmal:
            return
        sprich("Für einen neuen Fall die Sprechtaste drücken.")
        hoere.warten()


if __name__ == "__main__":
    main()
