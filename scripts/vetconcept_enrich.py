#!/usr/bin/env python3
"""Enrich a brand CSV with analytical constituents from the vet-concept.com shop.

Respects robots.txt: only sitemap and /p/ product pages are fetched, no search
URLs, with a fixed pause between requests. Pages are cached locally so reruns
do not hit the shop again.
"""

import argparse
import csv
import html as html_lib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KJ_PER_KCAL = 4.184
ENERGY_FIELDS = ("energie_kcal_100g", "energie_kj_100g")
SITEMAP = "https://www.vet-concept.com/toprank-sitemap_01-aa0.xml"
USER_AGENT = "Hundefutterdatenbank/1.0 (private research; slow crawl)"
NUTRIENTS = {
    "rohprotein": r"Rohprotein",
    "rohfett": r"Rohfett|Fettgehalt",
    "rohfaser": r"Rohfaser",
    "rohasche": r"Rohasche",
    "feuchtigkeit": r"Feuchtigkeit|Feuchte",
}


def fetch_bytes(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def decode(raw):
    head = raw[:4000].decode("ascii", "ignore")
    match = re.search(r"charset=[\"']?([\w-]+)", head, re.I)
    for encoding in ([match.group(1)] if match else []) + ["utf-8", "cp1252"]:
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("cp1252", "replace")


def fetch(url, timeout=30):
    return decode(fetch_bytes(url, timeout))


def dog_product_urls():
    xml = fetch(SITEMAP)
    urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    return sorted({u for u in urls if "/p/fuer-den-hund-" in u})


def to_float(text):
    return float(text.replace(",", "."))


def parse_product(page):
    product = {}
    for block in re.findall(
        r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", page, re.S
    ):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "Product":
                product["name"] = item.get("name", "")
                product["gtin13"] = str(item.get("gtin13") or "").strip()
            elif item.get("@type") == "BreadcrumbList":
                names = [
                    e.get("name") or (e.get("item") or {}).get("name") or ""
                    for e in item.get("itemListElement", [])
                ]
                if len(names) >= 3:
                    product["category"] = names[2]
                if len(names) >= 4:
                    product["breadcrumb_name"] = names[-1]

    # Some pages carry an unparsable Product JSON-LD block; fall back to the breadcrumb and raw gtin13.
    if not product.get("name") and product.get("breadcrumb_name"):
        product["name"] = product["breadcrumb_name"]
    if not product.get("gtin13"):
        match = re.search(r'"gtin13"\s*:\s*"(\d{13})"', page)
        if match:
            product["gtin13"] = match.group(1)

    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", page))
    text = re.sub(r"\s+", " ", text)

    start = text.find("Analytische Bestandteile")
    if start != -1:
        section = text[start:start + 400]
        for key, label in NUTRIENTS.items():
            match = re.search(rf"(?:{label})\s*:?\s*(\d+(?:[.,]\d+)?)\s*%", section)
            if match:
                product[key] = to_float(match.group(1))

    comp = re.search(
        r"Zusammensetzung\s*:?\s*(.{10,600}?)(?:Analytische Bestandteile|Zusatzstoffe|$)",
        text,
    )
    if comp:
        product["ingredients_text"] = comp.group(1).strip(" :")

    energy = re.search(
        r"Umsetzbare Energie.{0,40}?(\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,(\d+))?\s*kJ\s*/\s*(100\s*g|kg)",
        text,
        re.I,
    )
    if energy:
        kj = float(re.sub(r"[.\s]", "", energy.group(1)) + ("." + energy.group(2) if energy.group(2) else ""))
        if energy.group(3).lower() == "kg":
            kj /= 10
        product["energie_kj_100g"] = round(kj, 1)
        product["energie_kcal_100g"] = round(kj / KJ_PER_KCAL, 1)
    return product


def food_type_from_category(category):
    category = (category or "").lower()
    if "trocken" in category:
        return "Trockenfutter"
    if any(word in category for word in ("nass", "dose", "menü", "menue")):
        return "Nassfutter"
    return ""


def family_key(name):
    name = name.lower()
    name = name.replace("ü", "ue").replace("ä", "ae").replace("ö", "oe").replace("ß", "ss")
    name = re.sub(r"^vet-concept\s+", "", name)
    name = re.sub(r"\s+[–-]\s+[\d.,]+\s*(kg|g)\s*$", "", name)
    return re.sub(r"[^a-z0-9]+", " ", name).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="Brand CSV to enrich in place (relative to project folder)")
    parser.add_argument("--cache", default=".cache/vet-concept", help="Page cache directory (relative to project folder)")
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds between requests")
    parser.add_argument("--limit", type=int, default=0, help="Only process N pages (testing)")
    args = parser.parse_args()

    cache = Path(args.cache) if Path(args.cache).is_absolute() else ROOT / args.cache
    cache.mkdir(parents=True, exist_ok=True)

    urls = dog_product_urls()
    if args.limit:
        urls = urls[: args.limit]
    print(f"{len(urls)} dog product pages", file=sys.stderr)

    products = []
    for index, url in enumerate(urls, start=1):
        cached = cache / (url.rsplit("/", 1)[-1] + ".bin")
        if cached.exists():
            raw = cached.read_bytes()
        else:
            try:
                raw = fetch_bytes(url)
            except Exception as error:  # noqa: BLE001
                print(f"[{index}/{len(urls)}] skip {url}: {error}", file=sys.stderr)
                time.sleep(args.interval)
                continue
            cached.write_bytes(raw)
            time.sleep(args.interval)
        product = parse_product(decode(raw))
        product["url"] = url
        if "rohprotein" in product:
            products.append(product)
        print(f"[{index}/{len(urls)}] {product.get('name', '?')}", file=sys.stderr)

    path = Path(args.csv) if Path(args.csv).is_absolute() else ROOT / args.csv
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames)
        rows = list(reader)
    for extra in ("hersteller_url",) + ENERGY_FIELDS:
        if extra not in fields:
            fields.append(extra)

    # Manufacturer-owned fields are rebuilt on every run so corrections apply.
    for row in rows:
        if "vet-concept.com" not in row.get("source", ""):
            continue
        for key in tuple(NUTRIENTS) + ENERGY_FIELDS:
            row[key] = ""
        row["ingredients_text"] = ""
        row["hersteller_url"] = ""
        parts = [p.strip() for p in row["source"].split(";") if "vet-concept.com" not in p]
        row["source"] = "; ".join(p for p in parts if p)

    by_ean = {r["ean"]: r for r in rows}
    by_family = {}
    for row in rows:
        by_family.setdefault(family_key(row["product_name"]), []).append(row)

    stats = {"ean": 0, "family": 0, "new": 0}
    skipped_categories = {}
    claimed = {}
    assignments = []
    for product in products:
        targets = []
        ean = product.get("gtin13", "")
        food_type = food_type_from_category(product.get("category"))
        if ean in by_ean:
            targets.append((by_ean[ean], "EAN"))
            stats["ean"] += 1
        for row in by_family.get(family_key(product.get("name", "")), []):
            if row["ean"] != ean and food_type and row.get("food_type") == food_type:
                targets.append((row, "Produktfamilie"))
                stats["family"] += 1
        if not targets and re.fullmatch(r"\d{13}", ean) and not food_type:
            label = product.get("category") or "unbekannt"
            skipped_categories[label] = skipped_categories.get(label, 0) + 1
        if not targets and re.fullmatch(r"\d{13}", ean) and food_type:
            row = {f: "" for f in fields}
            row.update(
                ean=ean,
                product_name=f"Vet-Concept {product.get('name', '')}".strip(),
                brand="Vet-Concept",
                animal="Hund",
                food_type=food_type,
                source="",
            )
            rows.append(row)
            by_ean[ean] = row
            targets.append((row, "neu"))
            stats["new"] += 1

        assignments.extend((row, how, product) for row, how in targets)

    assignments.sort(key=lambda item: item[1] == "Produktfamilie")
    conflicts = 0
    for row, how, product in assignments:
        previous = claimed.get(row["ean"])
        if previous and previous != product["url"]:
            conflicts += 1
            print(f"conflict {row['ean']}: kept {previous}, skipped {product['url']}", file=sys.stderr)
            continue
        claimed[row["ean"]] = product["url"]
        for key in NUTRIENTS:
            row[key] = product.get(key, "")
        row["ingredients_text"] = product.get("ingredients_text", "")
        for key in ENERGY_FIELDS:
            row[key] = product.get(key, "")
        row["hersteller_url"] = product["url"]
        row["source"] = f"{row.get('source') or 'NfE-Pro'}; vet-concept.com ({how})".lstrip("; ")

    rows.sort(key=lambda r: r["ean"])
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"products with analysis: {len(products)}; matched by EAN: {stats['ean']}, "
        f"by family: {stats['family']}; new rows: {stats['new']}; conflicts: {conflicts}; "
        f"total rows: {len(rows)}",
        file=sys.stderr,
    )
    print(f"not added (other categories): {skipped_categories}", file=sys.stderr)

    try:
        from update_csv_filename import update_filename
        from build_dashboard_data import build

        print(f"file: {update_filename(path).name}", file=sys.stderr)
        build()
    except Exception as error:  # noqa: BLE001
        print(f"dashboard refresh skipped: {error}", file=sys.stderr)


if __name__ == "__main__":
    main()
