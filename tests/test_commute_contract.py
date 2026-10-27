"""
Transit & Commute Telemetry Contract & Template Test
Validates the data contract between the transit service (:8000),
packages/commute.yaml, and the commute cards in dashboards/kitchen.yaml.

The kitchen cards are rendered with Jinja2 against fake sensor states, so a
template change that breaks a scenario (or reads an attribute the package
never imports) fails here instead of on the kitchen screen. The card colours
come from the Commute AM/PM Severity template sensors in the package, which
are rendered first from the same fake states.

Run: python3 ~/ha_config/tests/test_commute_contract.py
"""
import os
import re

import jinja2
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PACKAGE = os.path.join(ROOT, "packages", "commute.yaml")
KITCHEN = os.path.join(ROOT, "dashboards", "kitchen.yaml")

# Fields of the service's commute payload that the kitchen cards rely on.
EXPECTED_COMMUTE_ATTRIBUTES = {
    "trip_type", "origin_train", "origin_line", "origin_departure_time",
    "origin_actual_departure_time", "origin_track", "origin_delay_minutes",
    "origin_delay_text", "origin_delay_unknown", "origin_current_stop",
    "is_cancelled", "is_stalled", "stall_minutes", "walk_time_minutes",
    "leave_by_time", "minutes_until_leave_by", "leave_now", "already_departed",
    "at_risk", "delayed", "connection_station", "connection_train",
    "connection_line", "connection_departure_time", "connection_actual_departure_time",
    "connection_track", "connection_delay_minutes", "connection_delay_text",
    "connection_delay_unknown", "connection_current_stop", "connection_is_stalled",
    "connection_stall_minutes", "connection_cancelled", "transfer_buffer_minutes",
    "arrival_time", "planned_arrival_time", "actual_arrival_time", "total_delay_minutes",
    "missed_connection", "planned_connection_cancelled", "planned_connection_train",
    "backup_train_departure", "data_stale", "service_alerts", "alerts_unavailable",
}

EXPECTED_WEATHER_ATTRIBUTES = {
    "high_f", "low_f", "morning_temp_f", "evening_temp_f",
    "condition", "needs_umbrella", "current_temp_f", "precip_chance",
    "commute_warnings", "weather_stale", "morning_warning", "evening_warning",
}


def _declared_attributes(sensor_name: str) -> set:
    with open(PACKAGE, encoding="utf-8") as f:
        package = yaml.safe_load(f)
    for resource in package["rest"]:
        for sensor in resource.get("sensor", []):
            if sensor["name"] == sensor_name:
                return set(sensor.get("json_attributes", []))
    raise AssertionError(f"{sensor_name} not found in packages/commute.yaml")


def _severity_templates() -> dict:
    """{'am': template, 'pm': template} for the Commute AM/PM Severity sensors."""
    with open(PACKAGE, encoding="utf-8") as f:
        package = yaml.safe_load(f)
    found = {}
    for block in package["template"]:
        for sensor in block.get("sensor", []):
            if sensor["name"] == "Commute AM Severity":
                found["am"] = sensor["state"]
            elif sensor["name"] == "Commute PM Severity":
                found["pm"] = sensor["state"]
    assert set(found) == {"am", "pm"}, f"severity sensors not found in commute.yaml: {set(found)}"
    return found


def _kitchen_cards() -> dict:
    """{'am': card, 'pm': card} for the conditional commute markdown cards."""
    with open(KITCHEN, encoding="utf-8") as f:
        dashboard = yaml.safe_load(f)
    cards = {}

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "conditional":
                entities = {c.get("entity") for c in node.get("conditions", [])
                            if c.get("state") == "on"}
                card = node.get("card", {})
                if "binary_sensor.septa_am_window" in entities:
                    cards["am"] = card
                elif "binary_sensor.septa_pm_window" in entities:
                    cards["pm"] = card
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(dashboard)
    assert set(cards) == {"am", "pm"}, f"commute cards not found in kitchen.yaml: {set(cards)}"
    return cards


class _Entity:
    def __init__(self, state, attributes):
        self.state = state
        self.attributes = attributes


class _Domain:
    def __init__(self, entities, domain):
        self._entities, self._domain = entities, domain

    def __getattr__(self, name):
        return self._entities.get(f"{self._domain}.{name}")


class _States:
    """Mimics HA's `states`: callable for a state string, attribute access
    (states.sensor.x) for the state object, None when the entity is missing."""
    def __init__(self, entities):
        self._entities = entities

    def __call__(self, entity_id):
        entity = self._entities.get(entity_id)
        return entity.state if entity else "unknown"

    def __getattr__(self, domain):
        return _Domain(self._entities, domain)


def _render(template: str, commute_state: str, commute: dict, weather: dict | None = None) -> str:
    entities = {
        "sensor.septa_commute": _Entity(commute_state, commute),
        "sensor.commute_weather": _Entity("Light jacket / sweater", {
            "current_temp_f": 52, "morning_temp_f": 48, "evening_temp_f": 60,
            "high_f": 61, "low_f": 47, **(weather or {}),
        }),
    }
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    for window, severity in _severity_templates().items():
        level = env.from_string(severity).render(states=_States(entities)).strip()
        entities[f"sensor.commute_{window}_severity"] = _Entity(level, {})
    return env.from_string(template).render(states=_States(entities))


def _severity(window: str, commute_state: str, commute: dict) -> str:
    return _render("{{ states('sensor.commute_%s_severity') }}" % window, commute_state, commute)


def _attribute_lookups(text: str, var: str = "c") -> set:
    return set(re.findall(var + r"\.get\(['\"]([\w_]+)['\"]", text))


# Placeholder trains and stations; keep real stations out of this public repo.
BASE = {
    "trip_type": "transfer", "origin_train": "1001", "origin_line": "Line A",
    "origin_actual_departure_time": "5:10PM", "origin_track": "3",
    "leave_by_time": "5:00PM", "leave_now": False, "is_cancelled": False,
    "is_stalled": False, "stall_minutes": 0, "origin_delay_unknown": False,
    "origin_delay_text": "On time", "connection_station": "Center Station",
    "connection_train": "2002", "connection_line": "Line B",
    "connection_actual_departure_time": "5:40PM", "connection_track": "TBD",
    "connection_cancelled": False, "connection_is_stalled": False,
    "connection_stall_minutes": 0, "connection_delay_unknown": False,
    "connection_delay_text": "On time", "at_risk": False, "delayed": False,
    "missed_connection": False, "planned_connection_cancelled": False,
    "planned_connection_train": None, "total_delay_minutes": 0,
    "actual_arrival_time": "6:15PM", "planned_arrival_time": "6:15PM",
    "backup_train_departure": "5:40PM", "data_stale": False,
    "service_alerts": [], "alerts_unavailable": False,
}

# (name, sensor state, attribute overrides, text expected on AM card, on PM card)
SCENARIOS = [
    ("On time", "ok", {}, "Leave by", "On Time"),
    ("Service down", "unavailable", None, "Train times unavailable", "Train times unavailable"),
    ("SEPTA error", "error", {"error": "SEPTA trip data unavailable"},
     "Train times unavailable", "Train times unavailable"),
    ("Leave now", "ok", {"leave_now": True}, "LEAVE NOW", "On Time"),
    ("Cancelled", "cancelled", {"is_cancelled": True},
     "next train **5:40PM**", "next train **5:40PM**"),
    ("Connection cancelled (fallback)", "cancelled", {"connection_cancelled": True},
     "Train 2002 at Center Station is cancelled", "Train 2002 at Center Station is cancelled"),
    ("Planned connection cancelled", "cancelled",
     {"planned_connection_cancelled": True, "planned_connection_train": "2000",
      "total_delay_minutes": 30, "delayed": True},
     "Usual connection (train 2000) cancelled", "Usual train 2000 is cancelled"),
    ("Origin stalled", "stalled", {"is_stalled": True, "stall_minutes": 12,
                                   "origin_current_stop": "North Junction"},
     "stopped at North Junction", "stopped at North Junction"),
    ("Connection stalled", "stalled", {"connection_is_stalled": True, "connection_stall_minutes": 11,
                                       "connection_current_stop": "South Yard"},
     "Train 2002 stopped at South Yard", "Train 2002 stopped at South Yard"),
    ("Unclear delay text", "delayed", {"origin_delay_unknown": True, "origin_delay_text": "Delayed",
                                       "delayed": True},
     'SEPTA says "Delayed"', 'SEPTA says "Delayed"'),
    ("Missed connection", "missed_connection",
     {"missed_connection": True, "total_delay_minutes": 30, "actual_arrival_time": "6:45PM"},
     "Misses the planned connection", "MISSED CONNECTION"),
    ("Tight connection", "at_risk", {"at_risk": True}, "Tight connection", "Tight connection"),
    ("Delayed 10 min", "delayed", {"total_delay_minutes": 10, "delayed": True},
     "10 min late", "Delayed 10 min"),
    ("Minor delay", "ok", {"total_delay_minutes": 4}, "4 min late", "Delayed 4 min"),
    ("Stale data", "ok", {"data_stale": True}, "few minutes ago", "few minutes ago"),
    ("Line alert", "alert", {"service_alerts": ["Line A: Suspended near Center Station"]},
     "🚨 **Line A: Suspended near Center Station**", "🚨 **Line A: Suspended near Center Station**"),
    ("Line alert never reads as on time", "alert", {"service_alerts": ["Line A: Suspended"]},
     "check the alert above", "# 🚨 Service alert"),
    ("Line alert while SEPTA is down", "error",
     {"error": "SEPTA trip data unavailable", "service_alerts": ["Line A: Suspended"]},
     "🚨 **Line A: Suspended**", "🚨 **Line A: Suspended**"),
    ("Next train shown", "ok", {"backup_train_departure": "5:55PM"},
     "Next train after this one: 5:55PM", "On Time"),
    ("Direct trip", "ok", {"trip_type": "direct", "connection_station": None,
                           "connection_train": None, "connection_line": None},
     "On time", "On Time"),
]


def test_commute_package_contract():
    print("  [1/3] Validating packages/commute.yaml attribute schema...")
    missing = EXPECTED_COMMUTE_ATTRIBUTES - _declared_attributes("SEPTA Commute")
    assert not missing, f"Missing commute attributes in package: {sorted(missing)}"
    missing = EXPECTED_WEATHER_ATTRIBUTES - _declared_attributes("Commute Weather")
    assert not missing, f"Missing weather attributes in package: {sorted(missing)}"
    print(f"    ✓ All {len(EXPECTED_COMMUTE_ATTRIBUTES)} commute attributes declared")


def test_kitchen_reads_only_imported_attributes():
    print("  [2/3] Auditing kitchen dashboard attribute lookups...")
    with open(KITCHEN, encoding="utf-8") as f:
        lookups = _attribute_lookups(f.read())
    for template in _severity_templates().values():
        lookups |= _attribute_lookups(template)
    undeclared = lookups - _declared_attributes("SEPTA Commute")
    assert not undeclared, (
        f"kitchen.yaml reads attributes HA never imports (always empty): {sorted(undeclared)}"
    )
    with open(KITCHEN, encoding="utf-8") as f:
        weather_lookups = _attribute_lookups(f.read(), var="w")
    undeclared = weather_lookups - _declared_attributes("Commute Weather")
    assert not undeclared, f"kitchen.yaml reads weather attributes HA never imports: {sorted(undeclared)}"
    print(f"    ✓ {len(lookups)} commute attribute lookups are all imported by the REST sensor")


def test_commute_card_rendering_matrix():
    print("  [3/3] Rendering kitchen commute cards for each scenario...")
    cards = _kitchen_cards()
    for name, state, overrides, am_expect, pm_expect in SCENARIOS:
        commute = {} if overrides is None else (
            overrides if "error" in overrides else {**BASE, **overrides})
        for window, expect in (("am", am_expect), ("pm", pm_expect)):
            card = cards[window]
            text = _render(card["content"], state, commute)
            assert expect in text, f"{name} / {window}: expected {expect!r} in:\n{text}"
            assert "None" not in text, f"{name} / {window}: 'None' leaked into:\n{text}"
            _render(card["card_mod"]["style"], state, commute)
        print(f"    ✓ {name}")

    weather = {"morning_warning": "Heavy rain around 7AM", "evening_warning": "Rain likely (60%)"}
    am = _render(cards["am"]["content"], "ok", BASE, weather)
    pm = _render(cards["pm"]["content"], "ok", BASE, weather)
    assert "☔ Heavy rain around 7AM" in am, am
    assert "☔ Rain likely (60%) on the way home" in pm, pm
    dry = _render(cards["am"]["content"], "ok", BASE, {"morning_warning": None})
    assert "☔" not in dry and "None" not in dry, dry
    print("    ✓ Weather warnings")

    red = "rgba(244, 67, 54, 0.4)"
    alert = {**BASE, "service_alerts": ["Line A: Suspended"]}
    for window in ("am", "pm"):
        style = cards[window]["card_mod"]["style"]
        assert red in _render(style, "alert", alert), f"{window} card not red for a line alert"
        assert red not in _render(style, "ok", BASE), f"{window} card red with nothing wrong"
    print("    ✓ Card turns red for a line alert")

    # (scenario, expected AM level, expected PM level)
    levels = [
        ({}, "ok", "ok"),
        ({"total_delay_minutes": 4}, "warn", "warn"),
        ({"total_delay_minutes": 10}, "warn", "alert"),
        ({"leave_now": True}, "alert", "ok"),
        ({"at_risk": True}, "warn", "warn"),
        ({"is_cancelled": True}, "alert", "alert"),
        ({"service_alerts": ["Line A: Suspended"]}, "alert", "alert"),
    ]
    for overrides, am_level, pm_level in levels:
        commute = {**BASE, **overrides}
        assert _severity("am", "ok", commute) == am_level, (overrides, "am")
        assert _severity("pm", "ok", commute) == pm_level, (overrides, "pm")
    assert _severity("am", "unavailable", {}) == "warn"
    assert _severity("pm", "unavailable", {}) == "warn"
    print("    ✓ Severity sensors pick ok / warn / alert")


if __name__ == "__main__":
    print("\n==================================================")
    print("TRANSIT & COMMUTE CONTRACT VERIFICATION")
    print("==================================================")
    test_commute_package_contract()
    test_kitchen_reads_only_imported_attributes()
    test_commute_card_rendering_matrix()
    print("==================================================")
    print("✓ ALL COMMUTE CONTRACT CHECKS PASSED CLEANLY\n")
