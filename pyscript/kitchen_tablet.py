# /config/pyscript/kitchen_tablet.py
#
# Battery-health charging for the wall-mounted kitchen tablet. The tablet has
# no built-in charge limit, so its charger sits on a smart plug and we keep
# the battery between CHARGE_ON_PCT and CHARGE_OFF_PCT instead of holding it
# at 100% around the clock (that's what swells tablet batteries).
#
# Safety layers:
# 1. HA charge window: plug on at <= 30%, off at >= 80%.
# 2. On-device backstop: every time the plug turns on, its own countdown timer
#    is set to MAX_CHARGE_S, so the plug cuts power by itself even if HA, the
#    Pi, Wi-Fi or the tablet's battery reporting goes down mid-charge.
# 3. HA-side cap: if the plug is still on after MAX_CHARGE_S (countdown write
#    failed, or the plug ignored it), HA turns it off and sends a notification.
# 4. Alerts: battery <= LOW_ALERT_PCT (charging isn't working) or the battery
#    sensor unavailable for an hour.
#
# Morning wake: while any WAKE_WINDOWS sensor is on (the commute cards' own
# display windows on weekdays, 8-11 AM on weekends), the screen is turned on
# and held on through the Companion app. When they all end, keep-screen-on is
# cleared and Android's normal screen timeout takes over.

PLUG = "switch.kitchen_tablet_mains"
PLUG_COUNTDOWN = "number.kitchen_tablet_mains_countdown_to_turn_off"
BATTERY = "sensor.big_tablet_battery_level"

CHARGE_ON_PCT = 30
CHARGE_OFF_PCT = 80
LOW_ALERT_PCT = 15
TABLET_NOTIFY = "mobile_app_big_tablet"
WAKE_WINDOWS = [
    "binary_sensor.septa_am_window",
    "binary_sensor.drive_display_window",
    "binary_sensor.kitchen_weekend_wake",
]
WAKE_ON = " or ".join([f"{e} == 'on'" for e in WAKE_WINDOWS])
WAKE_OFF = " or ".join([f"{e} == 'off'" for e in WAKE_WINDOWS])
MAX_CHARGE_S = 4 * 3600  # 30->80% takes about 2 h; 4 h leaves room for heavy use while charging


def _battery_pct():
    try:
        return float(state.get(BATTERY))
    except Exception:
        return None


def _notify(title, message):
    try:
        notify.ntfy(title=title, message=message)
    except Exception:
        pass


def _apply_charge_window():
    pct = _battery_pct()
    if pct is None:
        return
    plug = state.get(PLUG)
    if pct <= CHARGE_ON_PCT and plug == "off":
        log.info(f"kitchen_tablet: battery {pct:.0f}%, starting charge")
        switch.turn_on(entity_id=PLUG)
    elif pct >= CHARGE_OFF_PCT and plug == "on":
        log.info(f"kitchen_tablet: battery {pct:.0f}%, stopping charge")
        switch.turn_off(entity_id=PLUG)


@state_trigger(BATTERY)
def kitchen_tablet_battery_changed(value=None, old_value=None):
    _apply_charge_window()
    try:
        new, old = float(value), float(old_value)
    except Exception:
        return
    if new <= LOW_ALERT_PCT < old:
        _notify(
            "🔋 Kitchen tablet battery low",
            f"Kitchen tablet is at {new:.0f}% and plug is {state.get(PLUG)}. Charging may not be working.",
        )


@state_trigger(f"{PLUG} == 'on'")
def kitchen_tablet_arm_backstop():
    """Arm the plug's own off-timer whenever it turns on, including manual or power-restore turn-ons."""
    task.sleep(2)  # let the Zigbee plug settle after switching
    try:
        number.set_value(entity_id=PLUG_COUNTDOWN, value=MAX_CHARGE_S)
    except Exception as e:
        log.warning(f"kitchen_tablet: could not set plug countdown: {e}")


@state_trigger(f"{PLUG} == 'on'", state_hold=MAX_CHARGE_S + 300)
def kitchen_tablet_charge_cap():
    """Backstop in case the on-device countdown didn't take."""
    switch.turn_off(entity_id=PLUG)
    _notify(
        "🔌 Kitchen tablet charge cap",
        f"Plug was on for over {MAX_CHARGE_S // 3600} h without reaching {CHARGE_OFF_PCT}% "
        f"(battery {state.get(BATTERY)}%). HA turned it off; the plug's own timer didn't.",
    )


@state_trigger(f"{BATTERY} == 'unavailable'", state_hold=3600)
def kitchen_tablet_sensor_lost():
    _notify(
        "🔋 Kitchen tablet not reporting",
        f"Battery sensor has been unavailable for an hour; plug is {state.get(PLUG)}. "
        "The plug's own timer still limits any charge to 4 h.",
    )


def _screen_command(keep_on):
    # Any command value other than keep_screen_on resets the app's keep-screen-on flag.
    try:
        service.call("notify", TABLET_NOTIFY, message="command_screen_on",
                     data={"command": "keep_screen_on" if keep_on else "default"})
    except Exception as e:
        log.warning(f"kitchen_tablet: screen command failed: {e}")


def _in_wake_window():
    for e in WAKE_WINDOWS:
        if state.get(e) == "on":
            return True
    return False


@state_trigger(WAKE_ON)
def kitchen_tablet_wake(var_name=None, value=None, old_value=None):
    # Send once, when the first window opens. At 8 AM one window ends as the
    # next begins; a second command then turned the screen off (2026-11-06).
    if value != "on" or old_value == "on":
        return
    if any([state.get(e) == "on" for e in WAKE_WINDOWS if e != var_name]):
        return
    _screen_command(True)


@state_trigger(WAKE_OFF)
def kitchen_tablet_release(var_name=None, old_value=None):
    if old_value == "on" and not _in_wake_window():
        _screen_command(False)


@time_trigger("startup")
def kitchen_tablet_startup():
    _apply_charge_window()
    if _in_wake_window():
        _screen_command(True)
    if state.get(PLUG) == "on":
        kitchen_tablet_arm_backstop()
