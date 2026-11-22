#!/usr/bin/env python3
"""Collect one brand from NfE-Pro into its single project CSV.

Runs every requested food type x sort order (all pages), keeps only rows whose
brand matches, deduplicates by EAN and merges into '<slug>-<count>.csv' in the
project folder (existing rows are kept). On HTTP 429 the script waits for the
server's Retry-After before continuing - it never tries to evade the limit.
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nfepro_export import flatten, request_json  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SORTS = ("relevance", "popular", "newest", "nfe_asc", "nfe_desc", "name_asc")
DEFAULT_SORTS = ("relevance", "popular", "newest")
CSV_NAME = re.compile(r"^(.*)-(\d+)\.csv$")


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def find_project_csv(slug):
    for path in sorted(ROOT.glob(f"{slug}-*.csv")):
        match = CSV_NAME.match(path.name)
        if match and match.group(1) == slug:
            return path
    return None


def search_page(params, timeout, max_wait):
    while True:
        status, data = request_json(params, timeout)
        if status == 429 or data.get("error") == "automated_access_denied":
            retry = data.get("_retry_after")
            wait = int(retry) if retry and str(retry).isdigit() else 900
            if wait > max_wait:
                raise RuntimeError(f"Retry-After {wait}s exceeds --max-wait {max_wait}s")
            print(f"  HTTP {status}: Server verlangt Pause, warte {wait}s …", file=sys.stderr, flush=True)
            time.sleep(wait + 5)
            continue
        if status != 200 or not data.get("ok"):
            raise RuntimeError(f"HTTP {status}: {data.get('message') or data.get('error')}")
        return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brand", required=True, help='Brand name, e.g. "Royal Canin"')
    parser.add_argument("--q", help="Search term (default: brand)")
    parser.add_argument("--animal", default="dog", choices=("dog", "cat"))
    parser.add_argument("--food-types", nargs="+", default=["wet", "dry"], choices=("wet", "dry", "extra"))
    parser.add_argument("--sorts", nargs="+", default=list(DEFAULT_SORTS), choices=SORTS,
                        help="Sort orders; the 2nd+ only run if the search reports more than 60 hits")
    parser.add_argument("--interval", type=float, default=20.0, help="Seconds between requests")
    parser.add_argument("--sort-pause", type=float, default=60.0, help="Seconds between sort runs")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--max-wait", type=int, default=1800, help="Longest Retry-After to honour")
    args = parser.parse_args()

    query = args.q or args.brand
    slug = slugify(args.brand)
    brand_key = args.brand.lower()
    found, excluded = {}, {}

    for food_type in args.food_types:
        for sort in args.sorts:
            page = 1
            limited = False
            while True:
                data = search_page(
                    {"action": "search", "q": query, "animal": args.animal,
                     "food_type": food_type, "sort": sort, "page": page},
                    args.timeout, args.max_wait,
                )
                limited = limited or bool(data.get("limited"))
                for product in data.get("products", []):
                    ean = str(product.get("ean") or "").strip()
                    brand = (product.get("brand") or "").strip()
                    if not ean:
                        continue
                    if brand.lower().startswith(brand_key):
                        found.setdefault(ean, product)
                    else:
                        excluded[brand or "(leer)"] = excluded.get(brand or "(leer)", 0) + 1
                pages = int(data.get("pages") or 1)
                print(f"{food_type}/{sort}: Seite {page}/{pages} – {len(found)} EANs gesamt"
                      f"{' (begrenzt)' if data.get('limited') else ''}", file=sys.stderr, flush=True)
                if page >= pages:
                    break
                page += 1
                time.sleep(args.interval)
            # Save after every sort run so an interruption loses nothing.
            save(slug, found)
            time.sleep(args.sort_pause)
            if not limited:
                # 60 or fewer hits: the first sort order already returned everything.
                print(f"{food_type}: ≤ 60 Treffer – weitere Sortierungen nicht nötig", file=sys.stderr, flush=True)
                break

    final, added, total = save(slug, found)
    from build_dashboard_data import build

    build()
    print(f"neu: {added}, gesamt: {total} → {final.name}", file=sys.stderr)
    print(f"ausgeschlossene Fremdmarken: {excluded}", file=sys.stderr)


def save(slug, found):
    from update_csv_filename import update_filename

    existing = find_project_csv(slug)
    rows, fields = {}, list(flatten({}).keys()) + ["source"]
    if existing:
        with existing.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames) + [f for f in fields if f not in reader.fieldnames]
            rows = {r["ean"]: r for r in reader}
    before = len(rows)
    for ean, product in found.items():
        if ean in rows:
            if "NfE-Pro" not in rows[ean].get("source", ""):
                rows[ean]["source"] = f"NfE-Pro; {rows[ean].get('source', '')}".rstrip("; ")
            continue
        row = flatten(product)
        row["source"] = "NfE-Pro"
        rows[ean] = row

    target = existing or ROOT / f"{slug}-0.csv"
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for ean in sorted(rows):
            writer.writerow({f: rows[ean].get(f, "") for f in fields})
    return update_filename(target), len(rows) - before, len(rows)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(f"Abbruch: {error}", file=sys.stderr)
        raise SystemExit(1)
