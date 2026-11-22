# Hundefutterdatenbank

Dieses Projekt sammelt und vereinheitlicht öffentlich verfügbare Produktdaten
für Hundefutter. Die CSV-Dateien verbinden Produkttreffer aus Produktsuchen mit
Ergänzungen aus Herstellerangaben und offenen Produktdatenbanken. Ein lokales
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

## Skripte

Die Skripte liegen in `scripts/` und können aus jedem Arbeitsverzeichnis
gestartet werden:

- Such- und Exportskripte: sammeln Produkttreffer und führen sie anhand der
  EAN zusammen.
- `royalcanin_enrich.py`: ergänzt Royal-Canin-Produkte aus den erlaubten
  Produktseiten des Herstellers.
- `vetconcept_enrich.py`: ergänzt Vet-Concept-Analysewerte und Zutaten aus
  Herstellerseiten.
- `opff_match.py`: gleicht Produkt-EANs mit Open Pet Food Facts ab und füllt
  nur leere Felder.
- `update_csv_filename.py`: aktualisiert die Produktanzahl im CSV-Dateinamen.
- `build_dashboard_data.py`: erzeugt `scripts/dashboard-data.js` aus den
  Projekt-CSV-Dateien und `projects.json`.

Für eine neue Marke werden zunächst Produkttreffer gesammelt, danach
Herstellerangaben ergänzt und die EANs mit offenen Produktdatenbanken
abgeglichen. Die einzelnen Schritte sind in [Projekt.md](Projekt.md)
dokumentiert.

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

Die Sammlung nutzt öffentliche Produktsuchen, Herstellerseiten und offene
Produktdatenbanken. Verfügbarkeitsgrenzen und Servervorgaben werden respektiert;
es werden keine Zugangssperren oder Bot-Schutzmaßnahmen umgangen. Für Details zu
Abdeckung, Nutzungsbedingungen und bekannten Einschränkungen siehe
[Projekt.md](Projekt.md).
