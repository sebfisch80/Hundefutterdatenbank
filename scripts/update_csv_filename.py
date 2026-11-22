#!/usr/bin/env python3
"""Keep a count-based CSV filename synchronized with its row count."""

import argparse
import csv
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def project_path(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def count_rows(csv_path):
    with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def update_filename(csv_path):
    count = count_rows(csv_path)
    name = csv_path.name
    match = re.match(r"^(.*?)(?:-\d+)?\.csv$", name)
    stem = match.group(1) if match else csv_path.stem
    new_path = csv_path.with_name(f"{stem}-{count}.csv")

    if csv_path == new_path:
        return csv_path

    if new_path.exists():
        raise FileExistsError(f"Target already exists: {new_path}")

    csv_path.rename(new_path)
    return new_path


def main():
    parser = argparse.ArgumentParser(
        description="Rename a CSV to include its current number of product rows."
    )
    parser.add_argument(
        "csv",
        nargs="?",
        default="vet-concept-*.csv",
        help="CSV path or glob pattern (relative paths refer to the project folder)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Poll every 5 seconds and rename whenever the row count changes",
    )
    args = parser.parse_args()

    target = project_path(args.csv)
    directory = target.parent
    pattern = target.name
    paths = sorted(directory.glob(pattern))
    if not paths:
        raise SystemExit(f"No CSV matched: {args.csv}")

    if not args.watch:
        for path in paths:
            print(update_filename(path))
        refresh_dashboard()
        return

    print("Watching", args.csv)
    last_signature = None
    while True:
        for path in sorted(directory.glob(pattern)):
            try:
                count = count_rows(path)
                match = re.match(r"^(.*?)(?:-\d+)?\.csv$", path.name)
                stem = match.group(1) if match else path.stem
                expected = path.with_name(f"{stem}-{count}.csv")
                if path != expected:
                    print(update_filename(path))
            except (FileNotFoundError, csv.Error, UnicodeDecodeError) as error:
                print(f"Skipped {path}: {error}")
        signature = sorted(
            (p.name, p.stat().st_mtime) for p in directory.glob("*.csv")
        ) + [p.stat().st_mtime for p in directory.glob("projects.json")]
        if signature != last_signature:
            refresh_dashboard()
            last_signature = signature
        time.sleep(5)


def refresh_dashboard():
    try:
        from build_dashboard_data import build

        path, count = build()
        print(f"{path.name} aktualisiert ({count} Projekt(e))")
    except Exception as error:  # noqa: BLE001
        print(f"dashboard-data.js nicht aktualisiert: {error}")


if __name__ == "__main__":
    main()
