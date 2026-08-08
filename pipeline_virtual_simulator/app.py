from __future__ import annotations

import csv
import math
import random
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
BASE = Path(__file__).resolve().parent
HISTORY = BASE / "simulation_history.csv"
lock = threading.Lock()
state: dict[str, Any] = {
    "running": False,
    "pump_on": True,
    "leak_zone": 0,
    "severity": 50,
    "sample_id": 0,
    "latest": {},
}


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def probabilities(zone: int, confidence: float) -> list[float]:
    if zone == 0:
        return [0.0] * 5
    rem = 100.0 - confidence
    weights = [0.0 if z == zone else math.exp(-0.9 * abs(z-zone)) for z in range(1, 6)]
    total = sum(weights) or 1.0
    vals = [confidence if z == zone else rem*w/total for z, w in zip(range(1, 6), weights)]
    vals = [round(v, 1) for v in vals]
    vals[zone-1] = round(vals[zone-1] + (100.0 - sum(vals)), 1)
    return vals


def make_reading() -> dict[str, Any]:
    with lock:
        running = bool(state["running"])
        pump_on = bool(state["pump_on"])
        zone = int(state["leak_zone"])
        severity = int(state["severity"])
        state["sample_id"] += 1
        sample_id = state["sample_id"]

    now = datetime.now().isoformat(timespec="seconds")
    if not pump_on:
        return {
            "timestamp": now, "sample_id": sample_id, "running": running,
            "pump_on": False, "leak_zone": zone, "severity": severity,
            "source_pressure": 0.0, "destination_pressure": 0.0,
            "source_flow": 0.0, "destination_flow": 0.0,
            "source_vibration": 0.02, "destination_vibration": 0.02,
            "source_temperature": 29.0, "destination_temperature": 29.0,
            "pressure_difference": 0.0, "flow_imbalance": 0.0,
            "flow_loss_percent": 0.0, "leak_detected": False,
            "predicted_zone": 0, "confidence": 99.0,
            "severity_label": "Pump OFF", "zone_probabilities": [0.0]*5,
            "system_status": "Pump is switched off",
        }

    p1 = 2.50 + random.uniform(-0.025, 0.025)
    f1 = 12.00 + random.uniform(-0.08, 0.08)
    t1 = 29.0 + random.uniform(-0.15, 0.15)
    t2 = t1 + random.uniform(-0.10, 0.10)

    if zone == 0:
        p2 = 2.30 + random.uniform(-0.025, 0.025)
        f2 = 11.80 + random.uniform(-0.08, 0.08)
        v1 = 0.10 + random.uniform(-0.015, 0.015)
        v2 = 0.09 + random.uniform(-0.015, 0.015)
        confidence = round(random.uniform(94, 99), 1)
        predicted = 0
        detected = False
        label = "Normal"
        probs = [0.0]*5
        status = "Pipeline operating normally"
    else:
        s = clamp(severity/100.0, 0.05, 1.0)
        f2 = f1 - (0.45 + 4.10*s) + random.uniform(-0.10, 0.10)
        position = (zone-1)/4.0
        extra_drop = 0.20 + 0.95*s + 0.10*abs(position-0.5)
        p2 = clamp(2.30 - extra_drop + random.uniform(-0.035, 0.035), 0.45, 2.25)
        base_v = 0.12 + 1.00*s
        v1 = 0.08 + base_v/(0.75 + zone*0.42) + random.uniform(-0.025, 0.025)
        v2 = 0.08 + base_v/(0.75 + (6-zone)*0.42) + random.uniform(-0.025, 0.025)
        confidence = round(clamp(64 + 27*s + random.uniform(-3, 3), 60, 95), 1)
        predicted = zone
        detected = True
        probs = probabilities(zone, confidence)
        label = "Minor" if severity < 35 else "Moderate" if severity < 70 else "Critical"
        status = f"Leak signature detected — inspect Zone {zone}"

    dp = p1-p2
    df = f1-f2
    loss = (df/f1*100.0) if f1 else 0.0
    return {
        "timestamp": now, "sample_id": sample_id, "running": running,
        "pump_on": True, "leak_zone": zone, "severity": severity,
        "source_pressure": round(p1,2), "destination_pressure": round(p2,2),
        "source_flow": round(f1,2), "destination_flow": round(f2,2),
        "source_vibration": round(max(v1,0),2), "destination_vibration": round(max(v2,0),2),
        "source_temperature": round(t1,1), "destination_temperature": round(t2,1),
        "pressure_difference": round(dp,2), "flow_imbalance": round(df,2),
        "flow_loss_percent": round(max(loss,0),1), "leak_detected": detected,
        "predicted_zone": predicted, "confidence": confidence,
        "severity_label": label, "zone_probabilities": probs,
        "system_status": status,
    }


def save_history(r: dict[str, Any]) -> None:
    fields = [
        "timestamp","sample_id","pump_on","leak_zone","severity",
        "source_pressure","destination_pressure","source_flow","destination_flow",
        "source_vibration","destination_vibration","source_temperature","destination_temperature",
        "pressure_difference","flow_imbalance","flow_loss_percent",
        "predicted_zone","confidence","severity_label","leak_detected"
    ]
    new = not HISTORY.exists()
    with HISTORY.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new: w.writeheader()
        w.writerow({k:r.get(k,"") for k in fields})


def loop() -> None:
    while True:
        with lock:
            run = bool(state["running"])
        if run:
            r = make_reading()
            with lock: state["latest"] = r
            save_history(r)
        time.sleep(1)


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/latest")
def latest():
    with lock: r = dict(state["latest"])
    if not r:
        r = make_reading()
        with lock: state["latest"] = r
    return jsonify(r)


@app.post("/api/config")
def config():
    data = request.get_json(silent=True) or {}
    with lock:
        if "running" in data: state["running"] = bool(data["running"])
        if "pump_on" in data: state["pump_on"] = bool(data["pump_on"])
        if "leak_zone" in data: state["leak_zone"] = max(0, min(5, int(data["leak_zone"])))
        if "severity" in data: state["severity"] = max(0, min(100, int(data["severity"])))
    r = make_reading()
    with lock: state["latest"] = r
    return jsonify({"ok":True,"state":r})


@app.post("/api/reset")
def reset():
    with lock:
        state.update({"running":False,"pump_on":True,"leak_zone":0,"severity":50,"sample_id":0,"latest":{}})
    r = make_reading()
    with lock: state["latest"] = r
    return jsonify({"ok":True,"state":r})


if __name__ == "__main__":
    threading.Thread(target=loop, daemon=True).start()
    print("Simulator: http://127.0.0.1:5001")
    print("JSON API: http://127.0.0.1:5001/api/latest")
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
