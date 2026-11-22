#!/usr/bin/env python3
"""Local dashboard: every '<brand>-<count>.csv' in the project folder is one project.

Run:  python3 scripts/dashboard.py   ->  http://127.0.0.1:8899
Standard library only; binds to localhost.
"""

import csv
import json
import re
import socket
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent.parent
STATE_FILE = BASE / "projects.json"
HTML_FILE = BASE / "dashboard.html"
HOST, PORT = "127.0.0.1", 8899
STATUSES = ("offen", "in Bearbeitung", "erledigt")
PREVIEW_LIMIT = 5000
CSV_NAME = re.compile(r"^([a-z0-9][a-z0-9-]*?)-(\d+)\.csv$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
_lock = threading.Lock()


def load_state():
    with STATE_FILE.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_state(state):
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def project_files():
    projects = {}
    for path in sorted(BASE.glob("*.csv")):
        match = CSV_NAME.match(path.name)
        if match:
            projects[match.group(1)] = path
    return projects


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def source_breakdown(rows):
    counts = {}
    for row in rows:
        for token in (row.get("source") or "").split(";"):
            label = re.sub(r"\s*\(.*?\)\s*$", "", token).strip()
            if label:
                counts[label] = counts.get(label, 0) + 1
    return counts


def overall_status(source_states, registry):
    relevant = [
        source_states.get(s["id"], {}).get("status", "offen")
        for s in registry
        if not s.get("optional")
    ]
    if relevant and all(s == "erledigt" for s in relevant):
        return "erledigt"
    if any(s in ("in Bearbeitung", "erledigt") for s in relevant):
        return "in Bearbeitung"
    return "offen"


def summarize(slug, path, state):
    columns, rows = read_csv(path)
    entry = state["projects"].get(slug, {})
    registry = state["sources"]
    source_states = entry.get("sources", {})
    nutrient_cols = [c for c in ("rohprotein", "rohfett", "rohfaser", "rohasche") if c in columns]
    with_analysis = sum(1 for r in rows if any((r.get(c) or "").strip() for c in nutrient_cols))
    food_types = {}
    for row in rows:
        key = row.get("food_type") or "unbekannt"
        food_types[key] = food_types.get(key, 0) + 1
    return {
        "slug": slug,
        "brand": entry.get("brand") or slug.replace("-", " ").title(),
        "file": path.name,
        "rows": len(rows),
        "columns": len(columns),
        "with_analysis": with_analysis,
        "food_types": food_types,
        "row_sources": source_breakdown(rows),
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="minutes"),
        "overall": overall_status(source_states, registry),
        "sources": [
            {
                **src,
                "status": source_states.get(src["id"], {}).get("status", "offen"),
                "note": source_states.get(src["id"], {}).get("note", ""),
                "updated": source_states.get(src["id"], {}).get("updated", ""),
            }
            for src in registry
        ],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if not parts:
            body = HTML_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parts == ["api", "projects"]:
            state = load_state()
            files = project_files()
            self.send_json([summarize(slug, path, state) for slug, path in files.items()])
            return
        if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "rows":
            slug = parts[2]
            path = project_files().get(slug) if SLUG.match(slug) else None
            if not path:
                self.send_json({"error": "Projekt nicht gefunden"}, 404)
                return
            columns, rows = read_csv(path)
            self.send_json({
                "columns": columns,
                "rows": rows[:PREVIEW_LIMIT],
                "total": len(rows),
                "truncated": len(rows) > PREVIEW_LIMIT,
            })
            return
        self.send_json({"error": "Nicht gefunden"}, 404)

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if not (len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3] == "sources"):
            self.send_json({"error": "Nicht gefunden"}, 404)
            return
        slug, source_id = parts[2], parts[4]
        length = int(self.headers.get("Content-Length") or 0)
        if length > 10_000:
            self.send_json({"error": "Anfrage zu groß"}, 413)
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self.send_json({"error": "Ungültiges JSON"}, 400)
            return
        status = payload.get("status")
        note = str(payload.get("note", ""))[:500]
        with _lock:
            state = load_state()
            if not SLUG.match(slug) or slug not in project_files():
                self.send_json({"error": "Projekt nicht gefunden"}, 404)
                return
            if source_id not in {s["id"] for s in state["sources"]}:
                self.send_json({"error": "Quelle unbekannt"}, 400)
                return
            if status not in STATUSES:
                self.send_json({"error": "Status ungültig"}, 400)
                return
            project = state["projects"].setdefault(slug, {"brand": slug.title(), "sources": {}})
            project.setdefault("sources", {})[source_id] = {
                "status": status,
                "note": note,
                "updated": datetime.now().isoformat(timespec="minutes"),
            }
            save_state(state)
            path = project_files()[slug]
            self.send_json(summarize(slug, path, state))


class DualStackServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6


if __name__ == "__main__":
    servers = [ThreadingHTTPServer((HOST, PORT), Handler)]
    try:
        servers.append(DualStackServer(("::1", PORT), Handler))
    except OSError:
        pass
    for server in servers[1:]:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Dashboard: http://{HOST}:{PORT}  (auch http://localhost:{PORT})")
    servers[0].serve_forever()
