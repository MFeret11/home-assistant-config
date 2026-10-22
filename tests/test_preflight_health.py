"""
Preflight Health & Resilience Audit Test Suite.
Verifies continuous system integrity, critical entity availability,
hardware state reconciliation, and metadata sanitization.

Run: PYTHONPATH=~/ha_config/pyscript python3 ~/ha_config/tests/test_preflight_health.py
"""
import sys
import os
import time
import builtins

pyscript_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pyscript"))
if pyscript_dir not in sys.path:
    sys.path.insert(0, pyscript_dir)

# --- Stateful Mock Runtime ---
class MockState:
    def __init__(self):
        self._states = {}
        self._attrs = {}

    def get(self, entity_id, default=None):
        return self._states.get(entity_id, default)

    def getattr(self, entity_id, attr=None):
        entity_attrs = self._attrs.get(entity_id, {})
        return entity_attrs.get(attr) if attr else entity_attrs

    def set(self, entity_id, value=None, new_attributes=None, **kwargs):
        self._states[entity_id] = str(value)
        attrs = new_attributes or kwargs.get("attributes")
        if attrs:
            self._attrs.setdefault(entity_id, {}).update(attrs)


class ServiceSpy:
    def __init__(self):
        self.calls = []

    def clear(self):
        self.calls.clear()

    def record(self, domain, service, **kwargs):
        self.calls.append({"domain": domain, "service": service, "kwargs": kwargs})

    def was_called(self, domain, service, entity_id=None):
        for call in self.calls:
            if call["domain"] == domain and call["service"] == service:
                if entity_id is None:
                    return True
                target = call["kwargs"].get("entity_id")
                if target == entity_id or (isinstance(target, list) and entity_id in target):
                    return True
        return False


class MockTask:
    def unique(self, name): pass
    def sleep(self, seconds): pass
    def create(self, func, *args, **kwargs):
        func(*args, **kwargs)


class MockLog:
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def debug(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass


class MockDomain:
    def __init__(self, domain_name):
        self._domain = domain_name

    def __getattr__(self, service_name):
        def _callable(*args, **kwargs):
            spy.record(self._domain, service_name, args=args, **kwargs)
            # Update mock state the way real HA would (matches test_theater_basement.py)
            entity_id = kwargs.get("entity_id")
            targets = [entity_id] if isinstance(entity_id, str) else (entity_id or [])
            for target in targets:
                if service_name == "turn_on":
                    mock_state.set(target, "on")
                elif service_name == "turn_off":
                    mock_state.set(target, "off")
                elif service_name == "select_option" and kwargs.get("option"):
                    mock_state.set(target, kwargs["option"])
                elif service_name == "set_value" and kwargs.get("value") is not None:
                    mock_state.set(target, str(kwargs["value"]))
        return _callable


mock_state = MockState()
spy = ServiceSpy()
mock_task = MockTask()
mock_log = MockLog()

builtins.state = mock_state
builtins.task = mock_task
builtins.log = mock_log
builtins.service = MockDomain("service")
builtins.recorder = MockDomain("recorder")
builtins.media_player = MockDomain("media_player")
builtins.light = MockDomain("light")
builtins.switch = MockDomain("switch")
builtins.remote = MockDomain("remote")
builtins.notify = MockDomain("notify")
builtins.input_select = MockDomain("input_select")
builtins.input_boolean = MockDomain("input_boolean")
builtins.input_number = MockDomain("input_number")
builtins.rest_command = MockDomain("rest_command")
builtins.adaptive_lighting = MockDomain("adaptive_lighting")
builtins.button = MockDomain("button")

builtins.service_decorator = lambda f: f
builtins.service = lambda f: f
builtins.state_trigger = lambda *a, **k: (lambda f: f)
builtins.time_trigger = lambda *a, **k: (lambda f: f)
builtins.pyscript_executor = lambda f: f

import health_check
import theater


def setup_healthy_environment():
    mock_state._states.clear()
    mock_state._attrs.clear()
    spy.clear()

    # Seed all critical entities as nominal
    mock_state.set("media_player.theater_receiver", "off", {"source": "HDMI1"})
    mock_state.set("switch.projector", "off")
    mock_state.set("sensor.projector_current_rounded", "0.0")
    mock_state.set("sensor.projector_power_state", "standby")
    mock_state.set("binary_sensor.theater_in_use", "off")
    mock_state.set("light.theater_dimmer", "off")
    mock_state.set("light.zigbee_basement_lights", "off")
    mock_state.set("light.stairlights", "off")
    mock_state.set("binary_sensor.bottom_stairs", "off")
    mock_state.set("binary_sensor.basement_stairs_door_sensor", "off")
    mock_state.set("input_select.basement_theater_mode", "Off")
    mock_state.set("input_select.basement_lighting_mode", "Daily Driver")


def test_preflight_diagnostics_all_healthy():
    setup_healthy_environment()
    res = health_check.run_preflight_diagnostics()

    assert res["status"] == "healthy", f"Expected healthy status, got {res['status']}"
    assert res["healthy_count"] == len(health_check.CRITICAL_ENTITIES)
    assert len(res["unavailable_items"]) == 0
    assert len(res["missing_items"]) == 0
    assert mock_state.get("sensor.basement_automation_health") == "healthy"
    print("  ✓ [Preflight] test_preflight_diagnostics_all_healthy PASSED (100% nominal)")


def test_preflight_diagnostics_degraded_on_unavailable():
    setup_healthy_environment()
    mock_state.set("switch.projector", "unavailable")

    res = health_check.run_preflight_diagnostics()
    assert res["status"] == "degraded", f"Expected degraded status, got {res['status']}"
    assert len(res["unavailable_items"]) == 1
    assert "switch.projector" in res["unavailable_items"][0]
    assert mock_state.get("sensor.basement_automation_health") == "degraded"
    print("  ✓ [Preflight] test_preflight_diagnostics_degraded_on_unavailable PASSED")


def test_preflight_diagnostics_error_on_missing():
    setup_healthy_environment()
    del mock_state._states["media_player.theater_receiver"]

    res = health_check.run_preflight_diagnostics()
    assert res["status"] == "error", f"Expected error status, got {res['status']}"
    assert len(res["missing_items"]) == 1
    assert "media_player.theater_receiver" in res["missing_items"][0]
    assert mock_state.get("sensor.basement_automation_health") == "error"
    print("  ✓ [Preflight] test_preflight_diagnostics_error_on_missing PASSED")


def test_theater_force_reconcile_when_active():
    setup_healthy_environment()
    mock_state.set("media_player.theater_receiver", "on", {"source": "HDMI1"})
    mock_state.set("sensor.mediasession2mqtt_1_application_id", "com.stremio.one")
    mock_state.set("sensor.mediasession2mqtt_1_media_title", "Dune Part Two")

    theater.theater_force_reconcile()

    assert mock_state.get("binary_sensor.theater_in_use") == "on"
    assert mock_state.get("sensor.theater_mode") == "movie"
    assert mock_state.get("input_select.basement_theater_mode") == "Movie"
    print("  ✓ [Reconcile] test_theater_force_reconcile_when_active PASSED (state resynced to movie)")


def test_theater_force_reconcile_when_off():
    setup_healthy_environment()
    mock_state.set("media_player.theater_receiver", "off")
    mock_state.set("sensor.theater_mode", "movie")
    mock_state.set("binary_sensor.theater_in_use", "on")

    theater.theater_force_reconcile()

    assert mock_state.get("binary_sensor.theater_in_use") == "off"
    assert mock_state.get("sensor.theater_mode") == "off"
    assert mock_state.get("input_select.basement_theater_mode") == "Off"
    print("  ✓ [Reconcile] test_theater_force_reconcile_when_off PASSED (state reset to off)")


def test_edge_case_media_candidate_sanitization():
    cases = [
        ("Movie.Title.2023.1080p.WEBRip.x265.mkv", "Movie Title"),
        ("Show.Name.S02E04.720p.HDTV.ts", ["Show Name", "Show Name S02E04 720p HDTV"]),
        ("RetroGame (USA) (Rev 1) [!].zip", "RetroGame"),
        ("SingleWordTitle", "SingleWordTitle"),
    ]
    for raw, expected in cases:
        cands = theater.get_search_candidates(raw)
        if isinstance(expected, list):
            assert any(exp in cands for exp in expected), f"Failed candidate for '{raw}': got {cands}"
        else:
            assert any(expected.lower() in c.lower() for c in cands), f"Failed candidate for '{raw}': got {cands}"
    print("  ✓ [TitleCleaning] test_edge_case_media_candidate_sanitization PASSED (all edge cases resolved)")


def test_database_maintenance_trigger():
    setup_healthy_environment()
    health_check.trigger_database_maintenance()
    assert spy.was_called("service", "call") or spy.was_called("recorder", "purge")
    print("  ✓ [Maintenance] test_database_maintenance_trigger PASSED (recorder repack initiated)")


if __name__ == "__main__":
    print("\n==================================================")
    print("RUNNING PREFLIGHT HEALTH & RESILIENCE AUDIT SUITE")
    print("==================================================")
    test_preflight_diagnostics_all_healthy()
    test_preflight_diagnostics_degraded_on_unavailable()
    test_preflight_diagnostics_error_on_missing()
    test_theater_force_reconcile_when_active()
    test_theater_force_reconcile_when_off()
    test_edge_case_media_candidate_sanitization()
    test_database_maintenance_trigger()
    print("==================================================")
    print("ALL 7 PREFLIGHT & RECONCILIATION TESTS PASSED")
    print("==================================================\n")
