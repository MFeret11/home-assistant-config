# /config/pyscript/commute_location.py
#
# Sends the commuter's position to the transit service (:8000) during the
# weekday commute hours, and at any hour while they're on the way home
# (binary_sensor.partner_heading_home, packages/commute.yaml), so it can tell
# which train they are actually on and follow that train instead of the one
# nearest the usual time. Each post says whether they're heading home, so the
# service shows the next train they can still make once they've left work.
#
# The position comes from sensor.partner_location, a neutral copy of the
# location tracker defined in a private (gitignored) package. It goes only to
# the service on this machine, which keeps it in memory; nothing is logged.

LOCATION = "sensor.partner_location"
HEADING_HOME = "binary_sensor.partner_heading_home"  # left work, not home yet
ENDPOINT = "http://127.0.0.1:8000/api/location"


@pyscript_compile
def _post_json(url, body, timeout=5):
    """Blocking POST. Returns the HTTP status, or -1 on a network error."""
    import json
    import urllib.request
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except Exception:
        return -1


def _in_commute_hours():
    """Same hours as the transit service's own windows (5-9 AM, 2-7 PM, weekdays)."""
    from datetime import datetime
    now = datetime.now()
    return now.weekday() < 5 and (5 <= now.hour < 9 or 14 <= now.hour < 19)


def _send_location():
    attrs = state.getattr(LOCATION) or {}
    lat, lon = attrs.get("latitude"), attrs.get("longitude")
    try:
        body = {"latitude": float(lat), "longitude": float(lon), "zone": state.get(LOCATION),
                "heading_home": state.get(HEADING_HOME) == "on"}
    except (TypeError, ValueError):
        return  # tracker has no position right now
    try:
        body["accuracy"] = float(attrs.get("gps_accuracy"))
    except (TypeError, ValueError):
        pass
    if attrs.get("last_seen"):
        body["last_seen"] = str(attrs.get("last_seen"))
    status = task.executor(_post_json, ENDPOINT, body)
    if status != 200:
        log.warning(f"commute_location: transit service answered {status}")


@state_trigger(LOCATION, f"{LOCATION}.latitude", f"{LOCATION}.longitude", f"{LOCATION}.last_seen")
def commute_location_changed():
    # On the way home the service needs the position at any hour, not only in
    # the usual afternoon window.
    if _in_commute_hours() or state.get(HEADING_HOME) == "on":
        _send_location()


@state_trigger(HEADING_HOME)
def commute_heading_home_changed(value=None, old_value=None):
    """Tell the service at once when the commuter leaves work or gets home,
    rather than at the next position update."""
    if value in ("on", "off") and old_value in ("on", "off"):
        _send_location()


@time_trigger("cron(0 5,14 * * 1-5)")
def commute_location_window_opened():
    """Send the current position as each window opens, so the service isn't
    waiting for the next move."""
    _send_location()
