import sqlite3
import time
import json
from datetime import datetime, timezone

DB_PATH = "/home/mferet11/ha_config/home-assistant_v2.db"
OUTPUT_FILE = "telemetry_48h.json"

# Target entities to pull (or set to None to pull everything)
TARGET_ENTITIES = [
    "sensor.projector_current",
    "sensor.theater_mode",
    "binary_sensor.theater_in_use",
    "input_select.basement_lighting_mode",
    "binary_sensor.bottom_stairs",
    "binary_sensor.basement_stairs_door_sensor",
    "sensor.batocera_state",
    "sensor.batocera_current",
    "light.theater_dimmer",
    "light.stairlights",
    "sensor.philadelphia_eagles",
]

# 48 hours ago in UNIX epoch
cutoff_ts = time.time() - (48 * 3600)

conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
cursor = conn.cursor()

# Query handles modern HA schema (states joined with states_meta)
query = """
    SELECT 
        sm.entity_id,
        s.state,
        s.last_updated_ts
    FROM states s
    JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    WHERE s.last_updated_ts >= ?
"""
params = [cutoff_ts]

if TARGET_ENTITIES:
    placeholders = ",".join("?" for _ in TARGET_ENTITIES)
    query += f" AND sm.entity_id IN ({placeholders})"
    params.extend(TARGET_ENTITIES)

query += " ORDER BY s.last_updated_ts ASC"

cursor.execute(query, params)
rows = cursor.fetchall()

telemetry = []
for entity_id, state, ts in rows:
    telemetry.append({
        "timestamp_utc": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        "timestamp_epoch": ts,
        "entity_id": entity_id,
        "state": state,
    })

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(telemetry, f, indent=2)

print(f"Extracted {len(telemetry)} state transitions over the last 48h to {OUTPUT_FILE}")
conn.close()