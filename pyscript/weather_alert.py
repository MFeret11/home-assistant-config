# /config/pyscript/weather_alert.py
#
# Dismiss button for the Weather Service alert banner
# (dashboards/components/shared/weather_alert.yaml, on Home and the kitchen
# tablet). Tapping the banner calls pyscript.weather_alert_dismiss, which saves
# the current alert's key as DISMISSED. The banner shows only while
# binary_sensor.weather_alert_showing (packages/kitchen_display.yaml) is on,
# and that turns off when its key matches the saved one. A new or changed
# alert has a different key, so it shows again.

SHOWING = "binary_sensor.weather_alert_showing"
DISMISSED = "pyscript.weather_alert_dismissed"  # kept across HA restarts

state.persist(DISMISSED, default_value="")


@service
def weather_alert_dismiss():
    """Hide the current weather alert banner until the alert changes."""
    key = state.getattr(SHOWING).get("key")
    if key:
        state.set(DISMISSED, key)
