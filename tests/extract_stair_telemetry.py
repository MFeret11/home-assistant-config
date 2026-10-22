"""
Extracts actual historical walking speeds between the top door and bottom stairs.
Run: python3 ~/ha_config/tests/extract_stair_telemetry.py
"""
import sqlite3
import os

DB_PATH = os.path.expanduser("~/ha_config/home-assistant_v2.db")
conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
cursor = conn.cursor()

query = """
SELECT 
    sm.entity_id,
    s.state,
    s.last_updated_ts,
    datetime(s.last_updated_ts, 'unixepoch', 'localtime') as ts_str
FROM states s
JOIN states_meta sm ON s.metadata_id = sm.metadata_id
WHERE sm.entity_id IN ('binary_sensor.basement_stairs_door_sensor', 'binary_sensor.bottom_stairs')
  AND s.state = 'on'
ORDER BY s.last_updated_ts DESC
LIMIT 40;
"""

try:
    cursor.execute(query)
    events = cursor.fetchall()
    events.reverse()

    print("\n==================================================")
    print("REAL-WORLD STAIRCASE TRANSIT TELEMETRY")
    print("==================================================")

    last_door_ts = None
    last_motion_ts = None

    for entity_id, state_val, ts, ts_str in events:
        short_name = "DOOR OPENED " if "door" in entity_id else "BOTTOM MOTION"
        
        if "door" in entity_id:
            last_door_ts = ts
            delta = f"(+{ts - last_motion_ts:4.1f}s after bottom)" if last_motion_ts and (0 < ts - last_motion_ts < 40) else ""
            direction = "▲ EXITING UP" if delta else ""
            print(f"{ts_str} | {short_name} {delta:<25} {direction}")
        else:
            last_motion_ts = ts
            delta = f"(+{ts - last_door_ts:4.1f}s after door)" if last_door_ts and (0 < ts - last_door_ts < 40) else ""
            direction = "▼ ENTERING DOWN" if delta else ""
            print(f"{ts_str} | {short_name} {delta:<25} {direction}")

    print("==================================================\n")

except Exception as e:
    print(f"Query error: {e}")
finally:
    conn.close()