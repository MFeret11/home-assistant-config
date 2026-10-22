"""
Extracts actual historical current telemetry from Home Assistant's SQLite DB.
Run: python3 ~/ha_config/tests/extract_real_telemetry.py
"""
import sqlite3
import os
import sys

DB_PATH = os.path.expanduser("~/ha_config/home-assistant_v2.db")

if not os.path.exists(DB_PATH):
    print(f"❌ Could not find database at {DB_PATH}")
    sys.exit(1)

conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)  # Read-only mode
cursor = conn.cursor()

print(f"✓ Connected to Home Assistant Database ({os.path.getsize(DB_PATH) / (1024*1024):.1f} MB)\n")

# Query recent history for projector current
query = """
SELECT 
    datetime(s.last_updated_ts, 'unixepoch', 'localtime') as timestamp,
    s.state
FROM states s
JOIN states_meta sm ON s.metadata_id = sm.metadata_id
WHERE sm.entity_id = 'sensor.projector_current'
  AND s.state NOT IN ('unavailable', 'unknown')
ORDER BY s.last_updated_ts DESC
LIMIT 25;
"""

try:
    cursor.execute(query)
    rows = cursor.fetchall()
    if not rows:
        # Fallback for older HA schemas
        query_fallback = """
        SELECT last_updated, state 
        FROM states 
        WHERE entity_id = 'sensor.projector_current'
          AND state NOT IN ('unavailable', 'unknown')
        ORDER BY last_updated_ts DESC
        LIMIT 25;
        """
        cursor.execute(query_fallback)
        rows = cursor.fetchall()

    print("==================================================")
    print("LAST 25 PHYSICAL OPTOMA PROJECTOR CURRENT READINGS")
    print("==================================================")
    for ts, current in reversed(rows):
        val = float(current)
        bar = "█" * int(val * 15)
        status = "LAMP ON" if val > 0.8 else ("FAN COOLDOWN" if val > 0.06 else "COLD STANDBY")
        print(f"{ts} | {val:5.2f} A | {status:<12} | {bar}")
    print("==================================================\n")

except Exception as e:
    print(f"Query error: {e}")
finally:
    conn.close()