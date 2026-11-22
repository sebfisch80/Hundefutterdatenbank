#!/usr/bin/env python3
"""Match a brand project CSV against the official Open Pet Food Facts dump.

Streams the nightly CSV dump once and keeps rows whose EAN is in the project or
whose brand matches. The extract is cached in .cache/opff-<slug>.json, so the
merge can be repeated without downloading again (--refresh to re-download).

Merge rules: only empty fields are filled (names from other sources are never
overwritten); OPFF nutrient values are not imported (inconsistent units).
New rows are only added for brand matches clearly categorised as dry/wet dog food.
Data: Open Pet Food Facts, ODbL / DbCL (https://world.openpetfoodfacts.org/data).
"""

import argparse
import csv
import gzip
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DUMP = "https://static.openpetfoodfacts.org/data/en.openpetfoodfacts.org.products.csv.gz"
USER_AGENT = "Hundefutterdatenbank/1.0 (local research; ODbL attribution)"
KEEP = ("code", "brands", "product_name", "product_name_de", "quantity", "ingredients_text",
        "ingredients_text_de", "countries", "categories_tags")
FILL = ("quantity", "ingredients_text", "countries")


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def find_csv(slug):
    for path in sorted(ROOT.glob(f"{slug}-*.csv")):
        if re.fullmatch(rf"{re.escape(slug)}-\d+\.csv", path.name):
            return path
    raise SystemExit(f"Keine Projektdatei {slug}-<anzahl>.csv gefunden")


def extract(brand, eans):
    csv.field_size_limit(sys.maxsize)
    request = urllib.request.Request(DUMP, headers={"User-Agent": USER_AGENT})
    brand_key = brand.lower()
    hits = {}
    with urllib.request.urlopen(request, timeout=300) as response, gzip.GzipFile(fileobj=response) as gz:
        reader = csv.DictReader(io.TextIOWrapper(gz, encoding="utf-8", newline=""), delimiter="\t")
        for row in reader:
            code = (row.get("code") or "").strip()
            if code in eans or brand_key in (row.get("brands") or "").lower():
                hits[code] = {k: row.get(k) or "" for k in KEEP}
    return hits


def food_type(categories):
    categories = categories.lower()
    if "dry-dog-food" in categories:
        return "Trockenfutter"
    if "wet-dog-food" in categories:
        return "Nassfutter"
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brand", required=True)
    parser.add_argument("--refresh", action="store_true", help="Download the dump again")
    args = parser.parse_args()

    slug = slugify(args.brand)
    path = find_csv(slug)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames)
        rows = {r["ean"]: r for r in reader}
    for name in FILL + ("source_url", "source"):
        if name not in fields:
            fields.append(name)

    cache = ROOT / ".cache" / f"opff-{slug}.json"
    if cache.exists() and not args.refresh:
        hits = json.loads(cache.read_text(encoding="utf-8"))
    else:
        print("Lade OPFF-Dump (ca. 0,9 GB, gestreamt) …", file=sys.stderr, flush=True)
        hits = extract(args.brand, set(rows))
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(hits, ensure_ascii=False), encoding="utf-8")

    matched = added = 0
    for code, hit in hits.items():
        row = rows.get(code)
        if row is None:
            kind = food_type(hit["categories_tags"])
            if not kind or args.brand.lower() not in hit["brands"].lower():
                continue
            name = hit["product_name_de"] or hit["product_name"]
            row = {f: "" for f in fields}
            row.update(ean=code, brand=args.brand, animal="Hund", food_type=kind,
                       product_name=f"{args.brand} {name}".strip())
            rows[code] = row
            added += 1
            how = "neu"
        else:
            matched += 1
            how = "EAN"
        values = {
            "quantity": hit["quantity"],
            "ingredients_text": hit["ingredients_text_de"] or hit["ingredients_text"],
            "countries": hit["countries"],
        }
        for key, value in values.items():
            if value and not row.get(key):
                row[key] = value
        if not row.get("source_url"):
            row["source_url"] = f"https://world.openpetfoodfacts.org/product/{code}"
        if "Open Pet Food Facts" not in row.get("source", ""):
            row["source"] = f"{row.get('source', '')}; Open Pet Food Facts ({how})".lstrip("; ")

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for ean in sorted(rows):
            writer.writerow({f: rows[ean].get(f, "") for f in fields})

    from update_csv_filename import update_filename
    from build_dashboard_data import build

    final = update_filename(path)
    build()
    print(f"OPFF-Treffer im Dump: {len(hits)}; per EAN ergänzt: {matched}; neu: {added}; "
          f"Zeilen gesamt: {len(rows)} → {final.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
