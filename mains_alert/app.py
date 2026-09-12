import json
import logging
import os
import platform
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_file

from detector import MainsDetector

APP_VERSION = "0.1.1"
DATA_DIR = Path("/data")
SETTINGS_FILE = DATA_DIR / "settings.json"
EVENTS_FILE = DATA_DIR / "events.json"
HA_URL = "http://supervisor/core"
TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
DEFAULTS = {
    "enabled": False,
    "entity_id": "",
    "attribute": "",
    "mode": "numeric",
    "off_threshold": 50,
    "on_threshold": 180,
    "off_delay": 15,
    "on_delay": 10,
    "startup_suppression": 60,
    "notify_services": [],
    "outage_title": "Mains power is OFF",
    "outage_message": "Mains power has failed at home.",
    "restore_title": "Mains power restored",
    "restore_message": "Mains power is back on at home."
}

app = Flask(__name__)
lock = threading.RLock()
detector = MainsDetector()
started_at = time.time()
latest = {"state": None, "value": None, "attributes": {}, "error": None, "checked_at": None}
events = deque(maxlen=200)


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path, fallback):
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return fallback


def save_json(path, value):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)
    temp.replace(path)


settings = {**DEFAULTS, **load_json(SETTINGS_FILE, {})}
for row in load_json(EVENTS_FILE, []):
    events.append(row)


def add_event(kind, message, details=None):
    row = {"time": utcnow(), "kind": kind, "message": message}
    if details is not None:
        row["details"] = details
    with lock:
        events.appendleft(row)
        save_json(EVENTS_FILE, list(events))
    logging.info("%s: %s", kind, message)


def ha_get(path):
    response = requests.get(f"{HA_URL}{path}", headers=HEADERS, timeout=10)
    response.raise_for_status()
    return response.json()


def ha_post(path, payload):
    response = requests.post(f"{HA_URL}{path}", headers=HEADERS, json=payload, timeout=10)
    response.raise_for_status()
    return response.json() if response.content else {}


def notify(kind, test=False):
    cfg = settings.copy()
    title = cfg["outage_title"] if kind == "off" else cfg["restore_title"]
    message = cfg["outage_message"] if kind == "off" else cfg["restore_message"]
    if test:
        title = f"TEST: {title}"
        message = f"{message} This is a test from Mains Power Alert."
    outcomes = []
    for service in cfg.get("notify_services", []):
        service_name = service.replace("notify.", "", 1)
        try:
            ha_post(f"/api/services/notify/{service_name}", {"title": title, "message": message})
            outcomes.append({"service": service, "ok": True})
        except Exception as exc:
            outcomes.append({"service": service, "ok": False, "error": str(exc)})
    add_event("test" if test else kind, f"Sent {kind} notification to {sum(x['ok'] for x in outcomes)}/{len(outcomes)} targets", outcomes)
    return outcomes


def monitor():
    while True:
        time.sleep(2)
        cfg = settings.copy()
        entity_id = cfg.get("entity_id", "")
        if not entity_id:
            continue
        try:
            state = ha_get(f"/api/states/{entity_id}")
            attr = cfg.get("attribute", "").strip()
            value = state.get("attributes", {}).get(attr) if attr else state.get("state")
            with lock:
                latest.update({"state": state.get("state"), "value": value,
                               "attributes": state.get("attributes", {}), "error": None,
                               "checked_at": utcnow()})
            allowed = cfg.get("enabled", False) and time.time() - started_at >= float(cfg.get("startup_suppression", 60))
            result = detector.update(value, time.monotonic(), cfg, allow_event=allowed)
            if result.event:
                add_event(result.event, "Mains outage confirmed" if result.event == "off" else "Mains restoration confirmed",
                          {"entity_id": entity_id, "value": value})
                notify(result.event)
        except Exception as exc:
            with lock:
                latest.update({"error": str(exc), "checked_at": utcnow()})
            logging.warning("Monitor check failed: %s", exc)


@app.get("/")
def index():
    return send_file("/index.html")


@app.get("/api/discover")
def discover():
    try:
        states = ha_get("/api/states")
        services = ha_get("/api/services")
        entities = [{"entity_id": x["entity_id"], "state": x.get("state"),
                     "name": x.get("attributes", {}).get("friendly_name", x["entity_id"]),
                     "unit": x.get("attributes", {}).get("unit_of_measurement", "")}
                    for x in states]
        notify_services = []
        for domain in services:
            if domain.get("domain") == "notify":
                notify_services = [f"notify.{name}" for name in domain.get("services", {}) if name.startswith("mobile_app_")]
        return jsonify({"entities": entities, "notify_services": sorted(notify_services)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    global settings
    if request.method == "GET":
        return jsonify(settings)
    incoming = request.get_json(force=True) or {}
    allowed = set(DEFAULTS)
    new_settings = {**DEFAULTS, **{k: v for k, v in incoming.items() if k in allowed}}
    if new_settings["mode"] not in ("numeric", "state"):
        return jsonify({"error": "mode must be numeric or state"}), 400
    with lock:
        settings = new_settings
        save_json(SETTINGS_FILE, settings)
        detector.status = "unknown"
    add_event("config", "Configuration saved; detector baseline reset")
    return jsonify(settings)


@app.get("/api/status")
def status():
    with lock:
        return jsonify({"version": APP_VERSION, "detector_status": detector.status,
                        "latest": latest, "events": list(events)[:50], "uptime_seconds": int(time.time() - started_at)})


@app.post("/api/test/<kind>")
def test_notification(kind):
    if kind not in ("off", "on"):
        return jsonify({"error": "kind must be off or on"}), 400
    return jsonify({"outcomes": notify(kind, test=True)})


@app.get("/api/diagnostics")
def diagnostics():
    cfg = settings.copy()
    report = {
        "addon": {"name": "Mains Power Alert", "version": APP_VERSION, "python": platform.python_version()},
        "configuration": cfg,
        "runtime": {"detector_status": detector.status, "uptime_seconds": int(time.time() - started_at)},
        "selected_entity": latest,
        "recent_events": list(events)[:30]
    }
    return app.response_class(json.dumps(report, indent=2, default=str), mimetype="text/plain")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host="0.0.0.0", port=8099, threaded=True)
