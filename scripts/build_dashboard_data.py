#!/usr/bin/env python3
"""Write scripts/dashboard-data.js so dashboard.html can show the project folder without a server.

Browsers block reading sibling files from a file:// page, but they allow loading a
sibling <script>. This bundles projects.json and every '<brand>-<count>.csv' in
this folder into that script. Re-run after CSV changes (the other scripts call it).
"""

import json
import re
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CSV_NAME = re.compile(r"^([a-z0-9][a-z0-9-]*?)-(\d+)\.csv$")
OUTPUT = BASE / "scripts" / "dashboard-data.js"


def build(base=BASE):
    state_path = base / "projects.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    files = {}
    for path in sorted(base.glob("*.csv")):
        match = CSV_NAME.match(path.name)
        if not match:
            continue
        files[match.group(1)] = {
            "name": path.name,
            "lastModified": int(path.stat().st_mtime * 1000),
            "text": path.read_text(encoding="utf-8-sig"),
        }
    data = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "state": state,
        "files": files,
    }
    output = base / OUTPUT.relative_to(BASE)
    tmp = output.with_suffix(".js.tmp")
    tmp.write_text(
        "window.DASHBOARD_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    tmp.replace(output)
    return output, len(files)


if __name__ == "__main__":
    path, count = build()
    print(f"{path.name}: {count} Projekt(e)")
