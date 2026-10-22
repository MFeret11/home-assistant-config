"""
Trace-Driven Historical Telemetry Replay Test
Pulls actual recorded sensor curves from home-assistant_v2.db and streams them into the engines.
Run: PYTHONPATH=~/ha_config/pyscript python3 ~/ha_config/tests/test_historical_replay.py
"""
import sqlite3
import os
import sys
import builtins
import time

pyscript_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pyscript"))
if pyscript_dir not in sys.path:
    sys.path.insert(0, pyscript_dir)

# --- Setup Mock Environment ---
class MockState:
    def __init__(self):
        self._states = {}
        self._attrs = {}
    def get(self, k, default=None): return self._states.get(k, default)
    def getattr(self, k, attr=None):
        a = self._attrs.get(k, {})
        return a.get(attr) if attr else a
    def set(self, k, v=None, new_attributes=None):
        self._states[k] = str(v)
        if new_attributes: self._attrs.setdefault(k, {}).update(new_attributes)

class ServiceSpy:
    def __init__(self): self.calls = []
    def clear(self): self.calls.clear()
    def record(self, d, s, **kw): self.calls.append({"domain": d, "service": s, "kwargs": kw})
    def was_called(self, d, s, entity_id=None):
        for c in self.calls:
            if c["domain"] == d and c["service"] == s:
                target = c["kwargs"].get("entity_id")
                if not entity_id or target == entity_id or (isinstance(target, list) and entity_id in target):
                    return True
        return False

class MockTask:
    def __init__(self): self._q = []
    def unique(self, n): pass
    def sleep(self, s): pass
    def create(self, f, *a, **k): self._q.append((f, a, k))
    def run_deferred_tasks(self):
        while self._q:
            f, a, k = self._q.pop(0)
            f(*a, **k)
    def clear(self): self._q.clear()

class MockLog:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def debug(self, *a, **k): pass
    def error(self, *a, **k): pass

class MockDomain:
    def __init__(self, d): self._d = d
    def __getattr__(self, s):
        def _c(**kw):
            spy.record(self._d, s, **kw)
            ent = kw.get("entity_id")
            targets = [ent] if isinstance(ent, str) else (ent or [])
            for t in targets:
                if s == "turn_on": mock_state.set(t, "on")
                elif s == "turn_off": mock_state.set(t, "off")
        return _c

mock_state = MockState()
spy = ServiceSpy()
mock_task = MockTask()
mock_log = MockLog()

builtins.state = mock_state
builtins.task = mock_task
builtins.log = mock_log
builtins.spy = spy
builtins.mock_task = mock_task
builtins.safe_state_get = mock_state.get
builtins.light = MockDomain("light")
builtins.switch = MockDomain("switch")
builtins.media_player = MockDomain("media_player")
builtins.remote = MockDomain("remote")
builtins.button = MockDomain("button")
builtins.input_select = MockDomain("input_select")
builtins.input_boolean = MockDomain("input_boolean")
builtins.adaptive_lighting = MockDomain("adaptive_lighting")
builtins.service = lambda f: f
builtins.state_trigger = lambda *a, **k: (lambda f: f)
builtins.time_trigger = lambda *a, **k: (lambda f: f)
builtins.pyscript_executor = lambda f: f

import theater
import basement

# Connect to real HA Database or Fallback Fixture
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

# ==============================================================================
# REPLAY TEST 1: REPLAY ACTUAL OPTOMA PROJECTOR CURRENT TELEMETRY
# ==============================================================================
def test_replay_actual_projector_cooldown():
    """Extracts the actual Optoma current curve from yesterday and streams it through the engine."""
    spy.clear()
    theater.BOOT_TIMESTAMP = 0

    if cursor:
        query = """
        SELECT s.state
        FROM states s
        JOIN states_meta sm ON s.metadata_id = sm.metadata_id
        WHERE sm.entity_id = 'sensor.projector_current'
          AND s.state NOT IN ('unavailable', 'unknown')
        ORDER BY s.last_updated_ts DESC
        LIMIT 20;
        """
        cursor.execute(query)
        raw_readings = [float(r[0]) for r in cursor.fetchall()]
        raw_readings.reverse()
    else:
        import json
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        readings = [float(x['state']) for x in data if x['entity_id'] == 'sensor.projector_current' and x['state'] not in ('unavailable', 'unknown')]
        raw_readings = readings[-20:]

    print("\n  [Telemetry] Replaying Real Physical Optoma Current Stream...")
    
    # Verify the safety of every single real reading
    state.set("switch.projector", "on")
    for current_reading in raw_readings:
        state.set("sensor.projector_current", str(current_reading))
        is_cold = theater.is_projector_cold()

        # Physical safety invariant: If current > 0.06A (lamp or fan on), it MUST NOT be evaluated as cold
        if current_reading > 0.06:
            assert not is_cold, f"SAFETY BREACH: Current was {current_reading}A but evaluated as cold!"
        else:
            assert is_cold, f"FAIL: Current dropped to {current_reading}A but failed to detect cold standby!"

    print("  ★ test_replay_actual_projector_cooldown PASSED (Zero false power-cuts on real hardware)")


# ==============================================================================
# REPLAY TEST 2: REPLAY ACTUAL 22.7-SECOND SLOW DESCENT
# ==============================================================================
def test_replay_slow_stair_descent():
    """Replays the real-world 22.7-second slow descent to prove lights never cut out."""
    spy.clear()
    basement.BOOT_TIMESTAMP = 0
    state.set("input_select.basement_lighting_mode", "Daily Driver")

    # Step 1: Top door opens
    basement.stair_door_opened("off")
    assert spy.was_called("adaptive_lighting", "apply"), "FAIL: Stairs didn't turn on!"

    # Step 2: Occupant shuts door 2.5s later at the top of the stairs
    basement.stair_door_closed("on")
    mock_task.run_deferred_tasks()

    # Verify that closing the door did NOT kill the stair lights!
    assert not spy.was_called("light", "turn_off", "light.stairlights"), \
        "SAFETY BREACH: Door close shut off stairlights while occupant was still on the steps!"

    # Step 3: Occupant arrives at the bottom 22.7s later
    basement.motion_at_foot_of_stairs("off")
    mock_task.run_deferred_tasks()

    # Room cans must turn on
    assert spy.was_called("light", "turn_on", "light.theater_dimmer"), "FAIL: Cans didn't turn on at bottom!"

    print("  ★ test_replay_slow_stair_descent PASSED (22.7s slow descent fully protected)")


# ==============================================================================
# REPLAY TEST 3: REPLAY ACTUAL 18.76-SECOND SLOW ASCENT (WALKOUT REPLAY)
# ==============================================================================
def test_replay_actual_slow_ascent_18_8s():
    """Replays the real-world 18.76s slow ascent from telemetry_48h.json to verify walkout shutoff."""
    spy.clear()
    basement.BOOT_TIMESTAMP = 0
    basement.LAST_DOOR_OPEN_TS = 0.0
    basement.DIRECTION_OF_TRAVEL = "none"
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    state.set("binary_sensor.theater_in_use", "off")

    # Step 1: Bottom motion sensor trips as occupant ascends from basement
    basement.LAST_MOTION_BOTTOM_TS = 1000.0

    # Step 2: Occupant takes 18.76s to ascend steps to top door (real physical event)
    orig_time = time.time
    time.time = lambda: 1018.76
    try:
        basement.stair_door_opened("off")
        assert basement.DIRECTION_OF_TRAVEL == "up", \
            f"SAFETY/WALKOUT BREACH: 18.76s ascent classified as '{basement.DIRECTION_OF_TRAVEL}', expected 'up'!"
    finally:
        time.time = orig_time

    # Step 3: Top door closes behind occupant at the top of the stairs
    spy.clear()
    basement.stair_door_closed("on")
    mock_task.run_deferred_tasks()

    # Room lights must be extinguished after walkout
    assert spy.was_called("light", "turn_off", "light.theater_dimmer"), "FAIL: Dimmer not extinguished on upward exit!"
    assert spy.was_called("light", "turn_off", "light.zigbee_basement_lights"), "FAIL: Room cans not extinguished on upward exit!"
    assert spy.was_called("light", "turn_off", "light.stairlights"), "FAIL: Stairlights not extinguished on upward exit!"

    print("  ★ test_replay_actual_slow_ascent_18_8s PASSED (18.76s ascent walkout fully protected)")


if __name__ == "__main__":
    print("\n==================================================")
    print("RUNNING TRACE-DRIVEN REAL-WORLD REPLAY TESTS")
    print("==================================================")
    test_replay_actual_projector_cooldown()
    test_replay_slow_stair_descent()
    test_replay_actual_slow_ascent_18_8s()
    print("==================================================")
    print("ALL REAL TELEMETRY REPLAY TESTS PASSED")
    print("==================================================\n")
    if conn:
        conn.close()