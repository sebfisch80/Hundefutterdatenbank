#!/usr/bin/env python3
"""Respectful CSV export for NFE-Pro product searches.

The target website applies automated-access and rate limits. This script does
not bypass those limits. Review the site's terms and obtain permission before
bulk use.
"""

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


SEARCH_URL = "https://www.nfepro.de/api/community.php"
USER_AGENT = "NFE-Export/1.0 (manual, respectful CSV export)"


def request_json(params, timeout):
    url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8", "replace")
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            data = {"ok": False, "message": payload[:300]}
        data["_retry_after"] = error.headers.get("Retry-After")
        return error.code, data


def fetch_search(query, animal, food_type, sort, page, timeout):
    status, data = request_json(
        {
            "action": "search",
            "q": query,
            "animal": animal,
            "food_type": food_type,
            "sort": sort,
            "page": page,
        },
        timeout,
    )
    if status != 200:
        raise RuntimeError(
            f"HTTP {status}: {data.get('message') or data.get('error') or 'request failed'}"
        )
    if not data.get("ok"):
        raise RuntimeError(data.get("message") or "search failed")
    return data


def fetch_product(ean, timeout):
    status, data = request_json(
        {"action": "product", "context": "search", "ean": ean},
        timeout,
    )
    if status != 200:
        return None
    if not data.get("ok") or not data.get("found"):
        return None
    return data.get("product")


def flatten(row):
    values = row.get("values") or {}
    animal = {"dog": "Hund", "cat": "Katze"}.get(row.get("animal"), row.get("animal", ""))
    food_type = {
        "wet": "Nassfutter",
        "dry": "Trockenfutter",
        "extra": "Snacks & Ergänzungsfutter",
    }.get(row.get("food_type"), row.get("food_type", ""))
    return {
        "ean": row.get("ean", ""),
        "product_name": row.get("product_name", ""),
        "brand": row.get("brand", ""),
        "animal": animal,
        "food_type": food_type,
        "confirmations": row.get("confirmations", ""),
        "values_json": json.dumps(values, ensure_ascii=False, sort_keys=True),
        "rohprotein": values.get("rohprotein", ""),
        "rohprotein_trockenmasse": values.get("rohprotein_trockenmasse", ""),
        "rohprotein_feuchtigkeit": values.get("rohprotein_feuchtigkeit", ""),
        "rohprotein_basis": values.get("rohprotein_basis", ""),
        "rohprotein_wert": values.get("rohprotein_wert", ""),
        "rohprotein_proz": values.get("rohprotein_proz", ""),
        "protein": values.get("protein", ""),
        "protein_percent": values.get("protein_percent", ""),
        "protein_trockenmasse": values.get("protein_trockenmasse", ""),
        "rohfett": values.get("rohfett", ""),
        "fett": values.get("fett", ""),
        "fett_percent": values.get("fett_percent", ""),
        "rohfaser": values.get("rohfaser", ""),
        "faser": values.get("faser", ""),
        "faser_percent": values.get("faser_percent", ""),
        "rohasche": values.get("rohasche", ""),
        "asche": values.get("asche", ""),
        "asche_percent": values.get("asche_percent", ""),
        "feuchtigkeit": values.get("feuchtigkeit", ""),
        "moisture": values.get("moisture", ""),
    }


def main():
    parser = argparse.ArgumentParser(description="Export NFE-Pro search results to CSV")
    parser.add_argument("--q", default="a", help="Search term; repeat by using separate runs")
    parser.add_argument("--animal", choices=("cat", "dog"), default="", help="Animal filter")
    parser.add_argument("--food-type", choices=("wet", "dry", "extra"), default="", help="Food type filter")
    parser.add_argument(
        "--sort",
        choices=("relevance", "popular", "newest", "nfe_asc", "nfe_desc", "name_asc"),
        default="relevance",
        help="Search result sort",
    )
    parser.add_argument("--output", default="nfepro-products.csv", help="CSV output path (relative to project folder)")
    parser.add_argument("--max-pages", type=int, default=0, help="0 for all returned pages")
    parser.add_argument("--interval", type=float, default=4.5, help="Seconds between requests")
    parser.add_argument("--timeout", type=float, default=30, help="HTTP timeout in seconds")
    parser.add_argument("--details", action="store_true", help="Fetch full product details per EAN")
    args = parser.parse_args()

    products = {}
    page = 1
    while True:
        data = fetch_search(args.q, args.animal, args.food_type, args.sort, page, args.timeout)
        for product in data.get("products", []):
            ean = str(product.get("ean") or "")
            if ean:
                products[ean] = product

        pages = int(data.get("pages") or 1)
        print(f"q={args.q!r}: page {page}/{pages}, {len(products)} unique EANs", file=sys.stderr)
        if page >= pages or (args.max_pages and page >= args.max_pages):
            break
        page += 1
        time.sleep(args.interval)

    if args.details:
        for index, (ean, product) in enumerate(list(products.items()), start=1):
            detail = fetch_product(ean, args.timeout)
            if detail:
                products[ean] = detail
            if index < len(products):
                time.sleep(args.interval)

    output = Path(args.output)
    if not output.is_absolute():
        output = Path(__file__).resolve().parent.parent / output
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(flatten({}).keys())
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for ean in sorted(products):
            writer.writerow(flatten(products[ean]))

    print(f"Wrote {len(products)} products to {output}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
