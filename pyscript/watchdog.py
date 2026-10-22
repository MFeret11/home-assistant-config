# /config/pyscript/watchdog.py

CPU_TEMP_WARN_C = 65.0
CPU_TEMP_CLEAR_C = 60.0  # hysteresis: re-arm the thermal alert only after cooling below this
DISK_WARN_PCT = 85.0
DISK_CRITICAL_PCT = 95.0
DISK_CLEAR_PCT = 80.0

# Alert latches so a sustained condition notifies once, not every 15-minute sweep.
_alert_latched = {"thermal": False, "storage": False}


def safe_float_get(entity_id: str, default=None):
    """Safely retrieves a float state value without throwing NameError if the entity is missing."""
    try:
        val = state.get(entity_id)
        if val is not None and str(val).lower() not in ["unavailable", "unknown", "none", ""]:
            return float(val)
    except Exception:
        pass
    return default


def get_cpu_temp():
    """Returns CPU temperature in °C, or None if no sensor is available.

    HA converts temperature sensors to the instance unit system, so on an
    imperial install System Monitor reports °F; convert back before comparing.
    """
    for eid in [
        "sensor.system_monitor_processor_temperature",
        "sensor.processor_temperature",
        "sensor.cpu_temperature",
    ]:
        val = safe_float_get(eid, None)
        if val is None:
            continue
        unit = None
        try:
            unit = state.getattr(eid).get("unit_of_measurement")
        except Exception:
            pass
        if unit == "°F":
            val = (val - 32.0) * 5.0 / 9.0
        return round(val, 1)
    return None


def get_disk_usage():
    """Returns SSD utilization percent, or None if no sensor is available."""
    for eid in [
        "sensor.system_monitor_disk_use_percent",
        "sensor.disk_use_percent",
        "sensor.disk_use_percent_config",
        "sensor.system_monitor_disk_usage",
    ]:
        val = safe_float_get(eid, None)
        if val is not None:
            return val
    return None


def pi4_thermal_alert():
    """Sends the Raspberry Pi 4 CPU thermal warning via ntfy."""
    curr_temp = get_cpu_temp()
    try:
        notify.ntfy(
            title="🔥 RPi 4 Thermal Warning (>65°C)",
            message=f"Raspberry Pi 4 CPU temperature reached {curr_temp}°C. Check active fan or cabinet airflow.",
        )
    except Exception:
        pass


def pi4_storage_alert():
    """Sends the USB SSD storage warning via ntfy (prevents SQLite DB write locks)."""
    disk_usage = get_disk_usage()
    try:
        notify.ntfy(
            title="💾 Crucial BX500 SSD Storage Warning (>85%)",
            message=f"Crucial BX500 SSD (CT240BX500SSD1) disk usage reached {disk_usage}%. Review recorder purge settings or remove old logs.",
        )
    except Exception:
        pass


@state_trigger("binary_sensor.transit_microservice == 'off'", state_hold=120)
def transit_service_down_alert():
    """Pushes an alert via ntfy.sh if the transit microservice is down for 2 minutes."""
    try:
        notify.ntfy(
            title="🚨 Transit Microservice Offline",
            message="FastAPI container on port 8000 has stopped responding. Commute tracking and morning kiosk alerts are paused.",
        )
    except Exception:
        pass


@state_trigger("float(sensor.projector_current) > 0.8 and binary_sensor.theater_in_use == 'off'", state_hold=300)
def unexpected_projector_power_draw_alert():
    """Alerts if Optoma projector is drawing active lamp power (>0.8A) while the theater is unmanaged/off."""
    try:
        notify.ntfy(
            title="⚠️ Unattended Projector Power Draw",
            message="Optoma projector is drawing active lamp power (~2.5A) while Theater In-Use is OFF. Verify status.",
        )
    except Exception:
        pass


@service
def run_system_health_audit():
    """Performs an end-to-end synthetic health check across infrastructure, AVR, tuner, and storage."""
    import time
    curr_temp = get_cpu_temp()
    disk_usage = get_disk_usage()

    transit_state = None
    try:
        transit_state = state.get("binary_sensor.transit_microservice")
    except Exception:
        pass
    transit_ok = transit_state != "off"

    health_status = "nominal"
    warnings = []

    if curr_temp is None:
        warnings.append("CPU temperature sensor unavailable")
    elif curr_temp > CPU_TEMP_WARN_C:
        health_status = "warning"
        warnings.append(f"High CPU temp: {curr_temp}°C")
        if not _alert_latched["thermal"]:
            _alert_latched["thermal"] = True
            pi4_thermal_alert()
    elif curr_temp < CPU_TEMP_CLEAR_C:
        _alert_latched["thermal"] = False

    if disk_usage is None:
        warnings.append("Disk usage sensor unavailable")
    elif disk_usage > DISK_WARN_PCT:
        health_status = "critical" if disk_usage > DISK_CRITICAL_PCT else "warning"
        warnings.append(f"High SSD usage: {disk_usage}%")
        if not _alert_latched["storage"]:
            _alert_latched["storage"] = True
            pi4_storage_alert()
    elif disk_usage < DISK_CLEAR_PCT:
        _alert_latched["storage"] = False

    if not transit_ok:
        warnings.append("Transit microservice unreachable")

    try:
        state.set(
            "sensor.watchdog_system_health",
            value=health_status,
            new_attributes={
                "friendly_name": "Watchdog System Health",
                "icon": "mdi:shield-check" if health_status == "nominal" else "mdi:alert-circle",
                "cpu_temp": curr_temp,
                "cpu_temp_unit": "°C",
                "disk_use_percent": disk_usage,
                "transit_ok": transit_ok,
                "ssd_model": "Crucial BX500 240GB (CT240BX500SSD1)",
                "warnings": warnings,
                "last_audit_ts": int(time.time()),
            },
        )
    except Exception:
        pass

    return {
        "status": health_status,
        "warnings": warnings,
        "cpu_temp": curr_temp,
        "disk_use_percent": disk_usage,
    }


@time_trigger("startup")
@time_trigger("cron(*/15 * * * *)")
def scheduled_watchdog_health_sweep():
    """Executes synthetic health sweep every 15 minutes."""
    run_system_health_audit()
