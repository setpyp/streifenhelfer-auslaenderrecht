"""Tests der Sprachsteuerung ohne Audio/GPIO.  Aufruf: python -m unittest discover -s pi -p "test_*.py" """
import datetime as dt
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fragen  # noqa: E402
import zahlen  # noqa: E402

HEUTE = dt.date(2026, 10, 20)


class Zahlen(unittest.TestCase):
    def test_zahlen(self):
        for text, wert in [("fünfundsechzig", 65), ("hundert zwanzig", 120), ("einhundertachtzig", 180),
                           ("neunzehn", 19), ("zweitausendsechsundzwanzig", 2026), ("dreissig", 30), ("65", 65)]:
            self.assertEqual(zahlen.zahl(text), wert, text)
        self.assertIsNone(zahlen.zahl("quatsch"))

    def test_ordinalzahlen(self):
        for text, wert in [("erster", 1), ("dritten", 3), ("sechster", 6), ("achter", 8), ("achtzehnter", 18),
                           ("zwanzigsten", 20), ("einunddreißigster", 31)]:
            self.assertEqual(zahlen.ordinal(text), wert, text)

    def test_datum(self):
        self.assertEqual(zahlen.datum("dritter märz zweitausendsiebenundzwanzig", HEUTE), dt.date(2027, 3, 3))
        self.assertEqual(zahlen.datum("einunddreißigster dezember", HEUTE), dt.date(2026, 12, 31))
        self.assertIsNone(zahlen.datum("dreißigster februar", HEUTE))
        self.assertIsNone(zahlen.datum("märz", HEUTE))


class Zuordnung(unittest.TestCase):
    def test_staaten(self):
        for text, wert in [("türkei", "Türkei"), ("amerika", "Vereinigte Staaten"), ("elfenbeinküste", "Côte d'Ivoire"),
                           ("die türkei", "Türkei"), ("unbekannt", "ungeklärt"), ("bosnien und herzegowina", "Bosnien und Herzegowina")]:
            self.assertEqual(fragen.waehle(text, fragen.STAATEN)[0], wert, text)
        self.assertIsNone(fragen.waehle("[unk]", fragen.STAATEN))

    def test_optionen_und_kommandos(self):
        self.assertEqual(fragen.waehle("im zug", fragen.ORTE)[0], "rail")
        self.assertEqual(fragen.waehle("kein dokument", fragen.DOKUMENTE)[0], "none")
        self.assertEqual(fragen.waehle("aufenthaltserlaubnis", fragen.TITEL)[0], "at_de")
        self.assertTrue(fragen.janein("ja richtig"))
        self.assertFalse(fragen.janein("nein"))
        self.assertIsNone(fragen.janein("vielleicht"))
        self.assertEqual(fragen.kommando("zurück"), "zurueck")
        self.assertIsNone(fragen.kommando("türkei"))

    def test_grammatik_nur_fuer_feste_antworten(self):
        nat = fragen.katalog(fragen.neuer_fall(HEUTE))[0]
        g = fragen.grammatik(nat)
        self.assertIn("türkei", g)
        self.assertEqual(g[-1], "[unk]")
        self.assertIsNone(fragen.grammatik(fragen.Frage("x", "", "zahl", "x")))


def dialog(antworten):
    """Dialog mit vorgegebenen Antworten; liefert (Fall, gesprochene Texte)."""
    gesagt, it = [], iter(antworten)
    fall = fragen.Dialog(gesagt.append, lambda g: next(it), heute=HEUTE).ablauf()
    return fall, gesagt


class Dialog(unittest.TestCase):
    LKW = ["türkei", "ja", "fünfundsechzig", "ja", "binnengrenze", "ja", "schengen", "ja", "pass", "ja",
           "kein titel", "ja", "zehn", "ja", "arbeit", "ja",
           "nein", "nein", "nein", "ja", "nein", "nein", "nein",          # asylum … identityUnclear (working = ja)
           "lkw fahrer bei spedition in istanbul",                       # beschaeftigung
           "fahrer", "ja", "ja", "ja", "ja", "ja",                         # Sonderregel + 4 Voraussetzungen
           "nein"]                                                         # keine Bemerkung

    def test_lkw_fahrer(self):
        fall, gesagt = dialog(self.LKW)
        self.assertEqual((fall["nat"], fall["age"], fall["place"], fall["from"], fall["title"], fall["days"]),
                         ("Türkei", 65, "internal_border", "schengen", "none", 10))
        self.assertTrue(fall["working"])
        s = fragen.fall_fuer_bewertung(fall)
        self.assertEqual(s["sonder"], {"id": "tr-fahrpersonal", "erfuellt": True, "offen": []})
        self.assertIn("Türkei. Richtig?", gesagt)

    def test_zurueck_und_korrektur(self):
        fall, _ = dialog(["syrien", "ja", "zurück", "türkei", "ja", "überspringen"] + ["überspringen"] * 40)
        self.assertEqual(fall["nat"], "Türkei")
        self.assertIsNone(fall["age"])

    def test_nicht_verstanden_dann_ueberspringen(self):
        fall, gesagt = dialog(["türkei", "ja", "bla", "bla", "bla"] + ["überspringen"] * 40)
        self.assertIsNone(fall["age"])
        self.assertIn("Frage wird übersprungen.", gesagt)

    def test_abbrechen(self):
        fall, gesagt = dialog(["abbrechen"])
        self.assertIsNone(fall)
        self.assertIn("Abgebrochen. Keine Daten gespeichert.", gesagt)

    def test_deutsche_werden_kurz_befragt(self):
        fall, gesagt = dialog(["deutschland", "ja", "vierzig", "ja", "zug", "ja", "kein dokument", "ja", "nein", "nein"])
        self.assertEqual(fall["iddoc"], "none")
        self.assertFalse(any("Aufenthaltstitel" in g for g in gesagt))


class Kurzfassung(unittest.TestCase):
    def test_kurzfassung(self):
        R = {"head": "Unerlaubter Aufenthalt", "find": [], "notify": [], "notes": [{"t": "x", "v": True}],
             "meas": [{"t": "Rechtsgrundlage", "lvl": "info"}, {"t": "Zurückschiebung prüfen", "lvl": "bad"}],
             "crim": [{"t": "Unerlaubter Aufenthalt", "lvl": "bad"}]}
        k = fragen.kurzfassung(R)
        self.assertIn("Ergebnis: Unerlaubter Aufenthalt.", k)
        self.assertIn("Zurückschiebung prüfen", k)
        self.assertNotIn("Rechtsgrundlage", k)
        self.assertIn("1 Punkte sind zu verifizieren", k)


PROC_DEVICES = '''I: Bus=0019 Vendor=0000 Product=0000 Version=0000
N: Name="vc4-hdmi"
H: Handlers=kbd event0
B: KEY=ffffc000000000 3ff

I: Bus=0003 Vendor=4c24 Product=3d3f Version=0100
N: Name="Generic AB13X USB Audio"
H: Handlers=kbd event2
B: KEY=1000000000000 7800000000 e000000000000 0
'''


class UsbSprechtaste(unittest.TestCase):
    def test_geraet_finden(self):
        import streifenhelfer_pi as sp
        self.assertEqual(sp.eingabegeraet("USB Audio", PROC_DEVICES), "/dev/input/event2")
        with self.assertRaises(RuntimeError):
            sp.eingabegeraet("Bluetooth", PROC_DEVICES)

    @unittest.skipIf(sys.platform.startswith("win"), "select() auf Pipes nur unter Linux")
    def test_halten_und_loslassen(self):
        import os
        import streifenhelfer_pi as sp
        lesen, schreiben = os.pipe()
        taste = sp.UsbTaste.__new__(sp.UsbTaste)
        taste.fd, taste.code, taste.gedrueckt = lesen, sp.KEY_PLAYPAUSE, False
        ereignis = lambda code, wert: sp.EREIGNIS.pack(0, 0, sp.EV_KEY, code, wert)
        self.assertFalse(taste.is_pressed)
        os.write(schreiben, ereignis(115, 1) + ereignis(115, 0))        # Lauter: ignorieren
        self.assertFalse(taste.is_pressed)
        os.write(schreiben, ereignis(sp.KEY_PLAYPAUSE, 1))
        taste.wait_for_press()
        self.assertTrue(taste.is_pressed)
        os.write(schreiben, ereignis(sp.KEY_PLAYPAUSE, 2))              # Wiederholung ändert nichts
        self.assertTrue(taste.is_pressed)
        os.write(schreiben, ereignis(sp.KEY_PLAYPAUSE, 0))
        taste.wait_for_release()
        self.assertFalse(taste.is_pressed)
        os.close(lesen), os.close(schreiben)


@unittest.skipUnless(shutil.which("node"), "Node.js nicht installiert")
class BewertungMitRegelwerk(unittest.TestCase):
    def bewerte(self, fall):
        r = subprocess.run(["node", str(Path(__file__).parent / "bewerten.mjs")], input=json.dumps(fragen.fall_fuer_bewertung(fall)),
                           capture_output=True, text=True, encoding="utf-8", check=True)
        return json.loads(r.stdout)

    def test_lkw_fahrer_wie_in_der_app(self):
        fall, _ = dialog(Dialog.LKW)
        R = self.bewerte(fall)
        self.assertEqual(R["head"], "Voraussichtlich rechtmäßig – Befreiung prüfen")
        self.assertFalse(any("Zurückweisung" in m["t"] for m in R["meas"]))

    def test_syrer_ohne_visum_an_der_grenze(self):
        fall, _ = dialog(["syrien", "ja", "dreißig", "ja", "binnengrenze", "ja", "schengen", "ja", "kein dokument", "ja",
                          "kein titel", "ja"] + ["überspringen"] * 40)
        R = self.bewerte(fall)
        self.assertEqual(R["head"], "Einreisevoraussetzungen nicht erfüllt")
        self.assertTrue(any("Zurückweisung" in m["t"] for m in R["meas"]))


if __name__ == "__main__":
    unittest.main()
