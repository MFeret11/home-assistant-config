"""
Deep Telemetry Audit: Lamp Burn Hours, Ghost Triggers, and Hardware Response Lag.
Run: python3 ~/ha_config/tests/deep_system_telemetry.py
"""
import sqlite3
import os

DB_PATH = os.path.expanduser("~/ha_config/home-assistant_v2.db")
conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
cursor = conn.cursor()

def audit_lamp_burn_hours():
    print("==================================================")
    print("1. OPTOMA PROJECTOR LAMP RUNTIME & POWER AUDIT")
    print("==================================================")
    query = """
    SELECT 
        s.state,
        s.last_updated_ts
    FROM states s
    JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    WHERE sm.entity_id = 'sensor.projector_current'
      AND s.state NOT IN ('unavailable', 'unknown')
    ORDER BY s.last_updated_ts ASC;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    if not rows:
        print("  No projector current data found.\n")
        return

    total_active_seconds = 0.0
    watt_samples = []
    last_ts = None
    was_running = False

    for state_val, ts in rows:
        try:
            amps = float(state_val)
            is_running = amps > 0.8  # Lamp strike threshold

            if was_running and last_ts:
                delta = ts - last_ts
                # Ignore gaps > 5 mins (e.g. system reboots)
                if 0 < delta < 300:
                    total_active_seconds += delta
                    watt_samples.append(amps * 120.0)

            was_running = is_running
            last_ts = ts
        except ValueError:
            pass

    burn_hours = total_active_seconds / 3600.0
    avg_watts = (sum(watt_samples) / len(watt_samples)) if watt_samples else 0.0

    print(f"  Recorded Lamp Burn Time:    {burn_hours:.2f} hours (over recorded history)")
    print(f"  Average Running Draw:       {avg_watts:.1f} Watts (~{avg_watts/120:.2f} A)")
    if avg_watts > 0:
        lamp_mode = "Eco / Dynamic" if avg_watts < 225 else "Bright / Standard"
        print(f"  Detected Projector Mode:    {lamp_mode}")
    print()

def audit_ghost_triggers_late_night():
    print("==================================================")
    print("2. GHOST LIGHTING & PIR AUDIT (1:00 AM - 5:30 AM)")
    print("==================================================")
    query = """
    SELECT 
        datetime(s.last_updated_ts, 'unixepoch', 'localtime') as ts_str,
        sm.entity_id,
        s.state
    FROM states s
    JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    WHERE sm.entity_id IN (
        'light.theater_dimmer',
        'light.stairlights',
        'light.zigbee_basement_lights',
        'binary_sensor.bottom_stairs'
    )
      AND s.state = 'on'
      AND time(s.last_updated_ts, 'unixepoch', 'localtime') >= '01:00:00'
      AND time(s.last_updated_ts, 'unixepoch', 'localtime') <= '05:30:00'
    ORDER BY s.last_updated_ts DESC
    LIMIT 20;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    if not rows:
        print("  ✓ Zero ghost triggers! The basement was 100% dark and quiet between 1:00 AM and 5:30 AM.\n")
        return

    print(f"  ⚠️  Found {len(rows)} late-night activation events:")
    for ts_str, entity_id, state_val in rows:
        name = entity_id.split(".")[-1]
        print(f"    {ts_str} | {name:<26} | turned ON")
    print()

def audit_network_hardware_delay():
    print("==================================================")
    print("3. COMMAND-TO-STATE ACKNOWLEDGMENT DELAYS")
    print("==================================================")
    # Check average interval between playback state hitting 'playing' and lights acknowledging 'off'
    query = """
    SELECT 
        s1.last_updated_ts,
        s2.last_updated_ts,
        sm2.entity_id
    FROM states s1
    JOIN states_meta sm1 ON s1.metadata_id = sm1.metadata_id
    JOIN states s2 ON s2.last_updated_ts >= s1.last_updated_ts 
                  AND s2.last_updated_ts <= s1.last_updated_ts + 5
    JOIN states_meta sm2 ON s2.metadata_id = sm2.metadata_id
    WHERE sm1.entity_id = 'sensor.mediasession2mqtt_1_playback_state'
      AND s1.state = 'playing'
      AND sm2.entity_id IN ('light.theater_dimmer', 'switch.bias_lights')
      AND s2.state IN ('off', 'on')
    ORDER BY s1.last_updated_ts DESC
    LIMIT 15;
    """
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        if rows:
            delays = [abs(r[1] - r[0]) for r in rows]
            avg_delay = sum(delays) / len(delays)
            print(f"  Cinema Sync Lag:            {avg_delay:.2f} seconds")
            print(f"  Fastest Response:           {min(delays):.2f} seconds")
            print(f"  Slowest Response:           {max(delays):.2f} seconds")
        else:
            print("  Not enough recent synchronized transitions to benchmark.")
    except Exception as e:
        print(f"  Query note: {e}")
    print("==================================================\n")

if __name__ == "__main__":
    try:
        audit_lamp_burn_hours()
        audit_ghost_triggers_late_night()
        audit_network_hardware_delay()
    finally:
        conn.close()