import sqlite3
from datetime import datetime

DB_PATH = "/var/lib/docker/volumes/septa-project_ha_config/_data/home-assistant_v2.db"

KNOWN_CLIENTS = {
    "192.168.1.216": "Basement Theater (Onn Pro)",
    "100.82.195.2": "Remote Stream (Jellyfin / Tailscale)",
}

conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
cursor = conn.cursor()

query = """
    SELECT 
        sm.entity_id,
        s.state,
        s.last_updated_ts
    FROM states s
    JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    WHERE sm.entity_id IN ('sensor.tuner0', 'sensor.tuner1')
      AND s.last_updated_ts > strftime('%s', 'now', '-7 days')
    ORDER BY sm.entity_id, s.last_updated_ts ASC;
"""

cursor.execute(query)
rows = cursor.fetchall()

if not rows:
    print("No tuner telemetry found.")
    exit()

print("=" * 75)
print("             HDHOMERUN BROADCAST AIRTIME AUDIT (LAST 7 DAYS)         ")
print("=" * 75)

sessions = []
current_session = None

for tuner, channel, ts in rows:
    if channel.lower() in ["idle", "off", "unavailable", "unknown", ""]:
        if current_session:
            sessions.append(current_session)
            current_session = None
        continue

    if current_session is None:
        current_session = {
            "tuner": tuner,
            "channel": channel,
            "start_ts": ts,
            "end_ts": ts,
        }
    elif current_session["channel"] == channel and (ts - current_session["end_ts"]) <= 60:
        current_session["end_ts"] = ts
    else:
        sessions.append(current_session)
        current_session = {
            "tuner": tuner,
            "channel": channel,
            "start_ts": ts,
            "end_ts": ts,
        }

if current_session:
    sessions.append(current_session)

# Filter out sessions < 1 minute (surfing)
sessions = [s for s in sessions if (s["end_ts"] - s["start_ts"]) >= 60]

for s in reversed(sessions):
    duration_min = round((s["end_ts"] - s["start_ts"]) / 60.0, 1)
    duration_hrs = round(duration_min / 60.0, 2)
    start_str = datetime.fromtimestamp(s["start_ts"]).strftime("%a %b %d %I:%M %p")
    end_str = datetime.fromtimestamp(s["end_ts"]).strftime("%I:%M %p")

    print(f"📺 [{s['tuner'].upper()}] {s['channel']}")
    print(f"   Aired:    {start_str}  →  {end_str}")
    print(f"   Airtime:  {duration_hrs} hrs ({duration_min} mins)")
    print("-" * 75)

conn.close()