#!/usr/bin/env python3
import sqlite3, os, sys, json, argparse
from datetime import datetime, timezone

DB_PATH = os.path.expanduser("~/ha_config/home-assistant_v2.db")
TARGET_ENTITIES = [
    "sensor.mediasession2mqtt_1_media_title", "sensor.mediasession2mqtt_media_title",
    "sensor.mediasession2mqtt_1_media_artist", "sensor.mediasession2mqtt_media_artist",
    "sensor.mediasession2mqtt_1_playback_state", "sensor.mediasession2mqtt_playback_state",
    "sensor.mediasession2mqtt_1_application_id", "sensor.mediasession2mqtt_application_id",
    "media_player.onn_pro", "media_player.onn_pro_2", "remote.onn_pro", "media_player.whole_house_spotify",
    "sensor.batocera_state", "sensor.batocera_current_game", "sensor.batocera_system", "sensor.batocera_current",
    "sensor.desktop_rspn8nu_activewindow", "sensor.desktop_rspn8nu_gputemperature",
    "binary_sensor.gaming_pc_online", "switch.gaming_pc",
    "sensor.theater_mode", "binary_sensor.theater_in_use",
    "sensor.theater_current_poster", "sensor.theater_current_boxart",
    "light.theater_dimmer", "switch.bias_lights",
]

parser = argparse.ArgumentParser()
parser.add_argument("--hours", type=float, default=24)
args = parser.parse_args()

if not os.path.exists(DB_PATH):
    print(f"❌ DB not found at {DB_PATH}")
    sys.exit(1)

cutoff_ts = datetime.now(timezone.utc).timestamp() - (args.hours * 3600)
conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
cursor = conn.cursor()
placeholders = ",".join("?" for _ in TARGET_ENTITIES)
query = f"""
SELECT datetime(s.last_updated_ts, 'unixepoch', 'localtime'), sm.entity_id, s.state, s.attributes
FROM states s JOIN states_meta sm ON s.metadata_id = sm.metadata_id
WHERE sm.entity_id IN ({placeholders}) AND s.last_updated_ts >= ?
  AND s.state NOT IN ('unavailable', 'unknown', 'None', '')
ORDER BY s.last_updated_ts ASC;
"""
cursor.execute(query, [*TARGET_ENTITIES, cutoff_ts])
rows = cursor.fetchall()
conn.close()

print(f"\n{'='*75}\nCHRONOLOGICAL MEDIA & GAMING TIMELINE (Last {args.hours}h: {len(rows)} events)\n{'='*75}")
for ts_local, entity_id, state_val, attrs_raw in rows:
    short_id = entity_id.replace("sensor.", "").replace("binary_sensor.", "").replace("media_player.", "")
    extra = ""
    attrs = json.loads(attrs_raw) if attrs_raw else {}
    if "media_title" in entity_id or "title" in entity_id:
        extra = f"🎬 TITLE: '{state_val}'"
    elif "application_id" in entity_id:
        extra = f"📱 APP: {state_val}"
    elif "activewindow" in entity_id:
        extra = f"🖥️ PC WINDOW: '{state_val}'"
    elif "batocera_current_game" in entity_id:
        extra = f"🕹️ ROM: '{state_val}'"
    elif "batocera_system" in entity_id:
        extra = f"🎮 SYSTEM: {state_val}"
    elif "theater_current_poster" in entity_id:
        extra = f"🖼️ MARQUEE -> '{attrs.get('title','')}' [{attrs.get('media_type','')} via {attrs.get('source','')}]"
    elif "theater_current_boxart" in entity_id:
        extra = f"📦 BOXART -> '{attrs.get('title','')}' [via {attrs.get('source','')}]"
    elif "theater_mode" in entity_id:
        extra = f"🎯 MODE -> {state_val.upper()}"
    elif "playback_state" in entity_id:
        extra = f"⏯️ PLAYBACK: {state_val}"
    print(f"{ts_local} | {short_id:<28} | {state_val:<14} | {extra}")
print(f"{'='*75}\n")
