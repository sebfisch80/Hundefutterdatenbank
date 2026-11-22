#!/usr/bin/env python3
"""Enrich/extend the Royal Canin project CSV from royalcanin.com/de product pages.

Only sitemap and product pages are fetched (robots.txt disallows /api/, cart,
view-all pages - none of these are used), with a fixed pause between requests
and a local page cache. Each product page lists all pack sizes with their own
EAN plus category, analytical constituents and composition, so rows are matched
exactly by EAN. Missing dry/wet EANs are added as new rows.
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITEMAP = "https://www.royalcanin.com/de/de-de/sitemap/sitemap-products.xml"
USER_AGENT = "Hundefutterdatenbank/1.0 (private research; slow crawl)"
SLUG = "royal-canin"
FOOD_TYPES = {"dry": "Trockenfutter", "wet": "Nassfutter"}
NUTRIENTS = {
    "rohprotein": r"Rohprotein|Protein|Crude protein",
    "rohfett": r"Rohfett|Fettgehalt|Fett|Fat content|Crude fat|Fat",
    "rohfaser": r"Rohfaser|Crude fibres?",
    "rohasche": r"Rohasche|Crude ash",
    "feuchtigkeit": r"Feuchtigkeit|Moisture",
}
SMALL_WORDS = {"für", "in", "mit", "und", "ohne", "von", "zur", "zum", "bei", "auf"}
OWNED = ("rohprotein", "rohfett", "rohfaser", "rohasche", "feuchtigkeit",
         "ingredients_text", "quantity", "hersteller_url",
         "energie_kcal_100g", "energie_kj_100g")
KJ_PER_KCAL = 4.184


def fetch(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def product_urls():
    xml = fetch(SITEMAP).decode("utf-8", "replace")
    urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    # Product pages end in a numeric id; others are category/filter listings.
    return sorted({u for u in urls if re.search(r"/de/dogs/products/.+-\d+/?$", u)})


def parse_page(raw):
    page = raw.decode("utf-8", "replace")
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not match:
        return None
    data = json.loads(match.group(1))
    response = (data.get("props", {}).get("pageProps", {}).get("productData") or {}).get("response")
    if not isinstance(response, dict):
        return None
    technology = (response.get("technology") or "").lower()
    if technology not in FOOD_TYPES:
        sub = ((response.get("digitalSubCategory") or {}).get("code") or "").lower()
        technology = "dry" if sub.startswith("dry") else "wet" if sub.startswith("wet") else technology
    info = {}
    for entry in response.get("nutritionalInfo") or []:
        key = (entry.get("title") or "").rsplit(".", 1)[-1]
        info[key] = entry.get("description") or entry.get("value") or ""
    product = {
        "title": (response.get("title") or "").strip(),
        "technology": technology,
        "category": response.get("categoryLabel") or "",
        "packs": [(str(p.get("ean") or "").strip(), p.get("size") or "")
                  for p in response.get("packs") or []],
    }
    analysis = info.get("analyticalConstituants", "")
    if not analysis:
        # Some pages embed the analysis in another block; the RSA guaranteed analysis (min/max) is excluded.
        analysis = " ".join(v for k, v in info.items() if k != "rsaStatement" and re.search(r"analyti", v, re.I))
    for key, label in NUTRIENTS.items():
        found = re.search(rf"(?:^|[\s:\-–])(?:{label})\s*:\s*(\d+(?:[.,]\d+)?)\s*%", analysis, re.I)
        if found:
            product[key] = float(found.group(1).replace(",", "."))
    composition = re.sub(r"^\s*zusammensetzung\s*:\s*", "", info.get("composition", ""), flags=re.I)
    product["ingredients_text"] = re.sub(r"\s+", " ", composition).strip()

    energy = (response.get("original_product") or {}).get("reference_energy_value_per_weight") or {}
    kcal_per_kg = energy.get("amount") if (energy.get("unit") or "").lower() == "kcal/kg" else None
    if not kcal_per_kg:
        found = re.search(r"Energiegehalt[^:]*:\s*(\d+(?:[.,]\d+)?)\s*kcal\s*/\s*kg", analysis, re.I)
        kcal_per_kg = float(found.group(1).replace(",", ".")) if found else None
    if kcal_per_kg:
        product["energie_kcal_100g"] = round(float(kcal_per_kg) / 10, 1)
        product["energie_kj_100g"] = round(float(kcal_per_kg) / 10 * KJ_PER_KCAL, 1)
    return product


def display_name(title):
    words = re.sub(r"\s+", " ", title).strip().title().split(" ")
    return " ".join(w.lower() if i and w.lower() in SMALL_WORDS else w for i, w in enumerate(words))


def find_csv():
    for path in sorted(ROOT.glob(f"{SLUG}-*.csv")):
        if re.fullmatch(rf"{SLUG}-\d+\.csv", path.name):
            return path
    raise SystemExit(f"Keine Projektdatei {SLUG}-<anzahl>.csv gefunden")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", default=".cache/royal-canin", help="Page cache (relative to project folder)")
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds between requests")
    parser.add_argument("--limit", type=int, default=0, help="Only process N pages (testing)")
    parser.add_argument("--csv", help="Override target CSV (testing)")
    args = parser.parse_args()

    cache = Path(args.cache) if Path(args.cache).is_absolute() else ROOT / args.cache
    cache.mkdir(parents=True, exist_ok=True)
    urls = product_urls()
    if args.limit:
        urls = urls[: args.limit]
    print(f"{len(urls)} Hunde-Produktseiten", file=sys.stderr, flush=True)

    products, skipped = [], {}
    for index, url in enumerate(urls, start=1):
        cached = cache / (url.rstrip("/").rsplit("/", 1)[-1] + ".bin")
        if cached.exists():
            raw = cached.read_bytes()
        else:
            try:
                raw = fetch(url)
            except Exception as error:  # noqa: BLE001
                print(f"[{index}/{len(urls)}] übersprungen {url}: {error}", file=sys.stderr)
                time.sleep(args.interval)
                continue
            cached.write_bytes(raw)
            time.sleep(args.interval)
        product = parse_page(raw)
        if not product:
            skipped["keine Produktdaten"] = skipped.get("keine Produktdaten", 0) + 1
            continue
        if product["technology"] not in FOOD_TYPES:
            label = product["category"].rsplit(".", 1)[-1] or "unbekannt"
            skipped[label] = skipped.get(label, 0) + 1
            continue
        product["url"] = url
        products.append(product)
        if index % 25 == 0:
            print(f"[{index}/{len(urls)}]", file=sys.stderr, flush=True)

    path = Path(args.csv) if args.csv else find_csv()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames)
        rows = {r["ean"]: r for r in reader}
    for name in OWNED + ("source",):
        if name not in fields:
            fields.append(name)

    for row in rows.values():
        if "royalcanin.com" in row.get("source", ""):
            # Rows that exist only because of the manufacturer stay manufacturer-owned.
            row["_rc_owned"] = "royalcanin.com (neu)" in row["source"]
            for key in OWNED:
                row[key] = ""
            parts = [p.strip() for p in row["source"].split(";") if "royalcanin.com" not in p]
            row["source"] = "; ".join(p for p in parts if p)

    stats = {"EAN": 0, "neu": 0, "Typ abweichend": 0}
    seen = set()
    for product in products:
        food_type = FOOD_TYPES[product["technology"]]
        for ean, size in product["packs"]:
            if not re.fullmatch(r"\d{8}|\d{12,14}", ean) or ean in seen:
                continue
            seen.add(ean)
            if ean in rows and not rows[ean].get("_rc_owned"):
                row, how = rows[ean], "EAN"
                if row.get("food_type") and row["food_type"] != food_type:
                    stats["Typ abweichend"] += 1
                    print(f"Hinweis {ean}: NfE-Pro {row['food_type']} vs. Hersteller {food_type}", file=sys.stderr)
            else:
                row = rows.get(ean) or {f: "" for f in fields}
                row.update(ean=ean, brand="Royal Canin", animal="Hund", food_type=food_type,
                           product_name=f"Royal Canin {display_name(product['title'])} – {size}".strip(" –"))
                rows[ean] = row
                how = "neu"
            stats[how] += 1
            for key in NUTRIENTS:
                row[key] = product.get(key, "")
            row["energie_kcal_100g"] = product.get("energie_kcal_100g", "")
            row["energie_kj_100g"] = product.get("energie_kj_100g", "")
            row["ingredients_text"] = product["ingredients_text"]
            row["quantity"] = size
            row["hersteller_url"] = product["url"]
            row["source"] = f"{row.get('source', '')}; royalcanin.com ({how})".lstrip("; ")

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for ean in sorted(rows):
            writer.writerow({f: rows[ean].get(f, "") for f in fields})

    print(f"Trocken/Nass-Produktseiten: {len(products)}; EANs per Abgleich: {stats['EAN']}, "
          f"neu: {stats['neu']}, Typ abweichend: {stats['Typ abweichend']}; Zeilen gesamt: {len(rows)}",
          file=sys.stderr)
    print(f"übersprungen: {skipped}", file=sys.stderr)

    if not args.csv:
        from update_csv_filename import update_filename
        from build_dashboard_data import build

        print(f"Datei: {update_filename(path).name}", file=sys.stderr)
        build()


if __name__ == "__main__":
    main()
