# Format für interne Weisungen

Die App liefert **keine** internen Weisungen aus. Sie lädt sie zur Laufzeit von einem
internen Server oder aus Dateien auf dem Gerät (⚙ → Interne Weisungen). Ein Muster liegt in
[weisungen-muster/](weisungen-muster/).

## Weisungspaket (`*.json`)

```json
{
  "typ": "streifenhelfer-weisungen",
  "meta": {
    "bezeichnung": "Weisungen Grenzpolizeiliche Aufgaben",
    "herausgeber": "Dienststelle / Referat",
    "stand": "2026-10-01",
    "version": "7",
    "einstufung": "VS-NfD"
  },
  "weisungen": [
    {
      "id": "eindeutige-kennung",
      "titel": "Kurztitel",
      "fundstelle": "Erlass/Verfügung, Datum, Ziffer",
      "gueltigAb": "2026-06-12",
      "gueltigBis": null,
      "einstufung": "VS-NfD",
      "normen": ["§ 57 Abs. 2 AufenthG", "Art. 14 SGK", "AsylG § 18"],
      "stichworte": ["Zurückschiebung"],
      "text": "Wortlaut oder Kurzfassung (reiner Text, Zeilenumbrüche mit \\n)",
      "link": "https://intranet…/dokument"
    }
  ]
}
```

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `typ` | ja | immer `streifenhelfer-weisungen` |
| `weisungen[].id`, `.titel` | ja | eindeutige Kennung, Anzeigetitel |
| `normen` | empfohlen | Bezugsnormen in üblicher Zitierweise; die App ordnet die Weisung damit allen Bewertungspunkten zu, die dieselbe Norm zitieren (Kennzeichnung ◆). Nur Gesetzesname (z. B. `"AMMR"`) = Bezug auf das ganze Gesetz. |
| `gueltigAb` / `gueltigBis` | nein | ISO-Datum; außerhalb des Zeitraums wird die Weisung ausgegraut und nicht als Treffer gezählt |
| `text` | nein | wird als reiner Text angezeigt (kein HTML) |
| `link` | nein | Verweis ins Intranet (nur online nutzbar) |

Erkannte Gesetzesnamen: siehe `aliase` in [daten/gesetze.json](daten/gesetze.json). Paragrafen
und Artikel werden ohne Absatz zugeordnet („§ 57 Abs. 2“ → § 57).

## Mehrere Dateien: Index

Zeigt die Server-URL auf einen Index, lädt die App alle genannten Dateien (Pfade relativ zum Index):

```json
{ "typ": "streifenhelfer-weisungen-index", "dateien": ["grenze.json", "asyl.json"] }
```

## Anforderungen an den internen Server

- Auslieferung über **HTTPS** (die App lädt mit `credentials: "include"`, d. h. vorhandene
  Anmeldung/SSO-Cookies oder Client-Zertifikate des Geräts werden mitgesendet).
- Läuft die App auf einem anderen Host als der Weisungsserver, muss dieser CORS erlauben:
  `Access-Control-Allow-Origin: <Herkunft der App>` und `Access-Control-Allow-Credentials: true`.
- Empfohlen: App und Weisungen vom selben internen Host ausliefern, dann entfällt CORS.

## Speicherung auf dem Gerät

- Mit „auf diesem Gerät speichern“ landen die Pakete in der IndexedDB des Browsers. Sie
  sind dann offline verfügbar, liegen aber **unverschlüsselt im Browserprofil**. Für VS-NfD
  nur auf dienstlich verwalteten Geräten mit Geräteverschlüsselung (MDM) zulässig, nach
  Freigabe durch die IT-Sicherheit.
- Ohne Speicherung gelten die Weisungen nur bis zum Schließen der App.
- „Entfernen“ löscht ein Paket vom Gerät.

## Offene Punkte

- **Signatur:** Pakete werden derzeit nur auf Format geprüft, nicht auf Herkunft. Für den
  Einsatz sollte jedes Paket signiert und in der App gegen einen hinterlegten öffentlichen
  Schlüssel geprüft werden (WebCrypto, ECDSA).
- **Ordner automatisch neu einlesen:** Ordner werden derzeit per Auswahl geladen. Auf
  verwalteten Geräten kann alternativ der Weisungsordner über einen lokalen Webserver oder
  per MDM-Synchronisation bereitgestellt werden.
