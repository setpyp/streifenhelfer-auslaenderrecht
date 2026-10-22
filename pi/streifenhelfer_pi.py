#!/usr/bin/env python3
"""Sprachgesteuerter Streifenhelfer für Raspberry Pi (Prototyp).

Der Pi stellt die Fragen per Sprachausgabe (espeak-ng), hört NUR bei gedrückter Sprechtaste zu
(Standard: Play/Pause-Taste am USB-Headset, alternativ Taster an GPIO 17), erkennt die Antwort
offline (Vosk) und bewertet mit app/regelwerk.js (Node.js).
Die vollständige Bewertung ist im Pi-Netz unter http://<pi>:8080/index.html?quelle=pi abrufbar.

Datenschutz: Audio wird nur während des Tastendrucks gelesen und nur im Arbeitsspeicher verarbeitet;
weder Audio noch erkannter Text werden gespeichert oder protokolliert.

  python3 pi/streifenhelfer_pi.py                 # Pi mit USB-Headset (Play/Pause = Sprechtaste)
  python3 pi/streifenhelfer_pi.py --taste-art gpio --led 27   # Taster an GPIO 17, LED an GPIO 27
  python3 pi/streifenhelfer_pi.py --simulation    # PC: Tastatur statt Taste/Mikrofon, Text statt Sprache
"""
import argparse
import json
import os
import re
import select
import struct
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


EV_KEY, KEY_PLAYPAUSE = 1, 164
EREIGNIS = struct.Struct("llHHi")  # struct input_event (64-Bit-Linux): Zeit, Typ, Code, Wert


def eingabegeraet(name_teil, devices_text=None):
    """/dev/input/eventN des ersten Eingabegeräts, dessen Name name_teil enthält (aus /proc/bus/input/devices)."""
    text = devices_text if devices_text is not None else Path("/proc/bus/input/devices").read_text()
    for block in text.split("\n\n"):
        name = re.search(r'^N: Name="(.*)"', block, re.M)
        event = re.search(r"^H: Handlers=.*\b(event\d+)\b", block, re.M)
        if name and event and name_teil.lower() in name.group(1).lower():
            return f"/dev/input/{event.group(1)}"
    raise RuntimeError(f"Kein Eingabegerät mit '{name_teil}' im Namen gefunden – Headset angesteckt?")


class UsbTaste:
    """Taste eines USB-/Bluetooth-Geräts über /dev/input (evdev), gleiche Schnittstelle wie gpiozero.Button."""

    def __init__(self, pfad, code=KEY_PLAYPAUSE):
        self.fd, self.code, self.gedrueckt = os.open(pfad, os.O_RDONLY | os.O_NONBLOCK), code, False

    def _lesen(self, wartezeit):
        if not select.select([self.fd], [], [], wartezeit)[0]:
            return
        daten = os.read(self.fd, EREIGNIS.size * 64)
        for i in range(0, len(daten) - EREIGNIS.size + 1, EREIGNIS.size):
            _, _, typ, code, wert = EREIGNIS.unpack_from(daten, i)
            if typ == EV_KEY and code == self.code and wert in (0, 1):  # 2 = Tastenwiederholung
                self.gedrueckt = wert == 1

    @property
    def is_pressed(self):
        self._lesen(0)
        return self.gedrueckt

    def wait_for_press(self):
        while not self.is_pressed:
            self._lesen(None)

    def wait_for_release(self):
        while self.is_pressed:
            self._lesen(None)


class KeineLed:
    def on(self):
        pass

    def off(self):
        pass


class Sprechtaste:
    """Mikrofon wird nur ausgelesen, solange die Taste gedrückt ist (arecord läuft nur dann)."""

    def __init__(self, modell, geraet, taste, led=None):
        from vosk import KaldiRecognizer, Model, SetLogLevel
        SetLogLevel(-1)
        self.model, self.Recognizer, self.geraet = Model(str(modell)), KaldiRecognizer, geraet
        self.taste, self.led = taste, led or KeineLed()

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


def _anzeigen(sprich, hoere):
    """Testhilfe: Gesprochenes und Erkanntes zusätzlich in der Konsole ausgeben (nicht für den Dienst)."""
    def sprich2(text):
        print(f"[Pi] {text}", flush=True)
        sprich(text)

    class Hoere2:
        def __call__(self, grammatik):
            text = hoere(grammatik)
            print(f"[erkannt] {text!r}", flush=True)
            return text

        def warten(self):
            hoere.warten()

    return sprich2, Hoere2()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--simulation", action="store_true", help="Tastatur und Textausgabe statt Pi-Hardware")
    ap.add_argument("--einmal", action="store_true", help="nach einem Fall beenden")
    ap.add_argument("--modell", default=str(ROOT / "pi" / "modell"), help="Vosk-Modellordner")
    ap.add_argument("--mikrofon", default=None, help="ALSA-Aufnahmegerät (Standard: erstes USB-Gerät)")
    ap.add_argument("--lautsprecher", default=None, help="ALSA-Wiedergabegerät (Standard: erstes USB-Gerät)")
    ap.add_argument("--taste-art", choices=["usb", "gpio"], default="usb", help="Sprechtaste am Headset (usb) oder Taster (gpio)")
    ap.add_argument("--taste-geraet", default="USB Audio", help="Teil des Namens des Eingabegeräts (usb)")
    ap.add_argument("--taste-code", type=int, default=KEY_PLAYPAUSE, help="Tastencode (usb), Standard Play/Pause")
    ap.add_argument("--taste", type=int, default=17, help="GPIO des Tasters (gpio)")
    ap.add_argument("--led", type=int, default=0, help="GPIO einer LED 'Mikrofon aktiv' (0 = keine)")
    ap.add_argument("--anzeigen", action="store_true", help="Fragen und erkannten Text in der Konsole zeigen (nur zum Testen)")
    ap.add_argument("--port", type=int, default=8080, help="Port der Handy-Ansicht (0 = aus)")
    a = ap.parse_args()

    if a.simulation:
        sprich, hoere = (lambda text: print(f"[Pi] {text}")), Simulation()
    else:
        sprich = Sprachausgabe(a.lautsprecher or usb_geraet("aplay"))
        if a.taste_art == "usb":
            taste = UsbTaste(eingabegeraet(a.taste_geraet), a.taste_code)
        else:
            from gpiozero import Button
            taste = Button(a.taste, pull_up=True, bounce_time=0.05)
        led = None
        if a.led:
            from gpiozero import LED
            led = LED(a.led)
        hoere = Sprechtaste(a.modell, a.mikrofon or usb_geraet("arecord"), taste, led)
        if a.anzeigen:
            sprich, hoere = _anzeigen(sprich, hoere)

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
