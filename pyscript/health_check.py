# /config/pyscript/health_check.py
"""
Basement & Theater Enterprise Preflight Diagnostic Engine.
Runs continuous integrity checks across Zigbee mesh, AV entities, and database health.
"""
import time

CRITICAL_ENTITIES = [
    ("media_player.theater_receiver", "Yamaha RX-V673 AVR"),
    ("switch.projector", "Optoma Projector Relay"),
    ("sensor.projector_current_rounded", "Projector Current Sensor"),
    ("sensor.projector_power_state", "Projector Discrete State Machine"),
    ("binary_sensor.theater_in_use", "Theater In-Use Resolver"),
    ("light.theater_dimmer", "Theater Overhead Dimmer"),
    ("light.zigbee_basement_lights", "Zigbee 9-Bulb Master Group"),
    ("light.stairlights", "Stairway Illuminators"),
    ("binary_sensor.bottom_stairs", "Foot of Stairs Motion"),
    ("binary_sensor.basement_stairs_door_sensor", "Stair Door Contact Sensor"),
    # basement.py reads an unavailable presence sensor as "nobody there", so a
    # dead one silently weakens the vacancy and walk-out rules.
    ("binary_sensor.theater_mmwave_sensor", "Theater mmWave Presence"),
    # Bar mmWave left out while it is unplugged (since 2026-11-16); add it back
    # when it is plugged in again.
    # ("binary_sensor.mmwave_sensor_bar", "Bar mmWave Presence"),
    ("input_select.basement_theater_mode", "Theater Mode Selector"),
    ("input_select.basement_lighting_mode", "Lighting Mode Selector"),
]


@service
def run_preflight_diagnostics():
    """Runs end-to-end verification of all critical entities and returns a health scorecard."""
    missing_entities = []
    unavailable_entities = []
    healthy_entities = []

    for entity_id, name in CRITICAL_ENTITIES:
        try:
            val = state.get(entity_id)
            if val is None:
                missing_entities.append(f"{name} ({entity_id})")
            elif str(val).lower() in ["unavailable", "unknown"]:
                unavailable_entities.append(f"{name} ({entity_id})")
            else:
                healthy_entities.append(entity_id)
        except Exception:
            missing_entities.append(f"{name} ({entity_id})")

    # Evaluate overall status
    if missing_entities:
        health_status = "error"
    elif unavailable_entities:
        health_status = "degraded"
    else:
        health_status = "healthy"

    diagnostic_summary = {
        "status": health_status,
        "total_monitored": len(CRITICAL_ENTITIES),
        "healthy_count": len(healthy_entities),
        "unavailable_count": len(unavailable_entities),
        "missing_count": len(missing_entities),
        "unavailable_items": unavailable_entities,
        "missing_items": missing_entities,
        "timestamp": int(time.time()),
    }

    try:
        state.set(
            "sensor.basement_automation_health",
            value=health_status,
            new_attributes={
                "friendly_name": "Basement Automation Health",
                "icon": "mdi:check-decagram" if health_status == "healthy" else "mdi:alert-decagram",
                "healthy_count": len(healthy_entities),
                "total_count": len(CRITICAL_ENTITIES),
                "unavailable": unavailable_entities,
                "missing": missing_entities,
                "last_run": int(time.time()),
            },
        )
    except Exception as e:
        try:
            log.warning(f"[HealthCheck] Could not set state for sensor.basement_automation_health: {e}")
        except Exception:
            pass

    try:
        log.info(f"=== [Preflight Health Audit] Status: {health_status.upper()} ({len(healthy_entities)}/{len(CRITICAL_ENTITIES)} healthy) ===")
    except Exception:
        pass
    return diagnostic_summary


# Problems seen on the previous hourly run, and the ones already pushed.
_problems_last_run = set()
_problems_alerted = set()


def alert_on_persistent_problems(summary):
    """Pushes one ntfy alert per entity that is down on two hourly runs in a row.

    Two runs, so a Zigbee blip or a restart doesn't page anyone. An entity that
    recovers and drops again alerts again; a reload forgets what was pushed, so
    a still-dead entity is repeated once after a restart.
    """
    global _problems_last_run, _problems_alerted
    problems = set(summary["unavailable_items"]) | set(summary["missing_items"])
    new = (problems & _problems_last_run) - _problems_alerted
    _problems_alerted = (_problems_alerted & problems) | new
    _problems_last_run = problems
    if not new:
        return
    try:
        notify.ntfy(
            title="Basement health: device offline",
            message="Unavailable for over an hour: " + "; ".join(sorted(new)),
        )
    except Exception:
        pass


@time_trigger("startup")
def startup_health_audit():
    run_preflight_diagnostics()


@time_trigger("cron(0 * * * *)")
def scheduled_health_audit():
    alert_on_persistent_problems(run_preflight_diagnostics())


@service
def trigger_database_maintenance():
    """Triggers an online database repack and purge to defragment SQLite pages on the Crucial BX500 SSD."""
    try:
        recorder.purge(keep_days=7, repack=True, apply_filter=False)
        log.info("[HealthCheck] Triggered recorder.purge with repack=True on home-assistant_v2.db")
    except Exception as e:
        try:
            log.warning(f"[HealthCheck] Failed to trigger recorder repack: {e}")
        except Exception:
            pass


@service
def test_pyscript():
    """Test service to verify Pyscript execution."""
    try:
        log.info("=== Pyscript engine is online and operational ===")
    except Exception:
        pass
