import sqlite3
import json
from datetime import datetime

DB_PATH = "/var/lib/docker/volumes/septa-project_ha_config/_data/home-assistant_v2.db"

conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
cursor = conn.cursor()

query = """
    SELECT 
        s.state,
        s.last_updated_ts,
        sa.shared_attrs
    FROM states s
    JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    LEFT JOIN state_attributes sa ON s.attributes_id = sa.attributes_id
    WHERE sm.entity_id = 'sensor.philadelphia_eagles'
      AND s.last_updated_ts > strftime('%s', 'now', '-7 days')
    ORDER BY s.last_updated_ts ASC;
"""

cursor.execute(query)
rows = cursor.fetchall()

if not rows:
    print("No Eagles telemetry recorded in the last 7 days.")
    exit()

print("=" * 65)
print("             PHILADELPHIA EAGLES TELEMETRY REPLAY            ")
print("=" * 65)

game_started = None
game_ended = None
last_score = -1

for state_val, ts, attrs_json in rows:
    t_str = datetime.fromtimestamp(ts).strftime("%a %b %d %I:%M:%S %p")
    attrs = json.loads(attrs_json) if attrs_json else {}

    team_score = attrs.get("team_score", "0")
    opp_score = attrs.get("opponent_score", "0")
    quarter = attrs.get("quarter", "")
    clock = attrs.get("clock", "")
    opp_name = attrs.get("opponent_name", "Opponent")

    # Detect Game Start
    if state_val == "IN" and not game_started:
        game_started = ts
        print(f"\n🏈 [KICKOFF] {t_str} vs {opp_name}")
        print("-" * 65)

    # Detect Score Change
    try:
        current_score = int(team_score)
        if state_val == "IN" and current_score != last_score and last_score != -1:
            delta = current_score - last_score
            event_type = "🚨 TOUCHDOWN!" if delta >= 6 else f"🎯 Field Goal/Score (+{delta})"
            print(f"  {t_str} | Q{quarter} {clock} | {event_type} | PHI {team_score} - {opp_score} {opp_name}")
        last_score = current_score
    except (ValueError, TypeError):
        pass

    # Detect Game End
    if state_val == "POST" and not game_ended and game_started:
        game_ended = ts
        duration_hrs = round((game_ended - game_started) / 3600.0, 2)
        print("-" * 65)
        print(f"🏁 [FINAL] {t_str} | Final Score: PHI {team_score} - {opp_score} {opp_name}")
        print(f"⏱️ Total Game Broadcast Duration: {duration_hrs} hours")
        print("=" * 65)

conn.close()