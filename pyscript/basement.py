# ==============================================================================
# BASEMENT LIGHTING: modes, stairs, vacancy, theater lighting, palettes
# ==============================================================================
# Sections, in order (search for the capitalised heading):
#   ENTITY IDS AND SETTINGS
#   SMALL HELPERS, AND HELPER ENTITIES CREATED AT LOAD
#   LIGHTING MODE (Daily Driver or Social Mode)
#   PALETTES AND THE DRIFT EFFECT, AND THE 4 AM RESET
#   STAIRS: DOOR, MOTION AND WALK-OUT DETECTION
#   VACANCY: LIGHTS OFF WHEN NOBODY IS DOWNSTAIRS
#   THEATER LIGHTING (Daily Driver) AND CURTAIN CALL
#   ALL-OFF, THE LIGHTS-ON CHIP, AND THE POWER-CUT SWEEP
#   PALETTE AND PARTY SERVICES (dashboard buttons)
#   DASHBOARD MODE DRAWER
#   DASHBOARD DRAWERS AND THEATER MEDIA BUTTONS
#
# Daily Driver is the normal mode: automations run the lights. Social Mode is for
# guests and game day: no timeouts or automatic shutoffs (game-day stairs aside).
# Timings and the reasons for them: docs/lighting.md.
# ==============================================================================
import time

BOOT_TIMESTAMP = time.time()

# ------------------------------------------------------------------------------
# ENTITY IDS AND SETTINGS
# ------------------------------------------------------------------------------
from pc_window import parse_pc_active_window  # pyscript/modules/pc_window.py: is the PC in a game?
from shared_entities import (  # pyscript/modules/shared_entities.py
    ADAPTIVE_SWITCH,
    RECEIVER,
    RECEIVER_ZONE_2,
    MMWAVE_PRESENCE,
    LIGHTING_MODE_SELECT,
    SOCIAL_SOURCE,
    CURTAIN_CALL,
    THEATER_IN_USE,
    THEATER_MODE,
    BATOCERA_STATE,
    ONN_ADB,
    ONN_PRO,
    ONN_REMOTE,
    PC_ACTIVE_WINDOW,
    THEATER_BOXART,
    SPOTIFY_PLAYER,
    MODE_DAILY,
    MODE_SOCIAL,
    FEATURED_TEAM,
)

THEATER_DIMMER = "light.theater_dimmer"
BIAS_LIGHTS = "switch.bias_lights"
STAIRLIGHTS = "light.stairlights"
MASTER_ZIGBEE_GROUP = "light.zigbee_basement_lights"
BEDROOM_ZIGBEE_GROUP = "light.zigbee_bedroom_lights"
BEDROOM_LAMP_1 = "light.bedroom_lamp_1"
BEDROOM_LAMP_2 = "light.bedroom_light_2"

DOOR_SENSOR = "binary_sensor.basement_stairs_door_sensor"
BOTTOM_STAIRS_MOTION = "binary_sensor.bottom_stairs"
# Second mmWave (SNZB-06P) at the bar, so someone sitting there counts too.
MMWAVE_BAR = "binary_sensor.mmwave_sensor_bar"
LIGHTS_ACTIVE_SENSOR = "binary_sensor.basement_lights_active"

DRAWER_SELECT = "input_select.basement_drawer"
MODE_EXPANDED = "pyscript.mode_selector_expanded"


SENSOR_PALETTE = "sensor.basement_palette"
SENSOR_EFFECT = "sensor.basement_effect"

VALID_MODES = {MODE_DAILY, MODE_SOCIAL}
DRIFT_EFFECTS = {"wave", "breathe", "cycle", "drift"}

ROOM_ZONES = [
    "light.zigbee_bar_lights",       # 1. North (Bar)
    "light.zigbee_lounge_lights_1",  # 2. Central Hub (Lounge Front / Stair Landing)
    "light.zigbee_lounge_lights_2",  # 3. Theater Flank (Lounge Mid)
    "light.zigbee_lounge_lights_3",  # 4. South (Lounge Rear)
]

PALETTES = {
    "speakeasy": [
        {"color_temp_kelvin": 2000, "brightness_pct": 25},
        {"color_temp_kelvin": 2200, "brightness_pct": 15},
        {"color_temp_kelvin": 2400, "brightness_pct": 10},
        {"color_temp_kelvin": 2300, "brightness_pct": 25},
        {"stair_k": 2200},
    ],
    "lofi": [
        {"hs_color": [28, 85], "brightness_pct": 55},
        {"hs_color": [340, 65], "brightness_pct": 45},
        {"hs_color": [280, 50], "brightness_pct": 30},
        {"hs_color": [15, 75], "brightness_pct": 25},
        {"stair_hs": [340, 65]},
    ],
    "synthwave": [
        {"hs_color": [35, 95], "brightness_pct": 70},
        {"hs_color": [300, 95], "brightness_pct": 55},
        {"hs_color": [185, 95], "brightness_pct": 35},
        {"hs_color": [320, 95], "brightness_pct": 25},
        {"stair_hs": [300, 95]},
    ],
    "cyberpunk": [
        {"hs_color": [185, 95], "brightness_pct": 65},
        {"hs_color": [40, 95], "brightness_pct": 55},
        {"hs_color": [185, 95], "brightness_pct": 35},
        {"hs_color": [280, 90], "brightness_pct": 25},
        {"stair_hs": [320, 95]},
    ],
    "nordic": [
        {"hs_color": [195, 75], "brightness_pct": 50},
        {"hs_color": [215, 60], "brightness_pct": 40},
        {"hs_color": [235, 50], "brightness_pct": 30},
        {"hs_color": [205, 55], "brightness_pct": 25},
        {"stair_hs": [215, 60]},
    ],
    "blood_moon": [
        {"hs_color": [280, 80], "brightness_pct": 55},
        {"hs_color": [0, 100], "brightness_pct": 50},
        {"hs_color": [15, 95], "brightness_pct": 30},
        {"hs_color": [355, 95], "brightness_pct": 20},
        {"stair_hs": [0, 100]},
    ],
}

# Stair brightness when they show a palette color (hue/saturation, or white in Kelvin)
STAIR_ACCENT_HS_PCT = 40
STAIR_ACCENT_K_PCT = 35

# Runtime tracking state
CURRENT_PALETTE = "synthwave"
CURRENT_EFFECT = "static"
LAST_DOOR_OPEN_TS = 0.0
LAST_MOTION_BOTTOM_TS = 0.0
LAST_MOTION_CLEAR_TS = 0.0
# Any bottom-stairs activity, tracked in every mode (starts at boot so a restart never reads as "idle for hours").
LAST_MOTION_SEEN_TS = BOOT_TIMESTAMP
DIRECTION_OF_TRAVEL = "none"
# Bottom-stairs motion this recent before a door event means someone is walking up and out.
EXIT_WINDOW_S = 25
# After a walk-out door close, wait this long and cancel the shutoff if anyone is still downstairs.
# The bottom-stairs sensor clears within ~7-11s, so someone left near the stairs re-trips it in this window.
WALKOUT_CONFIRM_S = 20
# Door opened this recently, then bottom-stairs motion, then the close: that is a group
# coming down (the first person trips the sensor before the last one shuts the door).
ENTRY_FOLLOW_WINDOW_S = 180
# Paused / pre-show glow on the theater dimmer. The cans don't light below ~3%.
GLOW_PCT = 3
# 4 AM reset: turn a forgotten room off if the stairs have seen no motion for this long.
NIGHTLY_IDLE_OFF_S = 7200
# Daily Driver: lights off once the mmWave and the stairs have both been quiet this long.
MMWAVE_VACANCY_S = 900
# Game day stairs: off this long after the game paint, motion or a door open, once the stairs are quiet.
STAIR_SPORTS_HOLD_S = 300
BLACKOUT_IN_PROGRESS = False
# "on" once team green is painted for this sports session; after that, lights turned
# off by hand or a palette pick are left alone. An entity, not a global, so a pyscript
# reload mid-game doesn't forget and repaint.
SPORTS_PAINTED = "pyscript.basement_sports_painted"
# Eagles Kelly green: the manual chant, and the fallback before Team Lights publishes.
# The stair bulbs' green LED is bluer, so 125° is the closest match by eye (2026-11-01).
EAGLES_RGB = [0, 170, 35]
EAGLES_STAIR_HS = [125, 100]

# ------------------------------------------------------------------------------
# SMALL HELPERS, AND HELPER ENTITIES CREATED AT LOAD
# ------------------------------------------------------------------------------
def safe_state_get(entity_id: str, default=None):
    """Safely retrieves entity state without throwing PyScript errors."""
    try:
        val = state.get(entity_id)
        return val if val is not None else default
    except Exception:
        return default


def _team_colors():
    """(room RGB, stair color settings) for the featured team, published by the Team Lights
    app (pyscript/apps/team_lights.py). The stair bulbs are hue/saturation only, so a team
    can give them their own tuned color (`light_colors`); otherwise they get the RGB.
    Eagles green until the app has published."""
    if safe_state_get(FEATURED_TEAM) is None:
        return list(EAGLES_RGB), {"hs_color": list(EAGLES_STAIR_HS)}
    rgb = list(safe_state_getattr(FEATURED_TEAM, "rgb") or EAGLES_RGB)
    stair = (safe_state_getattr(FEATURED_TEAM, "light_colors") or {}).get(STAIRLIGHTS)
    return rgb, (dict(stair) if stair else {"rgb_color": rgb})


def _team_green_on(brightness_pct, transition, rgb=None, stair=None):
    """Team color on the main group, and on the stairs only if they're already lit:
    on game day the stairs are a motion path light. Group last."""
    if rgb is None:
        rgb, stair = _team_colors()
    if safe_state_get(STAIRLIGHTS) == "on":
        light.turn_on(entity_id=STAIRLIGHTS, brightness_pct=brightness_pct, transition=transition, **stair)
    light.turn_on(entity_id=MASTER_ZIGBEE_GROUP, rgb_color=rgb, brightness_pct=brightness_pct, transition=transition)


def safe_state_getattr(entity_id: str, attr: str, default=None):
    """Safely retrieves an entity attribute."""
    try:
        attrs = state.getattr(entity_id) or {}
        return attrs.get(attr, default)
    except Exception:
        return default


def safe_service(service_func, **kwargs):
    """Safely executes a service call without crashing on offline devices."""
    try:
        service_func(**kwargs)
    except Exception as e:
        name = getattr(service_func, "__name__", str(service_func))
        log.warning(f"[Basement] safe_service failed: {name} {kwargs}: {e}")


def ensure_entity(entity_id: str, default_val="off", attrs=None):
    """Ensures an entity exists with default values if not already present."""
    if safe_state_get(entity_id) is None:
        try:
            state.set(entity_id, value=default_val, new_attributes=attrs or {})
        except Exception:
            pass


def is_booting(grace_seconds=30) -> bool:
    """True for the first grace_seconds after this file loaded (HA start or a pyscript
    reload), so triggers firing on restored states are ignored."""
    return (time.time() - BOOT_TIMESTAMP) < grace_seconds


def _theater_active() -> bool:
    """True while a theater session is running (in-use flag, or an active theater mode)."""
    return safe_state_get(THEATER_IN_USE) == "on" or safe_state_get(THEATER_MODE) in ["movie", "game", "music", "sports"]


# Ensure tracking entities exist safely on startup
ensure_entity(CURTAIN_CALL, "off")
ensure_entity(LIGHTS_ACTIVE_SENSOR, "off")
ensure_entity(MODE_EXPANDED, "off")
# Created on first load only; a reload keeps it. Mid-game first load = already painted.
ensure_entity(SPORTS_PAINTED, "on" if safe_state_get(THEATER_MODE) == "sports" else "off")
try:
    if not safe_state_get(DRAWER_SELECT):
        state.set(DRAWER_SELECT, value="theater")
except Exception:
    pass


# ------------------------------------------------------------------------------
# LIGHTING MODE (Daily Driver or Social Mode)
# input_select.basement_lighting_mode holds the mode.
# ------------------------------------------------------------------------------
def is_presence_locked() -> bool:
    """Social Mode is the presence lock: no automated timeouts or shutoffs."""
    return get_lighting_mode() == MODE_SOCIAL


def get_lighting_mode() -> str:
    """input_select.basement_lighting_mode is the single source of truth."""
    mode = safe_state_get(LIGHTING_MODE_SELECT)
    if mode in VALID_MODES:
        return mode
    return MODE_DAILY


def set_lighting_mode(new_mode: str, source: str = "manual"):
    """Switch between Daily Driver and Social Mode. source ('manual' or 'sports')
    records who turned Social on; automation never downgrades a manual Social. Social
    also turns Adaptive Lighting off. 'Movie Mode' is an old name for Daily Driver."""
    if new_mode == "Movie Mode":
        new_mode = MODE_DAILY
    if new_mode not in VALID_MODES:
        return

    was_social = get_lighting_mode() == MODE_SOCIAL
    if new_mode == MODE_SOCIAL:
        # A user action always takes ownership; automation never downgrades a manual Social.
        if not was_social or source == "manual":
            state.set(SOCIAL_SOURCE, value=source)
    else:
        state.set(SOCIAL_SOURCE, value="none")

    try:
        input_select.select_option(entity_id=LIGHTING_MODE_SELECT, option=new_mode)
    except Exception:
        pass
    state.set(LIGHTING_MODE_SELECT, value=new_mode)

    if new_mode == MODE_SOCIAL:
        try:
            switch.turn_off(entity_id=ADAPTIVE_SWITCH)
        except Exception:
            pass


@state_trigger(LIGHTING_MODE_SELECT)
def on_lighting_mode_changed(value=None, old_value=None):
    """The lighting mode picker changed. Social: count it as manual if nothing else
    claimed it, Adaptive Lighting off. Daily Driver: stop any palette effect, then
    hand the lights to the theater (if in use) or back to normal."""
    if is_booting() or value == old_value or BLACKOUT_IN_PROGRESS:
        return

    if value == MODE_SOCIAL:
        # Picked straight from the select (not via set_lighting_mode): treat as manual
        if safe_state_get(SOCIAL_SOURCE) not in ("manual", "sports"):
            state.set(SOCIAL_SOURCE, value="manual")
        try:
            switch.turn_off(entity_id=ADAPTIVE_SWITCH)
        except Exception:
            pass
    elif value in (MODE_DAILY, "Movie Mode"):
        state.set(SOCIAL_SOURCE, value="none")
        task.unique("basement_ambient_loop")
        if safe_state_get(THEATER_IN_USE) == "on":
            theater_lighting_sync()
        else:
            mood_reset_normal()


# ------------------------------------------------------------------------------
# PALETTES AND THE DRIFT EFFECT, AND THE 4 AM RESET
# A palette has four room colors (ROOM_ZONES, in order) and a fifth entry for
# the stairs. "Drift" slowly rotates the four colors around the room.
# ------------------------------------------------------------------------------
def _stair_accent_on(stair_conf, transition):
    """Light the stairs in a palette's stair color (its fifth entry). False if it has none."""
    if "stair_hs" in stair_conf:
        light.turn_on(entity_id=STAIRLIGHTS, hs_color=stair_conf["stair_hs"], brightness_pct=STAIR_ACCENT_HS_PCT, transition=transition)
        return True
    if "stair_k" in stair_conf:
        light.turn_on(entity_id=STAIRLIGHTS, color_temp_kelvin=stair_conf["stair_k"], brightness_pct=STAIR_ACCENT_K_PCT, transition=transition)
        return True
    return False


def apply_static_palette(palette_name: str, transition: int = 2):
    """Applies a static palette cleanly across stairs and 4 room zones."""
    slots = PALETTES.get(palette_name, PALETTES["synthwave"])

    # 1. Stairs accent
    _stair_accent_on(slots[4], transition)

    task.sleep(0.2)

    # 2. Room zones
    for idx, zone in enumerate(ROOM_ZONES):
        params = dict(slots[idx])
        params["transition"] = transition
        light.turn_on(entity_id=zone, **params)
        task.sleep(0.25)


def _ambient_loop_runner():
    """Background runner for locked static scenes or smooth hardware drift."""
    task.unique("basement_ambient_loop")

    if CURRENT_EFFECT == "static":
        apply_static_palette(CURRENT_PALETTE, transition=2)
        return

    # EFFECT 2: Ambient Spatial Drift
    TRANSITION_TIME = 22
    HOLD_TIME = 6
    step = 0

    slots = PALETTES.get(CURRENT_PALETTE, PALETTES["synthwave"])
    _stair_accent_on(slots[4], 2)

    while get_lighting_mode() == MODE_SOCIAL and CURRENT_EFFECT in DRIFT_EFFECTS:
        active_slots = PALETTES.get(CURRENT_PALETTE, PALETTES["synthwave"])

        for idx, zone in enumerate(ROOM_ZONES):
            slot_data = dict(active_slots[(step + idx) % 4])
            if "hs_color" in slot_data:
                light.turn_on(
                    entity_id=zone,
                    hs_color=slot_data["hs_color"],
                    brightness_pct=slot_data["brightness_pct"],
                    transition=TRANSITION_TIME,
                )
            else:
                light.turn_on(
                    entity_id=zone,
                    color_temp_kelvin=slot_data["color_temp_kelvin"],
                    brightness_pct=slot_data["brightness_pct"],
                    transition=TRANSITION_TIME,
                )
            task.sleep(0.15)

        step += 1
        task.sleep(TRANSITION_TIME + HOLD_TIME)


def apply_ambient_lighting():
    """Social Mode with the current palette and effect, run in the background."""
    set_lighting_mode(MODE_SOCIAL)
    task.create(_ambient_loop_runner)


@time_trigger("cron(0 4 * * *)")
def safe_nightly_social_reset():
    """Nightly hygiene at 4 AM: clears social/guest modes without waking dormant lights."""
    task.unique("basement_ambient_loop")
    task.unique("stair_red_timer")
    task.unique("stair_timer")

    # Lights left on in a room nobody has walked through for 2+ hours (e.g. a forgotten
    # Social session): turn everything off instead of handing them to Daily Driver.
    forgotten = (
        safe_state_get(LIGHTS_ACTIVE_SENSOR) == "on"
        and safe_state_get(THEATER_IN_USE) != "on"
        # mmWave deliberately not checked: a stuck "occupied" must not keep lights on all night.
        and _seconds_since_bottom_stairs_activity() >= NIGHTLY_IDLE_OFF_S
    )

    set_lighting_mode(MODE_DAILY)
    state.set(CURTAIN_CALL, value="off")
    state.set(SENSOR_EFFECT, value="static")
    state.set(SENSOR_PALETTE, value="speakeasy")

    try:
        switch.turn_on(entity_id=ADAPTIVE_SWITCH)
    except Exception:
        pass

    if forgotten:
        log.info("[Basement] 4 AM: no stairs motion for 2h+, turning off forgotten lights")
        basement_all_off()
    elif safe_state_get(LIGHTS_ACTIVE_SENSOR) == "on":
        mood_reset_normal()


# ------------------------------------------------------------------------------
# STAIRS: DOOR, MOTION AND WALK-OUT DETECTION
# Direction of travel: bottom-stairs motion shortly before the door opens means
# someone is walking up and out; the door opening first means someone coming down.
# ------------------------------------------------------------------------------
def _trigger_stealth_red_stairs():
    """Fades stairs up to subtle 2% warm candlelight (2000K) for 60s during active theater sessions."""
    task.unique("stair_red_timer")
    light.turn_on(
        entity_id=STAIRLIGHTS,
        color_temp_kelvin=2000,
        brightness_pct=2,
        transition=2,
    )
    task.sleep(60)

    if safe_state_get(CURTAIN_CALL) != "on" and get_lighting_mode() != MODE_SOCIAL:
        light.turn_off(entity_id=STAIRLIGHTS, transition=3)


def _sports_stairs() -> bool:
    """Game day (Social Mode from sports, or the TV on sports): the stairs are a team-green
    path light that motion or the door turns on and quiet turns off. The one exception to
    Social Mode's no-timeouts rule; the room lights keep it."""
    return get_lighting_mode() == MODE_SOCIAL and (
        safe_state_get(THEATER_MODE) == "sports" or safe_state_get(SOCIAL_SOURCE) == "sports"
    )


def _sports_stair_path_light(hold_s=STAIR_SPORTS_HOLD_S):
    """Stairs on in team green, then off once the stairs have been quiet for hold_s.
    New motion or a door open restarts the timer."""
    task.unique("stair_sports_timer")
    _, stair = _team_colors()
    light.turn_on(entity_id=STAIRLIGHTS, brightness_pct=100, transition=1, **stair)
    task.sleep(hold_s)
    # Someone still standing at the foot of the stairs: wait for the sensor to clear.
    while safe_state_get(BOTTOM_STAIRS_MOTION) == "on":
        task.sleep(5)
    if _sports_stairs():
        light.turn_off(entity_id=STAIRLIGHTS, transition=3)


def _turn_on_circadian_direct(entity_id, transition=1):
    """Turns on lights directly at target circadian brightness and Kelvin, preventing bright flashes."""
    circ_pct = safe_state_getattr(ADAPTIVE_SWITCH, "brightness_pct")
    circ_k = safe_state_getattr(ADAPTIVE_SWITCH, "color_temp_kelvin")
    kwargs = {}
    if circ_pct is not None:
        try:
            kwargs["brightness_pct"] = int(circ_pct)
        except (ValueError, TypeError):
            pass
    if circ_k is not None:
        try:
            kwargs["color_temp_kelvin"] = int(circ_k)
        except (ValueError, TypeError):
            pass
    if "color_temp_kelvin" not in kwargs:
        kwargs["color_temp_kelvin"] = 2700
    if "brightness_pct" not in kwargs:
        kwargs["brightness_pct"] = 40
    if transition:
        kwargs["transition"] = transition

    light.turn_on(entity_id=entity_id, **kwargs)


@state_trigger(f"{DOOR_SENSOR} == 'on'")
def stair_door_opened(old_value=None):
    """The basement door opened. Notes the direction of travel, then lights the stairs
    to suit the mode: a dim warm glow during a theater session, circadian white for 3
    min in Daily Driver, a team-color path light on game day, or the palette's stair
    color in Social Mode."""
    global LAST_DOOR_OPEN_TS, DIRECTION_OF_TRAVEL
    if is_booting() or old_value != "off":
        return

    LAST_DOOR_OPEN_TS = time.time()
    time_since_bottom_motion = LAST_DOOR_OPEN_TS - LAST_MOTION_BOTTOM_TS
    DIRECTION_OF_TRAVEL = "up" if 0 < time_since_bottom_motion < EXIT_WINDOW_S else "down"

    mode = get_lighting_mode()
    theater_active = _theater_active()

    if theater_active and mode != MODE_SOCIAL:
        task.create(_trigger_stealth_red_stairs)
    elif mode == MODE_DAILY:
        _turn_on_circadian_direct(STAIRLIGHTS, transition=1)
        adaptive_lighting.apply(
            entity_id=ADAPTIVE_SWITCH,
            lights=[STAIRLIGHTS],
            turn_on_lights=True,
            adapt_brightness=True,
            adapt_color=True,
            transition=2,
        )
        task.unique("stair_peek_timer")
        task.sleep(180)
        if safe_state_get(BOTTOM_STAIRS_MOTION) == "off" and not is_presence_locked():
            light.turn_off(entity_id=STAIRLIGHTS, transition=3)
    elif _sports_stairs():
        # Game day: team-green path light, off 5 min after the stairs go quiet.
        _sports_stair_path_light(STAIR_SPORTS_HOLD_S)
    elif mode == MODE_SOCIAL:
        # In Social Mode: door opening turns on stair lights (if not already on) and leaves them on permanently
        current_pal = safe_state_get(SENSOR_PALETTE, CURRENT_PALETTE)
        lit = False
        if current_pal in PALETTES and current_pal != "normal":
            lit = _stair_accent_on(PALETTES[current_pal][4], 1)
        if not lit:
            _turn_on_circadian_direct(STAIRLIGHTS, transition=1)


@state_trigger(f"{BOTTOM_STAIRS_MOTION} == 'on'")
def motion_at_foot_of_stairs(old_value=None):
    """Motion at the foot of the stairs. Theater in use: dim warm stairs only. Daily
    Driver: if the stairs are lit (someone came down), the room lights come on and
    the stairs go off after 30 s; if not, the stairs come on for 45 s. Social Mode:
    nothing, except the game-day stairs."""
    global LAST_MOTION_BOTTOM_TS, LAST_MOTION_SEEN_TS
    LAST_MOTION_SEEN_TS = time.time()
    if is_booting() or old_value != "off":
        return
    # Game day: Social Mode's lock doesn't apply to the stairs; motion lights them.
    if _sports_stairs():
        LAST_MOTION_BOTTOM_TS = time.time()
        _sports_stair_path_light(STAIR_SPORTS_HOLD_S)
        return
    if is_presence_locked():
        return

    task.unique("stair_peek_timer")
    LAST_MOTION_BOTTOM_TS = time.time()
    mode = get_lighting_mode()
    theater_active = _theater_active()

    # 1. Theater in use (Daily Driver): dim warm stairs only. The room lights stay off.
    if theater_active:
        task.create(_trigger_stealth_red_stairs)
        return

    # 2. SOCIAL MODE: Leave stairs and room untouched
    if mode == MODE_SOCIAL:
        return

    # 3. DAILY DRIVER: Standard utility pathway directly at circadian level
    task.unique("stair_timer")
    stair_state = safe_state_get(STAIRLIGHTS)

    if stair_state == "on":
        _turn_on_circadian_direct(THEATER_DIMMER, transition=1)
        _turn_on_circadian_direct(MASTER_ZIGBEE_GROUP, transition=2)
        adaptive_lighting.apply(
            entity_id=ADAPTIVE_SWITCH,
            lights=[THEATER_DIMMER, MASTER_ZIGBEE_GROUP],
            turn_on_lights=True,
            adapt_brightness=True,
            adapt_color=True,
            transition=2,
        )
        task.sleep(30)
        if get_lighting_mode() == MODE_DAILY and not is_presence_locked():
            light.turn_off(entity_id=STAIRLIGHTS, transition=3)

    elif stair_state == "off":
        _turn_on_circadian_direct(STAIRLIGHTS, transition=1)
        adaptive_lighting.apply(
            entity_id=ADAPTIVE_SWITCH,
            lights=[STAIRLIGHTS],
            turn_on_lights=True,
            adapt_brightness=True,
            adapt_color=True,
            transition=2,
        )
        task.sleep(45)
        if get_lighting_mode() == MODE_DAILY and not is_presence_locked():
            light.turn_off(entity_id=STAIRLIGHTS, transition=3)


@state_trigger(f"{BOTTOM_STAIRS_MOTION} == 'off'")
def motion_cleared_at_foot_of_stairs(old_value=None):
    """Note when the bottom-stairs sensor cleared, for direction of travel and vacancy."""
    global LAST_MOTION_CLEAR_TS, LAST_MOTION_SEEN_TS
    if old_value == "on":
        LAST_MOTION_CLEAR_TS = time.time()
        LAST_MOTION_SEEN_TS = LAST_MOTION_CLEAR_TS


def _seconds_since_bottom_stairs_activity() -> float:
    """Seconds since the bottom-stairs sensor last saw anyone (0 while it reads motion)."""
    if safe_state_get(BOTTOM_STAIRS_MOTION) == "on":
        return 0.0
    return max(0.0, time.time() - LAST_MOTION_SEEN_TS)


def _room_lights_off(transition):
    """Theater dimmer, room lights and stairs off, and the bias lights if they're on."""
    light.turn_off(entity_id=[THEATER_DIMMER, MASTER_ZIGBEE_GROUP, STAIRLIGHTS], transition=transition)
    if safe_state_get(BIAS_LIGHTS) == "on":
        switch.turn_off(entity_id=BIAS_LIGHTS)


def _mmwave_occupied() -> bool:
    """True while either mmWave sensor (theater or bar) reports someone. Unavailable
    counts as no, so a dead sensor falls back to the door + stairs logic alone."""
    return safe_state_get(MMWAVE_PRESENCE) == "on" or safe_state_get(MMWAVE_BAR) == "on"


def _recent_bottom_stairs_motion() -> bool:
    """True if someone was just at the foot of the stairs (motion now, or started/cleared within EXIT_WINDOW_S)."""
    if safe_state_get(BOTTOM_STAIRS_MOTION) == "on":
        return True
    last_seen = max(LAST_MOTION_BOTTOM_TS, LAST_MOTION_CLEAR_TS)
    return last_seen > 0 and 0 <= time.time() - last_seen < EXIT_WINDOW_S


@state_trigger(f"{DOOR_SENSOR} == 'off'")
def stair_door_closed(old_value=None):
    """The basement door closed. During curtain call: everything off (people walked
    out). In Daily Driver, a close right after someone walked up is a walk-out: wait
    WALKOUT_CONFIRM_S, then turn the lights off unless motion, the door or the mmWave
    shows someone is still downstairs."""
    global DIRECTION_OF_TRAVEL
    if is_booting() or old_value != "on" or is_presence_locked():
        return

    # 1. Curtain Call walkout: immediate room shutdown
    if safe_state_get(CURTAIN_CALL) == "on":
        task.sleep(1.5)
        state.set(CURTAIN_CALL, value="off")
        DIRECTION_OF_TRAVEL = "none"
        basement_all_off()
        return

    # 2. Social Mode or Theater Active: Preserve ambient lighting
    theater_active = _theater_active()
    if get_lighting_mode() == MODE_SOCIAL or theater_active:
        DIRECTION_OF_TRAVEL = "none"
        return

    # 3. Daily Driver: Descending entry -> allow slow walking.
    # The door sensor sometimes drops the "closed" report on the way down, so the
    # "opened" on the way up never registers. Recent bottom-stairs motion right
    # before this close still means a walk-out (on entry, the close comes before motion).
    if DIRECTION_OF_TRAVEL != "up" and not _recent_bottom_stairs_motion():
        return

    close_ts = time.time()
    # Two people coming down: the door opened moments ago, the first one tripped the
    # bottom-stairs sensor, then the second closed the door (2026-10-23). Not a walk-out.
    if (
        DIRECTION_OF_TRAVEL == "down"
        and 0 <= close_ts - LAST_DOOR_OPEN_TS < ENTRY_FOLLOW_WINDOW_S
        and LAST_MOTION_BOTTOM_TS >= LAST_DOOR_OPEN_TS
    ):
        DIRECTION_OF_TRAVEL = "none"
        return

    # 4. Daily Driver: likely walk-out. Confirm nobody is still downstairs: a fresh
    # bottom-stairs motion or the door reopening during the window cancels the shutoff.
    DIRECTION_OF_TRAVEL = "none"
    task.unique("walkout_confirm")
    task.sleep(WALKOUT_CONFIRM_S)
    if LAST_MOTION_BOTTOM_TS > close_ts or LAST_DOOR_OPEN_TS > close_ts:
        log.info("[Basement] Walk-out cancelled: activity downstairs after the door closed")
        return
    # Someone sitting still never trips the stairs sensor, but the mmWave sees them.
    # If it is still holding from the person who left, the mmWave vacancy check
    # below turns the lights off once the room goes quiet.
    if _mmwave_occupied():
        log.info("[Basement] Walk-out cancelled: mmWave still sees someone downstairs")
        return
    if (
        not is_presence_locked()
        and get_lighting_mode() == MODE_DAILY
        and safe_state_get(THEATER_IN_USE) == "off"
    ):
        _room_lights_off(2)


# ------------------------------------------------------------------------------
# VACANCY: LIGHTS OFF WHEN NOBODY IS DOWNSTAIRS
# ------------------------------------------------------------------------------
@state_trigger(f"{BOTTOM_STAIRS_MOTION} == 'off'", state_hold=14400)
def basement_door_open_vacancy_guard():
    """Daily Driver backstop: no bottom-stairs motion for 4 hours and neither mmWave
    sees anyone, so the lights go off."""
    if (
        get_lighting_mode() == MODE_DAILY
        and safe_state_get(THEATER_IN_USE) == "off"
        and not is_presence_locked()
        and safe_state_get(CURTAIN_CALL) == "off"
        and not _mmwave_occupied()
    ):
        _room_lights_off(4)


# != 'on' so an unavailable sensor doesn't block vacancy forever.
@state_trigger(
    f"{MMWAVE_PRESENCE} != 'on' and {MMWAVE_BAR} != 'on' and {BOTTOM_STAIRS_MOTION} != 'on'",
    state_hold=MMWAVE_VACANCY_S,
)
def basement_mmwave_vacancy():
    """Daily Driver: nobody seen by either mmWave or the stairs sensor for MMWAVE_VACANCY_S
    (15 min) -> all basement lights off. Catches walk-outs the door logic missed or cancelled."""
    if (
        get_lighting_mode() == MODE_DAILY
        and safe_state_get(THEATER_IN_USE) == "off"
        and not is_presence_locked()
        and safe_state_get(CURTAIN_CALL) == "off"
        and safe_state_get(LIGHTS_ACTIVE_SENSOR) == "on"
        and not _mmwave_occupied()
        and _seconds_since_bottom_stairs_activity() >= MMWAVE_VACANCY_S
    ):
        log.info("[Basement] Vacancy: no one seen for 15 min, turning lights off")
        _room_lights_off(4)


# ------------------------------------------------------------------------------
# THEATER LIGHTING (Daily Driver) AND CURTAIN CALL
# ------------------------------------------------------------------------------
def on_movie_screen() -> bool:
    """True when the Onn is on and showing an app rather than the home screen."""
    if safe_state_get(ONN_PRO) != "on":
        return False
    try:
        activity = safe_state_getattr(ONN_REMOTE, "current_activity")
        return activity != ONN_HOME_SCREEN
    except Exception:
        return True


# The Google TV home screen's package name
ONN_HOME_SCREEN = "com.google.android.apps.tv.launcherx"

# Last ADB state that wasn't a blip (see _adb_blip).
LAST_ADB_STATE = None


def _adb_blip(adb_state) -> bool:
    """The ADB player often reads 'off' for one poll (~8-20s) while the Onn is plainly on
    and playing (2026-11-01: dozens an hour). The Google TV remote player (ONN_PRO) does
    go off when the Onn really sleeps, so ADB 'off' while it reads 'on' is noise."""
    return adb_state == "off" and safe_state_get(ONN_PRO) == "on"


def get_media_state():
    """Onn playback state from the ADB player, holding the last real state through blips."""
    global LAST_ADB_STATE
    adb_state = safe_state_get(ONN_ADB)
    if _adb_blip(adb_state):
        return LAST_ADB_STATE or "idle"
    LAST_ADB_STATE = adb_state
    return adb_state


ADAPTIVE_PAUSED_BY_THEATER = False


def _pause_adaptive_for_theater():
    """Turn Adaptive Lighting off for a theater session, and remember that this did it."""
    global ADAPTIVE_PAUSED_BY_THEATER
    if safe_state_get(ADAPTIVE_SWITCH) == "on":
        switch.turn_off(entity_id=ADAPTIVE_SWITCH)
        ADAPTIVE_PAUSED_BY_THEATER = True


def _resume_adaptive_after_theater():
    """Turn Adaptive Lighting back on if a theater session paused it and ended without
    Curtain Call (which re-enables it itself)."""
    global ADAPTIVE_PAUSED_BY_THEATER
    if ADAPTIVE_PAUSED_BY_THEATER:
        ADAPTIVE_PAUSED_BY_THEATER = False
        if safe_state_get(ADAPTIVE_SWITCH) != "on":
            switch.turn_on(entity_id=ADAPTIVE_SWITCH)


@state_trigger(
    f"{THEATER_MODE}, {ONN_ADB}, {BATOCERA_STATE}, {THEATER_IN_USE}, "
    f"{ONN_REMOTE}.current_activity, {ONN_PRO}, {CURTAIN_CALL}, "
    f"{PC_ACTIVE_WINDOW}"
)
def theater_lighting_sync(var_name=None, value=None, old_value=None):
    """Set the basement lights to match the theater. Social Mode is left alone, except that
    sports paints team color once per session. Music, or a movie or game playing: lights off,
    bias lights on. A movie paused for 4 s, menus and pre-show: 3% glow on the dimmer, the
    rest off, bias on."""
    # ADB blip, or back from one to the same state: nothing changed, so don't touch the
    # lights (each blip used to flash the 3% glow mid-movie).
    if var_name == ONN_ADB and (_adb_blip(value) or (_adb_blip(old_value) and value == LAST_ADB_STATE)):
        return
    if is_booting() or safe_state_get(CURTAIN_CALL) == "on" or BLACKOUT_IN_PROGRESS:
        return

    mode = safe_state_get(THEATER_MODE)
    if mode != "sports" and safe_state_get(SPORTS_PAINTED) == "on":
        state.set(SPORTS_PAINTED, "off")
    media = get_media_state()
    batocera = safe_state_get(BATOCERA_STATE)
    lighting_mode = get_lighting_mode()
    in_use = safe_state_get(THEATER_IN_USE) == "on" or mode in ["movie", "game", "music", "sports"]

    # Sports: explicit game-day treatment (same as picking a palette).
    # Paint once per session; after that, whatever the user does (turn lights
    # off, pick a palette) stands. TV state changes must not repaint.
    if mode == "sports":
        if safe_state_get(SPORTS_PAINTED) == "on" and lighting_mode == MODE_SOCIAL:
            return
        state.set(SPORTS_PAINTED, "on")
        set_lighting_mode(MODE_SOCIAL, source="sports")
        _team_green_on(100, 2)
        # Stairs start green too, then time out like a path light.
        task.create(_sports_stair_path_light, STAIR_SPORTS_HOLD_S)
        return

    # Social Mode: theater never touches lights here — full stop
    if lighting_mode == MODE_SOCIAL:
        return
    if not in_use or mode == "off":
        _resume_adaptive_after_theater()
        return

    # Adaptive Lighting would grab the dimmer on turn_on (3% glow came up at AL's 30%)
    _pause_adaptive_for_theater()
    task.unique("theater_lighting_transition")

    # Music: always full dark + bias, no glow state, no pause nuance
    if mode == "music":
        light.turn_off(entity_id=[THEATER_DIMMER, MASTER_ZIGBEE_GROUP], transition=2)
        switch.turn_on(entity_id=BIAS_LIGHTS)
        return

    # Is a movie/game actively playing right now?
    pc_boxart_state = safe_state_getattr(THEATER_BOXART, "state")
    pc_playing = (pc_boxart_state == "playing") or (
        parse_pc_active_window(safe_state_get(PC_ACTIVE_WINDOW))[1] == "playing"
    )
    actively_playing = (
        (mode == "movie" and media == "playing")
        or (mode == "game" and (batocera == "playing" or pc_playing))
    )

    # SHOWTIME: active playback -> full blackout, bias on
    if actively_playing:
        light.turn_off(entity_id=[THEATER_DIMMER, MASTER_ZIGBEE_GROUP], transition=2)
        switch.turn_on(entity_id=BIAS_LIGHTS)
        return

    # INTERMISSION: paused mid-movie -> confirm it holds, then subtle glow
    if mode == "movie" and media == "paused" and on_movie_screen():
        task.sleep(4.0)
        if get_media_state() == "paused" and get_lighting_mode() != MODE_SOCIAL:
            _theater_glow()
            light.turn_off(entity_id=MASTER_ZIGBEE_GROUP, transition=2)
            switch.turn_on(entity_id=BIAS_LIGHTS)
        return

    # PRE-SHOW, MENUS, IDLE (game not yet playing): subtle glow, whole basement dark
    _theater_glow()
    light.turn_off(entity_id=MASTER_ZIGBEE_GROUP, transition=2)
    switch.turn_on(entity_id=BIAS_LIGHTS)


def _theater_glow():
    """3% dimmer glow. From off, skip the fade: the Leviton (Matter) dimmer would start
    at its last level (often 100% from daytime use) and visibly fade down from there."""
    if safe_state_get(THEATER_DIMMER) == "on":
        light.turn_on(entity_id=THEATER_DIMMER, brightness_pct=GLOW_PCT, transition=2)
    else:
        light.turn_on(entity_id=THEATER_DIMMER, brightness_pct=GLOW_PCT)


@state_trigger(f"{CURTAIN_CALL} == 'on'")
def handle_curtain_call_lighting():
    """House lights rise to 20% warm white for 10m on shutdown to let people exit."""
    light.turn_on(entity_id=THEATER_DIMMER, brightness_pct=20, transition=5)
    light.turn_on(entity_id=STAIRLIGHTS, brightness_pct=20, color_temp_kelvin=2700, transition=5)
    switch.turn_off(entity_id=BIAS_LIGHTS)

    if get_lighting_mode() != MODE_SOCIAL:
        light.turn_on(entity_id=MASTER_ZIGBEE_GROUP, brightness_pct=20, color_temp_kelvin=2700, transition=5)

    task.unique("curtain_call_timeout")
    task.sleep(600)

    if safe_state_get(CURTAIN_CALL) == "on":
        state.set(CURTAIN_CALL, value="off")
        set_lighting_mode(MODE_DAILY)
        light.turn_off(entity_id=[THEATER_DIMMER, MASTER_ZIGBEE_GROUP, STAIRLIGHTS], transition=4)


# ------------------------------------------------------------------------------
# ALL-OFF, THE LIGHTS-ON CHIP, AND THE POWER-CUT SWEEP
# ------------------------------------------------------------------------------
@service
def basement_all_off():
    """Every basement light and the bias lights off at once, all timers and effects
    stopped, mode back to Daily Driver. Sends the off twice to catch Zigbee drop-
    outs."""
    global BLACKOUT_IN_PROGRESS
    BLACKOUT_IN_PROGRESS = True

    # 1. Kill any ambient loops, timers, or transitions immediately
    for t in [
        "basement_ambient_loop",
        "stair_timer",
        "stair_red_timer",
        "stair_peek_timer",
        "curtain_call_timeout",
        "theater_lighting_transition",
    ]:
        task.unique(t)

    # 2. Reset state flags
    state.set(CURTAIN_CALL, value="off")
    state.set(SOCIAL_SOURCE, value="none")

    # 3. Direct turn-off across ALL targets: dimmer, stairs, master group, bias, AND 4 room zones
    all_targets = [
        THEATER_DIMMER,
        STAIRLIGHTS,
        MASTER_ZIGBEE_GROUP,
        "light.zigbee_bar_lights",
        "light.zigbee_lounge_lights",
        "light.zigbee_lounge_lights_1",
        "light.zigbee_lounge_lights_2",
        "light.zigbee_lounge_lights_3",
    ]
    light.turn_off(entity_id=all_targets, transition=0)
    switch.turn_off(entity_id=BIAS_LIGHTS)

    # 4. Set state directly so the mode is Daily Driver for next entry
    try:
        input_select.select_option(entity_id=LIGHTING_MODE_SELECT, option=MODE_DAILY)
    except Exception:
        pass
    state.set(LIGHTING_MODE_SELECT, value=MODE_DAILY)

    # 5. Dismiss dashboard active lights chip immediately
    state.set(
        LIGHTS_ACTIVE_SENSOR,
        value="off",
        new_attributes={
            "friendly_name": "Basement Lights Active",
            "icon": "mdi:lightbulb-group",
            "active_entities": [],
        },
    )

    # Confirmation cut to eliminate any Zigbee mesh dropouts or lingering dimmer ramp
    task.sleep(0.4)
    light.turn_off(entity_id=all_targets, transition=0)
    switch.turn_off(entity_id=BIAS_LIGHTS)
    BLACKOUT_IN_PROGRESS = False


@service
def toggle_all_basement_lights():
    """Dashboard toggle: anything on turns everything off; everything off turns the room
    lights on in Daily Driver."""
    monitored = [LIGHTS_ACTIVE_SENSOR, THEATER_DIMMER, STAIRLIGHTS, MASTER_ZIGBEE_GROUP, BIAS_LIGHTS]
    if any([safe_state_get(e) == "on" for e in monitored]):
        basement_all_off()
    else:
        set_lighting_mode(MODE_DAILY)
        light.turn_on(entity_id=MASTER_ZIGBEE_GROUP)


@time_trigger("startup")
@state_trigger(f"{THEATER_DIMMER}, {STAIRLIGHTS}, {MASTER_ZIGBEE_GROUP}, {BIAS_LIGHTS}")
@service
def update_basement_lights_active(**kwargs):
    """Keep binary_sensor.basement_lights_active, and its list of lights that are on, up
    to date for the dashboard chip."""
    # Only initialize if the telemetry entities don't already exist
    if safe_state_get(SENSOR_PALETTE) is None or safe_state_get(SENSOR_EFFECT) is None:
        initialize_basement_telemetry()

    monitored = [THEATER_DIMMER, STAIRLIGHTS, MASTER_ZIGBEE_GROUP, BIAS_LIGHTS]
    active_loads = [e for e in monitored if safe_state_get(e) == "on"]
    new_val = "on" if active_loads else "off"

    if safe_state_get(LIGHTS_ACTIVE_SENSOR) != new_val:
        state.set(
            LIGHTS_ACTIVE_SENSOR,
            value=new_val,
            new_attributes={
                "friendly_name": "Basement Lights Active",
                "icon": "mdi:lightbulb-group",
                "active_entities": active_loads,
            },
        )


# A Pi that booted within this window means power was cut (or the host
# rebooted). HA restarts and pyscript reloads also fire "startup" but leave
# host uptime high, so they skip the sweep.
POWER_RESTORE_BOOT_WINDOW_S = 900


def _host_uptime_s():
    """Host uptime in seconds (/proc/uptime is the Pi's, even inside Docker), or None."""
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except Exception:
        return None


@time_trigger("startup")
def power_restoration_on_boot():
    """At startup, run the power-cut sweep only if the Pi itself just booted (interlock
    4)."""
    uptime = _host_uptime_s()
    if uptime is not None and uptime > POWER_RESTORE_BOOT_WINDOW_S:
        log.info(f"[PowerRestore] Host up {int(uptime)}s; HA restart or reload, not a power cut. Skipping sweep.")
        return
    post_power_restoration_sweep()


@service
def post_power_restoration_sweep():
    """
    Sweeps basement and bedroom loads after mains power restoration.
    When mains AC cuts and restores, Zigbee bulbs (Third Reality) default to ON (100% white).
    If areas are vacant / presence is not locked, automatically extinguishes the bulbs
    and notifies via ntfy.sh so lights don't burn unattended. Can also be called on demand.
    """
    task.sleep(45.0)

    theater_active = (
        safe_state_get(THEATER_IN_USE) == "on"
        or safe_state_get(THEATER_MODE) in ["movie", "game", "music", "sports"]
        or safe_state_get(RECEIVER) == "on"
    )
    motion_active = safe_state_get(BOTTOM_STAIRS_MOTION) == "on"
    door_open = safe_state_get(DOOR_SENSOR) == "on"
    presence_locked = is_presence_locked()

    swept_areas = []

    # 1. Basement & Theater Sweep
    if not (theater_active or motion_active or door_open or presence_locked):
        basement_monitored = [THEATER_DIMMER, MASTER_ZIGBEE_GROUP, STAIRLIGHTS]
        active_basement = [e for e in basement_monitored if safe_state_get(e) == "on"]

        if active_basement or safe_state_get(BIAS_LIGHTS) == "on":
            log.warning(f"[PowerRestore] Active basement loads detected after reboot with vacant room: {active_basement}. Executing safety sweep.")
            _room_lights_off(2)

            if safe_state_get(RECEIVER_ZONE_2) == "on":
                media_player.turn_off(entity_id=RECEIVER_ZONE_2)

            swept_areas.append("Basement")

    # 2. Bedroom Zigbee Lamps Sweep
    if not presence_locked:
        bedroom_monitored = [BEDROOM_ZIGBEE_GROUP, BEDROOM_LAMP_1, BEDROOM_LAMP_2]
        active_bedroom = [e for e in bedroom_monitored if safe_state_get(e) == "on"]
        if active_bedroom:
            log.warning(f"[PowerRestore] Active bedroom loads detected after reboot: {active_bedroom}. Executing safety sweep.")
            light.turn_off(entity_id=[BEDROOM_ZIGBEE_GROUP, BEDROOM_LAMP_1, BEDROOM_LAMP_2], transition=2)
            swept_areas.append("Bedroom")

    if swept_areas:
        safe_service(
            notify.ntfy,
            title="⚡ Power Restored — Safety Sweep Executed",
            message=f"Home Assistant rebooted following power cut. Extinguished smart bulbs that defaulted ON in: {', '.join(swept_areas)}. System healthy.",
        )


@service
def initialize_basement_telemetry(**kwargs):
    """Create the palette and effect sensors the dashboard reads."""
    state.set(
        SENSOR_PALETTE,
        value=CURRENT_PALETTE or "synthwave",
        new_attributes={
            "friendly_name": "Active Spatial Palette",
            "icon": "mdi:palette",
            "available_palettes": list(PALETTES.keys()),
        },
    )
    state.set(
        SENSOR_EFFECT,
        value=CURRENT_EFFECT or "static",
        new_attributes={
            "friendly_name": "Active Lighting Modifier",
            "icon": "mdi:creation",
            "available_effects": ["static", "drift"],
        },
    )


# ------------------------------------------------------------------------------
# PALETTE AND PARTY SERVICES (dashboard buttons)
# ------------------------------------------------------------------------------
@service
def select_palette(palette: str):
    """Pick a color palette: Social Mode, then paint it (static or drifting, per the
    current effect)."""
    global CURRENT_PALETTE
    if palette not in PALETTES:
        return

    CURRENT_PALETTE = palette
    state.set(SENSOR_PALETTE, value=palette)
    set_lighting_mode(MODE_SOCIAL)

    if CURRENT_EFFECT == "static":
        apply_static_palette(palette, transition=2)
    else:
        task.create(_ambient_loop_runner)


@service
def select_effect_modifier(effect: str):
    """Pick static or a drift effect for the palette, and restart it."""
    global CURRENT_EFFECT
    if effect in {"static", *DRIFT_EFFECTS}:
        CURRENT_EFFECT = effect
        state.set(SENSOR_EFFECT, value=effect)
        set_lighting_mode(MODE_SOCIAL)
        task.create(_ambient_loop_runner)


@service
def mood_reset_normal():
    """Back to normal: no palette or effect, Daily Driver, Adaptive Lighting on and
    applied, stairs off."""
    global CURRENT_EFFECT
    CURRENT_EFFECT = "static"
    state.set(SENSOR_EFFECT, value="static")
    state.set(SENSOR_PALETTE, value="normal")
    task.unique("basement_ambient_loop")

    set_lighting_mode(MODE_DAILY)
    switch.turn_on(entity_id=ADAPTIVE_SWITCH)
    adaptive_lighting.apply(
        entity_id=ADAPTIVE_SWITCH,
        lights=[THEATER_DIMMER, MASTER_ZIGBEE_GROUP, STAIRLIGHTS],
        turn_on_lights=False,
        adapt_brightness=True,
        adapt_color=True,
        transition=2,
    )
    light.turn_off(entity_id=STAIRLIGHTS, transition=3)


@service
def effect_bar_toast():
    """Flash the bar and stairs amber three times for a toast, then go back to the
    palette."""
    task.unique("basement_ambient_loop")
    running_effect = CURRENT_EFFECT
    toast_amber = [255, 170, 0]
    bar_targets = [ROOM_ZONES[0], STAIRLIGHTS]

    for _ in range(3):
        light.turn_on(entity_id=bar_targets, rgb_color=toast_amber, brightness_pct=100, transition=0)
        task.sleep(0.40)
        light.turn_on(entity_id=bar_targets, brightness_pct=10, transition=0)
        task.sleep(0.30)

    light.turn_on(entity_id=bar_targets, rgb_color=toast_amber, brightness_pct=100, transition=0)
    task.sleep(0.8)

    if running_effect != "static":
        apply_ambient_lighting()
    else:
        apply_static_palette(CURRENT_PALETTE or "synthwave", transition=2)


@service
def effect_eagles_chant():
    """Manual trigger: plays the Zigbee-safe solid Kelly Green Philadelphia Eagles touchdown chant."""
    task.unique("basement_ambient_loop")
    eagles_green = EAGLES_RGB
    stair_green = {"hs_color": EAGLES_STAIR_HS}

    # 1. Spell-out: E - A - G - L - E - S (Deliberate, rhythmic stadium green surges)
    for _ in range(6):
        _team_green_on(100, 0, eagles_green, stair_green)
        task.sleep(0.65)
        _team_green_on(15, 0, eagles_green, stair_green)
        task.sleep(0.45)

    # 2. Stadium anticipation breath
    task.sleep(0.55)

    # 3. 'EA - GLES!' Climax
    # Syllable 1: 'EA-'
    _team_green_on(100, 0, eagles_green, stair_green)
    task.sleep(0.55)
    _team_green_on(15, 0, eagles_green, stair_green)
    task.sleep(0.35)

    # Syllable 2: '-GLES!'
    _team_green_on(100, 0, eagles_green, stair_green)
    task.sleep(0.85)

    # End holding solid team green
    task.sleep(0.35)
    _team_green_on(100, 2, eagles_green, stair_green)


@service
def toggle_ambient_drift():
    """Dashboard button: switch the palette between static and drift."""
    cur_eff = safe_state_get(SENSOR_EFFECT, "static")
    new_eff = "static" if cur_eff in DRIFT_EFFECTS else "drift"
    select_effect_modifier(new_eff)


@service
def toggle_lighting_mode():
    """Simple 1-tap toggle between Daily Driver and Social/Party Mode."""
    cur = get_lighting_mode()
    if cur == MODE_SOCIAL:
        set_lighting_mode(MODE_DAILY)
        mood_reset_normal()
    else:
        set_lighting_mode(MODE_SOCIAL)

# ------------------------------------------------------------------------------
# DASHBOARD MODE DRAWER
# ------------------------------------------------------------------------------
@service
def toggle_mode_drawer():
    """Open or close the dashboard's mode drawer. It closes itself after 10 s."""
    task.unique("mode_drawer_timer")
    cur = safe_state_get(MODE_EXPANDED, "off")
    new_val = "off" if cur == "on" else "on"
    state.set(MODE_EXPANDED, value=new_val)

    if new_val == "on":
        task.sleep(10)
        if safe_state_get(MODE_EXPANDED) == "on":
            state.set(MODE_EXPANDED, value="off")


@service
def select_lighting_mode_ui(mode: str):
    """Mode drawer button: set the lighting mode and close the drawer."""
    task.unique("mode_drawer_timer")
    set_lighting_mode(mode)
    state.set(MODE_EXPANDED, value="off")


# ------------------------------------------------------------------------------
# DASHBOARD DRAWERS AND THEATER MEDIA BUTTONS
# ------------------------------------------------------------------------------
@service
def toggle_basement_drawer(drawer: str = "theater"):
    """Dashboard drawer buttons: open the chosen drawer, or close it ('none') if it's open."""
    cur = safe_state_get(DRAWER_SELECT, "theater")
    target = "none" if cur == drawer else drawer
    try:
        input_select.select_option(entity_id=DRAWER_SELECT, option=target)
    except Exception:
        pass
    # Kept for compatibility with headless test runners:
    state.set(DRAWER_SELECT, value=target)

def _get_active_media_player():
    """The player the theater media buttons control: Spotify in music mode, otherwise
    the Onn."""
    return SPOTIFY_PLAYER if safe_state_get(THEATER_MODE) == "music" else ONN_PRO


@service
def theater_media_play_pause():
    """Play or pause the active player."""
    safe_service(media_player.media_play_pause, entity_id=_get_active_media_player())


@service
def theater_media_next():
    """Next track on the active player."""
    safe_service(media_player.media_next_track, entity_id=_get_active_media_player())


@service
def theater_media_previous():
    """Previous track on the active player."""
    safe_service(media_player.media_previous_track, entity_id=_get_active_media_player())