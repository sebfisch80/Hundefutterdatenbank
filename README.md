# Hundefutterdatenbank

Dieses Projekt sammelt und vereinheitlicht öffentlich verfügbare Produktdaten
für Hundefutter. Die CSV-Dateien verbinden Produkttreffer aus NfE-Pro mit
Ergänzungen aus Herstellerangaben und Open Pet Food Facts (OPFF). Ein lokales
Dashboard macht die Daten und den Bearbeitungsstand der Quellen übersichtlich.

## Datenbestand

| Datei | Inhalt |
|---|---|
| `vet-concept-176.csv` | 176 eindeutige Vet-Concept-Produkte |
| `royal-canin-493.csv` | 493 eindeutige Royal-Canin-Produkte |

Die CSV-Dateien enthalten unter anderem EAN, Produktname, Tierart, Futtertyp,
Quelle, Analysewerte, Zutaten, Packungsgröße und Hersteller-URL. Leere Felder
bedeuten, dass der jeweilige Wert in den abgefragten Quellen nicht verfügbar
war. Die Daten sind eine Sammlung öffentlich zugänglicher Angaben und keine
Garantie auf einen vollständigen Produktkatalog.

## Dashboard

`dashboard.html` lässt sich direkt im Browser öffnen. Es liest das gebündelte
Datenpaket `scripts/dashboard-data.js`; ein Server ist für die normale Ansicht
nicht erforderlich. Änderungen am Quellenstatus können lokal im Browser
gespeichert werden. Die aktualisierte `projects.json` lässt sich anschließend
herunterladen und in den Projektordner übernehmen.

Optional kann das Dashboard mit einem lokalen Server geöffnet werden:

```bash
python3 scripts/dashboard.py
```

Danach im Browser `http://127.0.0.1:8899` öffnen. Im Servermodus werden
Statusänderungen direkt in `projects.json` gespeichert.

## Skripte

Die Skripte liegen in `scripts/` und können aus jedem Arbeitsverzeichnis
gestartet werden:

- `nfepro_collect.py`: sammelt eine Marke aus NfE-Pro und führt Treffer nach
  EAN zusammen. Bei HTTP 429 wird die vom Server angegebene Wartezeit
  eingehalten.
- `royalcanin_enrich.py`: ergänzt Royal-Canin-Produkte aus den erlaubten
  Produktseiten des Herstellers.
- `vetconcept_enrich.py`: ergänzt Vet-Concept-Analysewerte und Zutaten aus
  Herstellerseiten.
- `opff_match.py`: gleicht Produkt-EANs mit Open Pet Food Facts ab und füllt
  nur leere Felder.
- `nfepro_export.py`: exportiert eine NfE-Pro-Suche.
- `update_csv_filename.py`: aktualisiert die Produktanzahl im CSV-Dateinamen.
- `build_dashboard_data.py`: erzeugt `scripts/dashboard-data.js` aus den
  Projekt-CSV-Dateien und `projects.json`.

Beispiel für eine neue Marke:

```bash
python3 scripts/nfepro_collect.py --brand "Markenname"
python3 scripts/opff_match.py --brand "Markenname"
```

Die Herstelleranreicherung wird über das passende Hersteller-Skript ausgeführt.
Beispiele und Hinweise zu Suchfiltern, Datenquellen, Einschränkungen und dem
Royal-Canin-Ablauf stehen in [Projekt.md](Projekt.md).

## Dateien und Cache

- `projects.json` enthält den Status der Datenquellen je Projekt.
- `scripts/dashboard-data.js` ist das vom Dashboard geladene Datenpaket und
  kann mit dem Build-Skript neu erstellt werden.
- `.cache/` enthält lokale Zwischenspeicher für abgefragte Quelldaten. Der
  Ordner wird nicht versioniert.

## Datenquellen und verantwortungsvolle Nutzung

Die Sammlung nutzt NfE-Pro, die jeweiligen Herstellerseiten und Open Pet Food
Facts. Verfügbarkeitsgrenzen und Servervorgaben werden respektiert; es werden
keine Zugangssperren oder Bot-Schutzmaßnahmen umgangen. Für Details zu
Abdeckung, Nutzungsbedingungen und bekannten Einschränkungen siehe
[Projekt.md](Projekt.md).
