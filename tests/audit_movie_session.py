"""
Audits the exact sequence of events during Stremio/Onn movie sessions.
Run: python3 ~/ha_config/tests/audit_movie_session.py
"""
import sqlite3
import os
import json

DB_PATH = os.path.expanduser("~/ha_config/home-assistant_v2.db")
conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
cursor = conn.cursor()

query = """
SELECT 
    datetime(s.last_updated_ts, 'unixepoch', 'localtime') as ts_str,
    sm.entity_id,
    s.state,
    s.attributes
FROM states s
JOIN states_meta sm ON s.metadata_id = sm.metadata_id
WHERE sm.entity_id IN (
    'sensor.mediasession2mqtt_1_playback_state',
    'remote.onn_pro',
    'media_player.onn_pro',
    'light.theater_dimmer',
    'switch.bias_lights',
    'sensor.theater_mode'
)
ORDER BY s.last_updated_ts DESC
LIMIT 60;
"""

try:
    cursor.execute(query)
    rows = cursor.fetchall()
    rows.reverse()

    print("\n==================================================")
    print("CHRONOLOGICAL MOVIE / PLAYBACK EVENT TIMELINE")
    print("==================================================")

    for ts_str, entity_id, state_val, attrs in rows:
        short_entity = entity_id.split(".")[-1]
        if short_entity == "mediasession2mqtt_1_playback_state":
            short_entity = "PLAYBACK_STATE"
        elif short_entity == "theater_dimmer":
            short_entity = "DIMMER"
        elif short_entity == "bias_lights":
            short_entity = "BIAS_LIGHT"
        elif short_entity == "theater_mode":
            short_entity = "THEATER_MODE"

        extra = ""
        attrs_str = attrs or ""

        if "brightness" in attrs_str:
            try:
                a_json = json.loads(attrs_str)
                if "brightness" in a_json:
                    pct = round((a_json["brightness"] / 255) * 100)
                    extra = f"(Brightness: {pct}%)"
            except Exception:
                pass
        elif "current_activity" in attrs_str:
            try:
                a_json = json.loads(attrs_str)
                act = a_json.get("current_activity", "")
                if act:
                    extra = f"(App: {act.split('.')[-1]})"
            except Exception:
                pass

        print(f"{ts_str} | {short_entity:<16} | {state_val:<12} {extra}")

    print("==================================================\n")

except Exception as e:
    print(f"Query error: {e}")
finally:
    conn.close()