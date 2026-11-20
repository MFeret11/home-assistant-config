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
# Screen: while any WAKE_WINDOWS sensor is on (mornings: 6-9 AM on weekdays,
# 8-11 AM on weekends; evenings: 4-8 PM every
# day, or earlier once the commuter leaves work and the train-home card
# shows), the screen is turned on and held on through the Companion app. When
# they all end, keep-screen-on is cleared and Android's normal screen timeout
# turns the screen off, so it is dark for the rest of the day and overnight.
# It is also released while both of us are away (binary_sensor.anyone_home),
# and held again if one of us gets home while a window is still open.

PLUG = "switch.kitchen_tablet_mains"
PLUG_COUNTDOWN = "number.kitchen_tablet_mains_countdown_to_turn_off"
BATTERY = "sensor.big_tablet_battery_level"

CHARGE_ON_PCT = 30
CHARGE_OFF_PCT = 80
LOW_ALERT_PCT = 15
TABLET_NOTIFY = "mobile_app_big_tablet"
WAKE_WINDOWS = [
    "binary_sensor.kitchen_morning_wake",
    "binary_sensor.kitchen_evening_wake",
    # The train-home card: on from when the commuter leaves work, even before 4 PM.
    "binary_sensor.kitchen_show_pm_commute",
]
# The screen is held only while a window is open and someone is home.
ANYONE_HOME = "binary_sensor.anyone_home"
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
    # A window entity that doesn't exist (yet) counts as closed.
    for e in WAKE_WINDOWS:
        if state.exist(e) and state.get(e) == "on":
            return True
    return False


def _want_screen():
    # Unknown or unavailable counts as home, so only a confirmed "off" darkens it.
    return _in_wake_window() and state.get(ANYONE_HOME) != "off"


_screen_held = None  # last command sent: True = held on, False = released


def _sync_screen():
    global _screen_held
    want = _want_screen()
    # Send only when the answer changes. At 8 AM one window ends as the next
    # begins; a second keep-on command then turned the screen off (2026-11-06).
    if want == _screen_held:
        return
    if want or _screen_held:
        _screen_command(want)
    _screen_held = want


@state_trigger(WAKE_WINDOWS + [ANYONE_HOME])
def kitchen_tablet_screen_inputs_changed():
    # Debounce: let window handovers and GPS blips settle before deciding.
    task.unique("kitchen_tablet_screen_sync")
    task.sleep(5)
    _sync_screen()


@time_trigger("startup")
def kitchen_tablet_startup():
    _apply_charge_window()
    _sync_screen()
    if state.get(PLUG) == "on":
        kitchen_tablet_arm_backstop()
