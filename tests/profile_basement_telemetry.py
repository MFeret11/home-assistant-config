"""
Deep Hardware & Telemetry Profiler for Basement Entities
Audits Batocera current draw, PIR motion blind times, and media pause durations.
Run: python3 ~/ha_config/tests/profile_basement_telemetry.py
"""
import sqlite3
import os

DB_PATH = os.path.expanduser("~/ha_config/home-assistant_v2.db")
conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
cursor = conn.cursor()

def audit_batocera_current():
    print("==================================================")
    print("1. BATOCERA PC ELECTRICAL PROFILE (sensor.batocera_current)")
    print("==================================================")
    query = """
    SELECT s.state, s.last_updated_ts
    FROM states s
    JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    WHERE sm.entity_id = 'sensor.batocera_current'
      AND s.state NOT IN ('unavailable', 'unknown')
    ORDER BY s.last_updated_ts DESC
    LIMIT 100;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    if not rows:
        print("  No Batocera current readings recorded yet.\n")
        return

    readings = [float(r[0]) for r in rows]
    min_curr = min(readings)
    max_curr = max(readings)
    recent = readings[:10]

    print(f"  Minimum Recorded Current:  {min_curr:.3f} A ({min_curr * 120:.1f} W)")
    print(f"  Maximum Recorded Current:  {max_curr:.3f} A ({max_curr * 120:.1f} W)")
    print(f"  Active 0.05A Cutoff Rule:  {'SAFE' if min_curr < 0.05 else '⚠️ AT RISK: Min current >= 0.05A!'}")
    print("\n  Recent 10 Readings:")
    for r in recent:
        status = "GAMING/LOAD" if r > 0.3 else ("IDLE OS" if r > 0.06 else "HALTED/STANDBY")
        print(f"    {r:5.3f} A ({r*120:5.1f} W) | {status}")
    print()

def audit_pir_motion_hardware_reset():
    print("==================================================")
    print("2. PIR MOTION SENSOR RESET WINDOW (bottom_stairs)")
    print("==================================================")
    query = """
    SELECT s.state, s.last_updated_ts
    FROM states s
    JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    WHERE sm.entity_id = 'binary_sensor.bottom_stairs'
    ORDER BY s.last_updated_ts DESC
    LIMIT 60;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    rows.reverse()

    durations = []
    last_on = None

    for state_val, ts in rows:
        if state_val == 'on':
            last_on = ts
        elif state_val == 'off' and last_on:
            hold_time = ts - last_on
            if 0 < hold_time < 300:
                durations.append(hold_time)
            last_on = None

    if durations:
        avg_hold = sum(durations) / len(durations)
        print(f"  PIR Hardware Hold Time:     {avg_hold:.1f} seconds (average)")
        print(f"  Shortest Reset:             {min(durations):.1f} seconds")
        print(f"  Longest Reset:              {max(durations):.1f} seconds")
        print(f"  Direction Window Safety:    {'EXCELLENT' if avg_hold < 20 else '⚠️ CAUTION: Sensor stays high > 20s'}")
    else:
        print("  Not enough on->off transition cycles recorded.")
    print()

def audit_playback_pause_durations():
    print("==================================================")
    print("3. STREMIO PLAYBACK PAUSE PATTERNS")
    print("==================================================")
    query = """
    SELECT s.state, s.last_updated_ts
    FROM states s
    JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    WHERE sm.entity_id = 'sensor.mediasession2mqtt_1_playback_state'
    ORDER BY s.last_updated_ts DESC
    LIMIT 80;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    rows.reverse()

    pause_durations = []
    last_pause = None

    for state_val, ts in rows:
        if state_val == 'paused':
            last_pause = ts
        elif state_val == 'playing' and last_pause:
            pause_time = ts - last_pause
            if 0 < pause_time < 1800:
                pause_durations.append(pause_time)
            last_pause = None

    if pause_durations:
        seeks = [p for p in pause_durations if p < 4.0]
        real_pauses = [p for p in pause_durations if p >= 4.0]
        print(f"  Total Pauses Recorded:      {len(pause_durations)}")
        print(f"  Quick Seeks (< 4.0s):       {len(seeks)} (Intermission successfully skipped)")
        print(f"  Real Intermissions (>= 4s): {len(real_pauses)} (1% glow triggered)")
        if real_pauses:
            print(f"  Average Intermission:       {sum(real_pauses)/len(real_pauses):.1f} seconds")
    else:
        print("  Not enough media pause cycles recorded.")
    print("==================================================\n")

if __name__ == "__main__":
    try:
        audit_batocera_current()
        audit_pir_motion_hardware_reset()
        audit_playback_pause_durations()
    finally:
        conn.close()