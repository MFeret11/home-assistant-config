"""Bedroom shortcuts for the Bedroom dashboard."""

BEDROOM_LAMPS = "light.zigbee_bedroom_lights"


@service
def bedroom_goodnight():
    """Fade the bedroom lamps off, and the basement lights too if nobody is using them.

    The basement is left alone while the theater is in use or Social Mode is on,
    since someone may still be down there.
    """
    light.turn_off(entity_id=BEDROOM_LAMPS, transition=3)

    basement_busy = (
        state.get("binary_sensor.theater_in_use") == "on"
        or state.get("input_select.basement_lighting_mode") == "Social Mode"
    )
    if state.get("binary_sensor.basement_lights_active") == "on" and not basement_busy:
        pyscript.basement_all_off()
