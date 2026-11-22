# Hundefutterdatenbank

## Zweck

Dieses Verzeichnis sammelt Daten aus der öffentlichen NfE-Pro-Produktsuche für
die Marke Vet-Concept. Die Daten wurden nach Tierart und Futtertyp gefiltert
und anschließend über mehrere Sortierreihenfolgen dedupliziert.

## Dateien

Im Projektordner (Daten und Dashboard):

- `vet-concept-176.csv`: kombinierte CSV mit 176 eindeutigen Vet-Concept-EANs.
- `dashboard.html`: Projekt-Dashboard (per Doppelklick öffnen).
- `projects.json`: Quellenstatus je Projekt.
- `.cache/`: zwischengespeicherte Herstellerseiten.

In `scripts/` (relative Pfade beziehen sich immer auf den Projektordner,
die Skripte können von jedem Verzeichnis aus gestartet werden):

- `nfepro_export.py`: skriptgesteuerte Suche und CSV-Extraktion.
- `nfepro_collect.py`: sammelt eine Marke komplett aus NfE-Pro (alle
  Sortierungen, Nass + Trocken, nur exakte Marke) in die eine Projektdatei;
  wartet bei HTTP 429 die vom Server genannte Zeit ab.
- `opff_match.py`: gleicht eine Projektdatei mit dem Open-Pet-Food-Facts-Dump
  ab (füllt nur leere Felder, Auszug in `.cache/opff-<marke>.json`).
- `royalcanin_enrich.py`: ergänzt Royal Canin aus royalcanin.com/de
  (alle Packungsgrößen mit eigener EAN, Analysewerte, Zusammensetzung).
- `update_csv_filename.py`: aktualisiert den Zahlenanteil im Dateinamen
  automatisch anhand der Produktzeilen.
- `vetconcept_enrich.py`: ergänzt Analysewerte und Zutaten aus vet-concept.com
  (Sitemap + Produktseiten, 3 s Pause, Seiten-Cache in `.cache/`).
- `build_dashboard_data.py`: erzeugt `scripts/dashboard-data.js`.
- `dashboard-data.js`: Datenpaket, das `dashboard.html` beim Öffnen lädt.
- `dashboard.py`: optionaler lokaler Server für das Dashboard.

Solange nach derselben Marke gesucht wird, wird keine separate Ergebnisdatei
angelegt. Zusätzliche Datenquellen werden in die vorhandene Herstellerdatei
gemergt.

## Dashboard

**Ohne Server (Standard, auch Safari):** `dashboard.html` per Doppelklick
öffnen. Die Projekte aus dem eigenen Ordner erscheinen sofort.

- Grundlage ist `scripts/dashboard-data.js`: Sie bündelt alle
  `<marke>-<anzahl>.csv` und `projects.json`. (Browser dürfen aus einer
  lokal geöffneten Seite keine CSV-Dateien lesen, aber ein Skript laden.)
- Die Datei wird automatisch neu erzeugt durch `vetconcept_enrich.py` und
  `update_csv_filename.py` (auch im `--watch`-Modus bei jeder CSV-Änderung).
  Manuell: `python3 scripts/build_dashboard_data.py`. Der Datenstand steht oben rechts.
- „Anderen Ordner wählen“ liest im Einzelfall einen beliebigen Ordner direkt
  ein. Fehlt `scripts/dashboard-data.js`, fragt das Dashboard automatisch nach dem Ordner.
- Jede Datei `<marke>-<anzahl>.csv` direkt im Ordner ist ein Projekt;
  Unterordner (z. B. `.cache/`) werden ignoriert.
- Pro Projekt und Quelle wird der Status `offen`, `in Bearbeitung` oder
  `erledigt` mit Notiz geführt. Änderungen speichert der Browser lokal; der
  Button „projects.json speichern (n)“ zeigt ungespeicherte Änderungen und lädt
  die aktualisierte `projects.json` herunter. Diese Datei danach aus dem
  Download-Ordner in den Projektordner verschieben (vorhandene ersetzen).
- Safari merkt sich manuell gewählte Ordner nicht; dafür erneut „Anderen
  Ordner wählen“ nutzen.
- Gesamtzustand: alle Pflichtquellen erledigt → `erledigt`; mindestens eine
  begonnen → `in Bearbeitung`; sonst `offen`. Optionale Quellen (GS1) zählen
  nicht mit.
- Kennzahlen: Produktanzahl, Futtertypen, Zeilen mit Analysewerten, Zeilen je
  Quelle (aus der Spalte `source`).
- CSV-Vorschau mit Volltextsuche, Futtertyp-Filter und Spaltenauswahl.
- Neue Quellen werden in `projects.json` unter `sources` ergänzt.

**Optional mit Server:** `python3 scripts/dashboard.py` → `http://127.0.0.1:8899`.
Dann werden Statusänderungen direkt in `projects.json` geschrieben und die
Ansicht aktualisiert sich alle 30 Sekunden.

## Weitere Datenbanken

### Open Pet Food Facts

Der offizielle nächtliche CSV-Dump wurde über
`https://static.openpetfoodfacts.org/data/en.openpetfoodfacts.org.products.csv.gz`
gestreamt. Die EANs wurden mit `vet-concept-176.csv` abgeglichen.

- Gefundene gemeinsame EANs: 6
- Diese 6 EANs wurden in `vet-concept-176.csv` eingetragen
- Die Quelle ist pro Zeile in `source_url` und `source` vermerkt
- Lizenz: ODbL für die Datenbank und DbCL für den Datenbankinhalt
- Produktbilder: Creative Commons Attribution-ShareAlike
- Quelle und Bedingungen:
  `https://world.openpetfoodfacts.org/data`

### Öffentliche Händlersuchen

- Zooplus: öffentliche Hundekategorie erreichbar, aber kein Vet-Concept-Markenpfad
  oder freier Export gefunden.
- Fressnapf: öffentliche Suche lieferte keinen Vet-Concept-Treffer.
- Futterhaus: öffentlicher Suchpfad lieferte keinen Vet-Concept-Treffer.

Die Händlerdaten werden nur manuell oder über offizielle Partner-/Produktfeeds
erfasst. Keine Bot-Schutzmaßnahmen oder Zugangssperren werden umgangen.

### Strukturierte Quellenbewertung (Stand 21.11.2026)

Prüfkriterien je Quelle: Erreichbarkeit, Abdeckung (Test-EANs `4250449901680`,
`4250449900027`, `4250449914819`), Datenfelder, Zugriffsart, Nutzungsbedingungen
(robots.txt, Lizenz, Bot-Schutz).

| Quelle | Abdeckung Vet-Concept | Felder | Zugriff | Bedingungen | Bewertung |
|---|---|---|---|---|---|
| vet-concept.com (Hersteller) | vollständiger Katalog, 370 Hunde-Produktseiten in der Sitemap | 1 EAN (`gtin13`) pro Produktfamilie, Analysewerte, Zutaten | Sitemap + Produktseiten (JSON-LD) | robots.txt erlaubt `/p/`, Suche gesperrt | **empfohlen** zur Anreicherung |
| Open Pet Food Facts | 6 von 176 EANs | EAN, Zutaten, Menge | Dump + API | ODbL/DbCL | genutzt |
| GS1 Verified | ohne Konto nicht prüfbar | verifizierte GTIN, Markeninhaber | Konto/Lizenz | lizenzpflichtig | optional zur EAN-Validierung |
| OpenGTIN-DB | Test-EAN nicht gefunden | EAN, Name | Web, API mit User-ID | GNU FDL | geringer Nutzen |
| UPCitemdb | 0 von 2 Test-EANs | EAN, Titel, Marke | Trial-API 100/Tag | API-Bedingungen | kein Nutzen |
| EAN-Search.org | Test-EAN nicht gefunden | EAN, Name | kostenpflichtige API | API-Lizenz | kein Nutzen |
| Open Food Facts | Test-EAN nicht gefunden | EAN, Nährwerte | Dump + API | ODbL | kein Nutzen (Tierfutter in OPFF) |
| Napfcheck | – | Bewertungen, Zutaten | – | robots.txt `Disallow: /` | **ausgeschlossen** |
| Barcode Lookup | – | – | Bot-Verifikation (HTTP 403) | Schutzmaßnahme aktiv | **ausgeschlossen** |
| zooplus.de | Produktseiten enthalten EAN, Analysewerte, Zusammensetzung | – | robots.txt offen, aber `agents.md`: „`llms.txt`/`llms-full.txt` statt Seiten zu scrapen“ (diese enthalten keine Produktdaten) | AGB verbieten Web-Scraping und Entnahme/Weiterverwendung wesentlicher Datenbankteile | **ausgeschlossen** für automatisierte Abfrage; möglich nur über offiziellen Partner-/Affiliate-Produktfeed oder Datenlizenz |
| Futterverzeichnis | – | – | nicht erreichbar | – | entfällt |

Hinweis zum Hersteller: Die Produktseiten enthalten nur die EAN der
Hauptvariante. Weitere Packungsgrößen (z. B. 600 g, 3 kg, 10 kg) haben eigene
EANs, die dort nicht ausgewiesen sind. Der Hersteller eignet sich daher vor
allem zum Ergänzen der Analysewerte, die in den NfE-Pro-Daten leer sind.

## Extraktionsvorgang

1. Auf `https://www.nfepro.de/` wurde nach `vet-concept` gesucht.
2. Die API-Suche wurde mit Tierart `Hund` und Futtertyp `Nassfutter` ausgeführt.
3. Die API begrenzte jede Sortierung auf drei Seiten mit jeweils 20 Treffern.
4. Die Sortierungen `Beste Treffer`, `Beliebteste`, `Neu hinzugefügt`,
   `NfE niedrig → hoch`, `NfE hoch → niedrig` und `Produktname A–Z` wurden
   einzeln abgefragt.
5. Alle gefundenen Datensätze wurden anhand ihrer eindeutigen EAN zusammengeführt.
6. Danach wurden alle Nass- und Trockenfutter-Sortierungen über die EAN
   zusammengeführt und dedupliziert.

## Aktueller Datenstand

- Nassfutter: 72 eindeutige EANs nach Mehrfach-Sortierung.
- Trockenfutter: 104 eindeutige EANs nach Mehrfach-Sortierung.
- Kombinierte Tabelle: 176 eindeutige EANs ausschließlich der Marke Vet-Concept.
- Analysewerte (Rohprotein, Rohfett, Rohfaser, Rohasche, bei Nassfutter auch
  Feuchtigkeit) und Zutaten vom Hersteller für alle 176 Produkte: 44 per EAN,
  132 per Produktfamilie (nur bei gleichem Futtertyp). Kontrolle bei der
  Übernahme: Bei allen 82 Zeilen mit vollständigen Werten passten die
  Herstellerwerte zum damaligen NfE-Wert von NfE-Pro (Abweichung ≤ 1,5
  Prozentpunkte).
- Der NfE-Wert selbst wird nicht erfasst (Spalte `nfe` entfernt).
- Energie: `energie_kcal_100g` und `energie_kj_100g` (1 kcal = 4,184 kJ) aus der
  Herstellerangabe „Umsetzbare Energie (berechnet)“ – für alle 176 Produkte.
  Kontrolle per Atwater-Rechnung (3,5/8,5/3,5 kcal je g Protein/Fett/NfE):
  Abweichung im Median 6 %, maximal 9 %.
- Trockenfutter-Seiten nennen keine Feuchtigkeit.
- Kategorien „Kauartikel“, „Nahrungsergänzung“, „Protein Selektion“,
  „Gemüse & Cerealien“ und „Angebote“ sind Snacks/Ergänzungen und wurden nicht
  aufgenommen.
- `vetconcept_enrich.py` kann jederzeit erneut laufen: Herstellerfelder werden
  neu aufgebaut, bereits geladene Seiten kommen aus `.cache/` (kein erneuter
  Abruf).

Die Mehrfach-Sortierung erhöht die Abdeckung, garantiert aber keine
Vollständigkeit, solange die API begrenzte oder gesperrte Ergebnisse liefert.

## Export-Skript

Das Skript unterstützt Hersteller, Tierart, Futtertyp und Sortierung:

```bash
python3 scripts/nfepro_export.py \
  --q vet-concept \
  --animal dog \
  --food-type dry \
  --sort nfe_asc \
  --output vet-concept-dog-dry.csv
```

Unterstützte Sortierungen sind `relevance`, `popular`, `newest`, `nfe_asc`,
`nfe_desc` und `name_asc`.

## Dateiname automatisch aktualisieren

Nach jeder Aktualisierung der CSV kann die Dateinummer neu berechnet werden:

```bash
python3 scripts/update_csv_filename.py "vet-concept-*.csv"
```

Für kontinuierliche Aktualisierung:

```bash
python3 scripts/update_csv_filename.py "vet-concept-*.csv" --watch
```

## Pflicht für zukünftige Suchen

Für jede Hersteller- oder Produktnamensuche (je Futtertyp) gilt:

1. `relevance` - Beste Treffer: immer.
2. `popular` - Beliebteste und `newest` - Neu hinzugefügt: nur wenn die Suche
   mehr als 60 Treffer meldet („60+“, API-Feld `limited`), da NfE-Pro pro
   Sortierung höchstens 60 Einträge (3 Seiten à 20) ausgibt.

Weitere Sortierungen (`nfe_asc`, `nfe_desc`, `name_asc`) werden nicht mehr
verwendet. Alle Treffer werden ausschließlich anhand der EAN dedupliziert.
`nfepro_collect.py` setzt das standardmäßig so um (20 s zwischen Anfragen,
60 s zwischen Sortierungen, Zwischenspeichern nach jeder Sortierung).

## Hinweise

- Die Website kann Suchanfragen mit HTTP 429 drosseln.
- Die API kennzeichnet begrenzte Ergebnisse mit `limited: true`.
- `60+ Treffer` bedeutet nicht zwingend genau 60 vollständige Ergebnisse.
- Die CSV verwendet deutsche Filterwerte: `Hund`, `Nassfutter` und
  `Trockenfutter`. Technische API-Codes wie `dog`, `wet` und `dry` werden beim
  Export übersetzt.
- Mehrere Sortierungen erhöhen die Abdeckung, garantieren aber keine Vollständigkeit,
  solange die Serverbegrenzung besteht.

## Neue Marke anlegen (Ablauf, Beispiel Royal Canin)

```bash
python3 scripts/nfepro_collect.py --brand "Royal Canin"   # 1. NfE-Pro
python3 scripts/royalcanin_enrich.py                       # 2. Hersteller (markenspezifisch)
python3 scripts/opff_match.py --brand "Royal Canin"        # 3. Open Pet Food Facts
```

- Ergebnis immer in genau einer Datei `<marke>-<anzahl>.csv`.
- Nur Treffer mit passender Marke werden übernommen.
- Quellenstatus in `projects.json` bzw. im Dashboard pflegen.

### Royal Canin: Herstellerquelle

royalcanin.com erlaubt Produktseiten laut robots.txt (gesperrt sind nur
`/api/`, Warenkorb, Checkout und „view-all“-Seiten, die nicht genutzt werden).
Die deutsche Sitemap `sitemap-products.xml` listet die Produktseiten; jede
Produktseite enthält alle Packungsgrößen mit eigener EAN, die Kategorie
(Trocken/Nass/Snack/Ergänzung), die analytischen Bestandteile und die
Zusammensetzung. Zuordnung daher exakt per EAN; fehlende Nass-/Trockenfutter-
EANs werden als neue Zeilen ergänzt, Snacks/Ergänzungen/Milchersatz nicht.
Energie kommt aus dem strukturierten Feld `reference_energy_value_per_weight`
(kcal/kg, umgerechnet auf kcal/100 g und kJ/100 g).
