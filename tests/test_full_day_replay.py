"""
Replays all physical events from September 10th from home-assistant_v2.db
Run: PYTHONPATH=~/ha_config/pyscript python3 ~/ha_config/tests/test_full_day_replay.py
"""
import sqlite3
import os
import sys
import builtins

pyscript_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pyscript"))
if pyscript_dir not in sys.path:
    sys.path.insert(0, pyscript_dir)

# --- Fast Mock Harness ---
class MockState:
    def __init__(self): self._s = {}; self._a = {}
    def get(self, k, default=None): return self._s.get(k, default)
    def getattr(self, k, attr=None): a = self._a.get(k, {}); return a.get(attr) if attr else a
    def set(self, k, v=None, new_attributes=None):
        self._s[k] = str(v)
        if new_attributes: self._a.setdefault(k, {}).update(new_attributes)

class ServiceSpy:
    def __init__(self): self.calls = []
    def clear(self): self.calls.clear()
    def record(self, d, s, **kw): self.calls.append({"domain": d, "service": s, "kwargs": kw})

class MockTask:
    def unique(self, n): pass
    def sleep(self, s): pass
    def create(self, f, *a, **k): return f(*a, **k)

mock_state = MockState()
spy = ServiceSpy()
mock_task = MockTask()

builtins.state = mock_state
builtins.task = mock_task
builtins.log = type('MockLog', (), {'info': lambda *a: None, 'warning': lambda *a: None, 'debug': lambda *a: None, 'error': lambda *a: None})()
builtins.spy = spy
builtins.mock_task = mock_task
builtins.safe_state_get = mock_state.get

class MockDomain:
    def __init__(self, d): self._d = d
    def __getattr__(self, s):
        def _c(**kw):
            spy.record(self._d, s, **kw)
            ent = kw.get("entity_id")
            for t in ([ent] if isinstance(ent, str) else (ent or [])):
                if s == "turn_on": mock_state.set(t, "on")
                elif s == "turn_off": mock_state.set(t, "off")
        return _c

for d in ["light", "switch", "media_player", "remote", "button", "input_select", "input_boolean", "adaptive_lighting"]:
    setattr(builtins, d, MockDomain(d))

builtins.service = lambda f: f
builtins.state_trigger = lambda *a, **k: (lambda f: f)
builtins.time_trigger = lambda *a, **k: (lambda f: f)
builtins.pyscript_executor = lambda f: f

import theater
import basement

# Connect to Database or Fallback Fixture
DB_PATH = os.path.expanduser("~/ha_config/home-assistant_v2.db")
JSON_PATH = os.path.join(os.path.dirname(__file__), "telemetry_48h.json")
conn = None
cursor = None
if os.path.exists(DB_PATH):
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cursor = conn.cursor()
    except Exception:
        conn = None
        cursor = None

def run_full_day_replay():
    print("\n==================================================")
    print("REPLAYING 24-HOUR PHYSICAL EVENT TIMELINE")
    print("==================================================")
    
    events = []
    if cursor:
        query = """
        SELECT 
            sm.entity_id,
            s.state,
            s.last_updated_ts,
            datetime(s.last_updated_ts, 'unixepoch', 'localtime') as ts_str
        FROM states s
        JOIN states_meta sm ON s.metadata_id = sm.metadata_id
        WHERE sm.entity_id IN (
            'binary_sensor.basement_stairs_door_sensor',
            'binary_sensor.bottom_stairs',
            'media_player.theater_receiver',
            'media_player.theater_onn_pro_adb',
            'sensor.batocera_state'
        )
        ORDER BY s.last_updated_ts ASC;
        """
        cursor.execute(query)
        events = cursor.fetchall()
    else:
        import json
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        tracked = {
            'binary_sensor.basement_stairs_door_sensor',
            'binary_sensor.bottom_stairs',
            'media_player.theater_receiver',
            'media_player.theater_onn_pro_adb',
            'sensor.batocera_state'
        }
        for item in data:
            if item.get("entity_id") in tracked:
                events.append((
                    item["entity_id"],
                    item["state"],
                    item.get("timestamp_epoch", 0),
                    item.get("timestamp_utc", "")
                ))
    
    theater.BOOT_TIMESTAMP = 0
    basement.BOOT_TIMESTAMP = 0
    state.set("input_select.basement_lighting_mode", "Daily Driver")

    event_count = len(events)
    print(f"  Streaming {event_count} physical hardware events through Pyscript engines...")

    door_events = 0
    motion_events = 0
    media_events = 0

    for entity_id, state_val, ts, ts_str in events:
        old_state = state.get(entity_id, "off")
        state.set(entity_id, state_val)

        # Replay event to the appropriate trigger function
        if entity_id == "binary_sensor.basement_stairs_door_sensor":
            door_events += 1
            if state_val == "on":
                basement.stair_door_opened(old_state)
            else:
                basement.stair_door_closed(old_state)
        elif entity_id == "binary_sensor.bottom_stairs" and state_val == "on":
            motion_events += 1
            basement.motion_at_foot_of_stairs(old_state)
        elif entity_id in ["media_player.theater_onn_pro_adb", "sensor.batocera_state"]:
            media_events += 1
            basement.theater_lighting_sync()

    print(f"\n  ✓ Processed {door_events} Door Transits")
    print(f"  ✓ Processed {motion_events} Foot-of-Stair Trips")
    print(f"  ✓ Processed {media_events} Media Playback Transitions")
    print("==================================================")
    print("24-HOUR HISTORICAL REPLAY PASSED WITH ZERO CRASHES")
    print("==================================================\n")

if __name__ == "__main__":
    try:
        run_full_day_replay()
    finally:
        if conn:
            conn.close()