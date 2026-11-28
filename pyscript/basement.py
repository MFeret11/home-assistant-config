# ==============================================================================
# BASEMENT LIGHTING: modes, stairs, vacancy, theater lighting, palettes
# ==============================================================================
# Sections, in order (search for the capitalised heading):
#   ENTITY IDS AND SETTINGS
#   SMALL HELPERS, AND HELPER ENTITIES CREATED AT LOAD
#   LIGHTING MODE (Daily Driver or Social Mode)
#   PALETTES AND THE 4 AM RESET
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

VALID_MODES = {MODE_DAILY, MODE_SOCIAL}

# Palettes (colors, zones, bulb order) live in pyscript/modules/basement_palettes.py.
from basement_palettes import (
    PALETTES,
    LIBRARY_TABS,
    TAB_ALL,
    MY_THEME_ICON,
    ROOM_ZONES,
    ROOM_BULBS,
    BAR_BULBS,
    STAIR_BULBS,
    room_plan,
    stair_plan,
    settings_from_state,
    swatch,
    library_entries,
    filter_entries,
    team_palettes,
    TEAM_THEME_PREFIX,
    new_theme_id,
    read_themes_file,
    write_themes_file,
)

# "normal" means no palette: Daily Driver, or Social Mode entered from the header chip.
NO_PALETTE = "normal"

# Sports themes come from the teams the Team Lights app publishes
# (pyscript/apps/team_lights.py). Picking one tells the app which team's scores
# flash the lights; after a flash, the theme is painted back.
TEAM_LIGHTS_TEAMS = "pyscript.team_lights_teams"
TEAM_LIGHTS_PICKED = "pyscript.team_lights_picked"
TEAM_LIGHTS_CELEBRATION = "pyscript.team_lights_celebration"

# THEME LIBRARY (the dashboard's Themes pop-up). Themes saved or edited on the
# dashboard live in this file, {theme id: theme}; see basement_palettes.py.
THEMES_FILE = "/config/basement_themes.json"
CUSTOM_THEMES = {}
LIBRARY_SLOTS = 12          # theme pills per page in the pop-up
LIBRARY_PAGE = 0
LIBRARY_TAB = "pyscript.basement_theme_tab"          # all, moods, holidays, sports, mine
LIBRARY_STATUS = "pyscript.basement_theme_library"   # "results" or "none"
LIBRARY_PAGER = "pyscript.basement_theme_pager"      # "on" when there's more than one page
THEME_SEARCH_INPUT = "input_text.basement_theme_search"
THEME_NAME_INPUT = "input_text.basement_theme_name"
# The editor: "off", or what is being edited: "new", "mine" (one of ours),
# "builtin" (an unedited built-in) or "edited" (an edited built-in).
THEME_EDITOR = "pyscript.basement_theme_editor"
# Editor "Copy a color" tool: off, pick (tap the bulb whose color to copy) or
# paint (each tapped bulb or group gets that color). `settings` = the copied color.
COPY_TOOL = "pyscript.basement_theme_copy"
# What the editor can paint: every bulb, plus these groups.
EDITOR_GROUPS = [
    "light.zigbee_basement_lights",  # all room bulbs
    "light.zigbee_bar_lights",
    "light.zigbee_lounge_lights",
    "light.zigbee_lounge_lights_1",  # lounge bulbs 1-2
    "light.zigbee_lounge_lights_2",  # lounge bulbs 3-5
    "light.zigbee_lounge_lights_3",  # lounge bulbs 6-7
    "light.stairlights",
]

# Gap between bulb commands when painting, so the Zigbee mesh isn't flooded.
PAINT_STEP_S = 0.25
BULB_STEP_S = 0.15     # stair bulbs one by one, and the toast putting bulbs back
# Painting a theme takes a few seconds; a newer pick, a flash or all-off cancels it.
PAINT_TASK = "basement_paint"

# Runtime tracking state (CURRENT_PALETTE is restored from the sensor at load, below)
CURRENT_PALETTE = NO_PALETTE
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
# Paused / pre-show glow on the theater dimmer. The cans barely show at 3%; 6% reads as a faint glow (2026-11-21).
GLOW_PCT = 6
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

# The library tab survives HA restarts; the editor always starts closed.
state.persist(LIBRARY_TAB, default_value=TAB_ALL)
state.set(THEME_EDITOR, "off", {"friendly_name": "Basement theme editor"})

# A reload keeps the palette that was painted. (It used to fall back to Synthwave, so
# the stairs came on pink in Social Mode after any restart.) Checked after the palette
# helpers below are defined, in restore_current_palette().


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
    claimed it, Adaptive Lighting off. Daily Driver: stop any palette still painting, then
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
        task.unique(PAINT_TASK)
        if safe_state_get(CURTAIN_CALL) == "on":
            return  # curtain call owns the lights until its window ends
        if safe_state_get(THEATER_IN_USE) == "on":
            theater_lighting_sync()
        else:
            mood_reset_normal()


# ------------------------------------------------------------------------------
# PALETTES AND THE 4 AM RESET
# The palettes themselves are in pyscript/modules/basement_palettes.py: per-zone
# colors and bulb-by-bulb holiday patterns; themes saved on the dashboard are in THEMES_FILE.
# ------------------------------------------------------------------------------
def _theme_slot_entity(slot):
    return f"pyscript.basement_theme_slot_{slot}"


def _team_themes():
    """{theme id: palette} for the Sports tab, one per Team Lights team."""
    return team_palettes(safe_state_getattr(TEAM_LIGHTS_TEAMS, "teams") or [])


def _get_palette(palette_id):
    """A theme to paint: our own or an edited copy first, then the built-in or team
    theme. None if unknown."""
    if palette_id in CUSTOM_THEMES:
        return CUSTOM_THEMES[palette_id]
    return PALETTES.get(palette_id) or _team_themes().get(palette_id)


def _sync_team_pick(palette_id):
    """Tell Team Lights which team the theme in use belongs to ("" for none)."""
    themes = _team_themes()
    if palette_id.startswith(TEAM_THEME_PREFIX) and palette_id not in themes:
        return  # Team Lights hasn't published its teams yet (startup); keep the pick
    team = (themes.get(palette_id) or {}).get("team", "")
    picked = safe_state_get(TEAM_LIGHTS_PICKED, "none")
    if (team or "none") != picked:
        pyscript.team_lights_pick(team=team)


def _palette_label(palette_id):
    """The name the dashboard shows ("" for no palette)."""
    theme = _get_palette(palette_id)
    return (theme or {}).get("name", "")


def _publish_palette_sensor(palette_id):
    """Set sensor.basement_palette: the theme in use, its name and its swatch colors."""
    theme = _get_palette(palette_id)
    state.set(
        SENSOR_PALETTE,
        value=palette_id,
        new_attributes={
            "friendly_name": "Active Spatial Palette",
            "icon": "mdi:palette",
            "label": _palette_label(palette_id),
            "swatch": (theme.get("swatch") or swatch(theme)) if theme else [],
        },
    )
    _sync_team_pick(palette_id)


def _send_light(entity_id, settings, transition):
    """One bulb or group to the given settings; {"off": True} turns it off."""
    if settings.get("off"):
        light.turn_off(entity_id=entity_id, transition=transition)
    else:
        light.turn_on(entity_id=entity_id, transition=transition, **settings)


def _paint_stairs(palette, transition) -> bool:
    """Light the stairs in a palette's stair colors. False if it has none."""
    plan = stair_plan(palette) if palette else []
    for entity_id, settings in plan:
        _send_light(entity_id, settings, transition)
        if len(plan) > 1:
            task.sleep(BULB_STEP_S)
    return bool(plan)


def _paint_room(palette, transition):
    """Paint the room bulbs (or zone groups) in a palette."""
    for entity_id, settings in room_plan(palette):
        _send_light(entity_id, settings, transition)
        task.sleep(PAINT_STEP_S)


def apply_static_palette(palette_id: str, transition: int = 2):
    """Paint a palette across the stairs and the room. Unknown ids do nothing."""
    palette = _get_palette(palette_id)
    if not palette:
        log.warning(f"[Basement] No palette '{palette_id}' to paint")
        return
    _paint_stairs(palette, transition)
    task.sleep(0.2)
    _paint_room(palette, transition)


def restore_current_palette():
    """At load: pick up the palette the sensor says is painted, if it still exists."""
    global CURRENT_PALETTE
    restored = safe_state_get(SENSOR_PALETTE) or NO_PALETTE
    # A team theme counts even before Team Lights has published its teams.
    known = _get_palette(restored) or restored.startswith(TEAM_THEME_PREFIX)
    CURRENT_PALETTE = restored if known else NO_PALETTE


restore_current_palette()

@time_trigger("cron(0 4 * * *)")
def safe_nightly_social_reset():
    """Nightly hygiene at 4 AM: clears social/guest modes without waking dormant lights.
    Skipped while a theater session is running, so a late movie or game keeps its lights.
    It does clear a curtain call left on (a reload can kill its timer)."""
    global CURRENT_PALETTE
    if _theater_active():
        log.info("[Basement] 4 AM reset skipped: theater in use")
        return
    task.unique(PAINT_TASK)
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
    CURRENT_PALETTE = "speakeasy"
    _publish_palette_sensor(CURRENT_PALETTE)

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

    if safe_state_get(CURTAIN_CALL) == "on":
        return  # curtain call has the stairs lit for people leaving

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
        # Social Mode: stairs that are already lit stay exactly as they are (a palette,
        # or colors set by hand). Off stairs come on in the palette's stair color, or
        # circadian white with no palette, and stay on.
        if safe_state_get(STAIRLIGHTS) == "on":
            return
        if not _paint_stairs(_get_palette(CURRENT_PALETTE), 1):
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
    if safe_state_get(CURTAIN_CALL) == "on":
        LAST_MOTION_BOTTOM_TS = time.time()  # still counts for walk-out detection
        return  # curtain call has the lights set for people leaving
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
        safe_service(switch.turn_on, entity_id=ADAPTIVE_SWITCH)  # lights are off; ready for next time
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
    bias lights on. A movie paused for 4 s, menus and pre-show: glow (GLOW_PCT) on the dimmer, the
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
    """Dimmer glow at GLOW_PCT. From off, skip the fade: the Leviton (Matter) dimmer would start
    at its last level (often 100% from daytime use) and visibly fade down from there."""
    if safe_state_get(THEATER_DIMMER) == "on":
        light.turn_on(entity_id=THEATER_DIMMER, brightness_pct=GLOW_PCT, transition=2)
    else:
        light.turn_on(entity_id=THEATER_DIMMER, brightness_pct=GLOW_PCT)


# House lights after a session: this long at least, and then until nobody is seen.
CURTAIN_CALL_S = 600
CURTAIN_HOLD_CHECK_S = 60


@state_trigger(f"{CURTAIN_CALL} == 'on'")
def handle_curtain_call_lighting():
    """House lights for people leaving: 20% warm white on the dimmer, the stairs and (in
    Daily Driver) the room. They stay up for CURTAIN_CALL_S, and after that for as long as
    the mmWave sees someone; then they go off and Adaptive Lighting comes back on. The door
    closing ends it early (stair_door_closed). Adaptive Lighting stays off meanwhile: at
    night it pulled these lights down to a level the cans can't show (2026-11-14)."""
    if safe_state_get(ADAPTIVE_SWITCH) == "on":
        switch.turn_off(entity_id=ADAPTIVE_SWITCH)
    light.turn_on(entity_id=THEATER_DIMMER, brightness_pct=20, transition=5)
    light.turn_on(entity_id=STAIRLIGHTS, brightness_pct=20, color_temp_kelvin=2700, transition=5)
    switch.turn_off(entity_id=BIAS_LIGHTS)

    if get_lighting_mode() != MODE_SOCIAL:
        light.turn_on(entity_id=MASTER_ZIGBEE_GROUP, brightness_pct=20, color_temp_kelvin=2700, transition=5)

    task.unique("curtain_call_timeout")
    task.sleep(CURTAIN_CALL_S)
    # Still people downstairs (staying to talk): keep the house lights up.
    while safe_state_get(CURTAIN_CALL) == "on" and _mmwave_occupied():
        task.sleep(CURTAIN_HOLD_CHECK_S)

    if safe_state_get(CURTAIN_CALL) == "on":
        state.set(CURTAIN_CALL, value="off")
        set_lighting_mode(MODE_DAILY)
        light.turn_off(entity_id=[THEATER_DIMMER, MASTER_ZIGBEE_GROUP, STAIRLIGHTS], transition=4)
        safe_service(switch.turn_on, entity_id=ADAPTIVE_SWITCH)


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
        PAINT_TASK,
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


@time_trigger("startup")
@service
def initialize_basement_telemetry(**kwargs):
    """Publish the palette sensor and theme library the dashboard reads. Runs at every load,
    so a palette added to basement_palettes.py shows in the theme library right away."""
    load_theme_library()
    _publish_palette_sensor(CURRENT_PALETTE)
    _set_copy_tool("off")


# ------------------------------------------------------------------------------
# PALETTE AND PARTY SERVICES (dashboard buttons)
# ------------------------------------------------------------------------------
@service
def select_palette(palette: str):
    """Pick a theme (built-in, edited or our own): Social Mode, then paint it."""
    global CURRENT_PALETTE
    if not _get_palette(palette):
        log.warning(f"[Basement] select_palette: no palette '{palette}'")
        return

    CURRENT_PALETTE = palette
    _publish_palette_sensor(palette)
    set_lighting_mode(MODE_SOCIAL)
    task.unique(PAINT_TASK)
    apply_static_palette(palette, transition=2)


@state_trigger(TEAM_LIGHTS_TEAMS)
def team_list_changed():
    """Team Lights published its teams (at load): show their themes in the library."""
    _refresh_library()
    _publish_palette_sensor(CURRENT_PALETTE)


@state_trigger(f"{TEAM_LIGHTS_CELEBRATION} == 'off'")
def team_celebration_done():
    """A score flash ends in solid team color; put the team's theme back."""
    if CURRENT_PALETTE in _team_themes() and get_lighting_mode() == MODE_SOCIAL:
        task.unique(PAINT_TASK)
        apply_static_palette(CURRENT_PALETTE, transition=2)


# ------------------------------------------------------------------------------
# THEME LIBRARY (the dashboard's Themes pop-up)
# The pop-up has LIBRARY_SLOTS fixed pills; _refresh_library() fills them with the
# themes that match the tab and search box, one page at a time. Hold a pill to edit
# that theme: it is painted, the pop-up shows the bulbs to change by hand, and Save
# writes the bulbs as they are to THEMES_FILE.
# ------------------------------------------------------------------------------
def _clean_text(value):
    value = (value or "").strip()
    return "" if value in ("unknown", "unavailable") else value


def _refresh_library():
    """Fill the pop-up's theme pills for the current tab, search text and page."""
    global LIBRARY_PAGE
    tab = safe_state_get(LIBRARY_TAB, TAB_ALL)
    if tab not in LIBRARY_TABS:
        tab = TAB_ALL
    query = _clean_text(safe_state_get(THEME_SEARCH_INPUT, ""))
    found = filter_entries(library_entries(CUSTOM_THEMES, _team_themes()), tab, query)
    pages = max(1, (len(found) + LIBRARY_SLOTS - 1) // LIBRARY_SLOTS)
    LIBRARY_PAGE = max(0, min(LIBRARY_PAGE, pages - 1))
    shown = found[LIBRARY_PAGE * LIBRARY_SLOTS:(LIBRARY_PAGE + 1) * LIBRARY_SLOTS]

    for i in range(LIBRARY_SLOTS):
        entry = shown[i] if i < len(shown) else None
        state.set(
            _theme_slot_entity(i + 1),
            value="shown" if entry else "hidden",
            new_attributes={
                "friendly_name": f"Basement theme slot {i + 1}",
                "palette_id": entry["id"] if entry else "",
                "name": entry["name"] if entry else "",
                "icon": entry["icon"] if entry else "mdi:palette",
                "swatch": entry["swatch"] if entry else [],
                "edited": entry["edited"] if entry else False,
            },
        )
    state.set(
        LIBRARY_STATUS,
        value="results" if found else "none",
        new_attributes={"friendly_name": "Basement theme library", "count": len(found), "tab": tab, "query": query},
    )
    state.set(
        LIBRARY_PAGER,
        value="on" if pages > 1 else "off",
        new_attributes={"friendly_name": "Basement theme pages", "label": f"Page {LIBRARY_PAGE + 1} of {pages}"},
    )


def load_theme_library():
    """Read our saved themes from THEMES_FILE (at load), then refresh the pop-up."""
    global CUSTOM_THEMES
    try:
        CUSTOM_THEMES = task.executor(read_themes_file, THEMES_FILE) or {}
    except Exception as e:
        log.warning(f"[Basement] Couldn't read {THEMES_FILE}: {e}")
        CUSTOM_THEMES = {}
    restore_current_palette()
    _refresh_library()


def _write_themes(themes) -> bool:
    try:
        task.executor(write_themes_file, THEMES_FILE, themes)
        return True
    except Exception as e:
        log.error(f"[Basement] Couldn't write {THEMES_FILE}: {e}")
        _theme_notice(f"Couldn't save the theme ({e}).")
        return False


def _theme_notice(message):
    """A dashboard notification about the theme library (replaces the last one)."""
    safe_service(
        persistent_notification.create,
        title="Basement themes",
        message=message,
        notification_id="basement_themes",
    )


def _slot_palette_id(slot):
    try:
        return safe_state_getattr(_theme_slot_entity(int(slot)), "palette_id") or ""
    except (TypeError, ValueError):
        return ""


def _open_editor(kind, palette_id, name):
    _set_copy_tool("off")
    state.set(
        THEME_EDITOR,
        value=kind,
        new_attributes={"friendly_name": "Basement theme editor", "palette_id": palette_id, "name": name},
    )
    safe_service(input_text.set_value, entity_id=THEME_NAME_INPUT, value=name)


@state_trigger(THEME_SEARCH_INPUT)
def theme_search_changed(value=None):
    """The search box changed: back to the first page of matches."""
    global LIBRARY_PAGE
    LIBRARY_PAGE = 0
    _refresh_library()


@service
def select_theme_slot(slot: int):
    """Tap a theme pill: paint that theme."""
    palette_id = _slot_palette_id(slot)
    if palette_id:
        select_palette(palette_id)


@service
def select_theme_tab(tab: str):
    """Library filter: all, moods, holidays, sports or mine."""
    global LIBRARY_PAGE
    if tab in LIBRARY_TABS:
        state.set(LIBRARY_TAB, value=tab)
        LIBRARY_PAGE = 0
        _refresh_library()


@service
def theme_page(step: int = 1):
    """Next (1) or previous (-1) page of themes, wrapping around."""
    global LIBRARY_PAGE
    count = int(safe_state_getattr(LIBRARY_STATUS, "count") or 0)
    pages = max(1, (count + LIBRARY_SLOTS - 1) // LIBRARY_SLOTS)
    LIBRARY_PAGE = (LIBRARY_PAGE + int(step)) % pages
    _refresh_library()


@service
def clear_theme_search():
    safe_service(input_text.set_value, entity_id=THEME_SEARCH_INPUT, value="")
    theme_search_changed()


@service
def edit_theme_slot(slot: int):
    """Hold a theme pill: paint it and open the editor on it."""
    palette_id = _slot_palette_id(slot)
    if not palette_id:
        return
    select_palette(palette_id)
    if palette_id not in PALETTES and palette_id not in _team_themes():
        kind = "mine"
    elif palette_id in CUSTOM_THEMES:
        kind = "edited"
    else:
        kind = "builtin"
    _open_editor(kind, palette_id, _palette_label(palette_id))


@service
def new_theme():
    """"New from current lights": open the editor on the lights as they are now."""
    _open_editor("new", "", "")


@service
def close_theme_editor():
    _set_copy_tool("off")
    state.set(THEME_EDITOR, value="off", new_attributes={"palette_id": "", "name": ""})
    safe_service(input_text.set_value, entity_id=THEME_NAME_INPUT, value="")


# ------------------------------------------------------------------------------
# EDITOR TOOLS: copy one bulb's color to others, and repeat a pattern
# ------------------------------------------------------------------------------
def _set_copy_tool(mode, source="", settings=None):
    state.set(COPY_TOOL, value=mode, new_attributes={
        "friendly_name": "Basement theme copy tool",
        "source": source,
        "source_name": state.getattr(source).get("friendly_name", source) if source else "",
        "settings": settings or {},
    })


@service
def theme_copy_start():
    """Editor "Copy a color": next, tap the bulb whose color to copy."""
    _set_copy_tool("pick")


@service
def theme_copy_stop():
    _set_copy_tool("off")


@service
def theme_copy_tap(light: str):
    """A bulb or group tapped while copying: the first tap picks up its color, each
    tap after that paints the copied color on what was tapped."""
    if light not in ROOM_BULBS + STAIR_BULBS + EDITOR_GROUPS:
        return
    mode = safe_state_get(COPY_TOOL, "off")
    if mode == "pick":
        settings = settings_from_state(safe_state_get(light), state.getattr(light))
        if not settings:
            _theme_notice("That light isn't responding; pick another one to copy.")
            return
        _set_copy_tool("paint", source=light, settings=settings)
    elif mode == "paint":
        settings = safe_state_getattr(COPY_TOOL, "settings") or {}
        if settings:
            _send_light(light, settings, 1)


# How many colors "Repeat pattern" can repeat (the first N room bulbs).
REPEAT_MAX = 3


@service
def theme_repeat_pattern(count: int = 2):
    """Editor "Repeat pattern": the colors of the first `count` room bulbs, in
    ROOM_BULBS order (Bar 1, Bar 2, Lounge 1...), repeated along the rest of the
    room, the way the holiday themes alternate."""
    count = max(2, min(int(count), REPEAT_MAX))
    first = [settings_from_state(safe_state_get(b), state.getattr(b)) for b in ROOM_BULBS[:count]]
    if None in first:
        _theme_notice("One of the first bulbs isn't responding, so there's no pattern to repeat.")
        return
    task.unique(PAINT_TASK)
    for i in range(count, len(ROOM_BULBS)):
        _send_light(ROOM_BULBS[i], first[i % count], 1)
        task.sleep(PAINT_STEP_S)


def _snapshot(bulbs):
    """{bulb: settings} for the bulbs that are reporting, as they are now."""
    found = {}
    for bulb in bulbs:
        settings = settings_from_state(safe_state_get(bulb), state.getattr(bulb))
        if settings:
            found[bulb] = settings
    return found


@service
def save_theme(as_new: bool = False):
    """Editor Save: store every room and stair bulb as it is now (color, brightness, or
    off). Saves over the theme being edited (an edited copy, for a built-in), or as a
    new theme of our own for "new" or as_new. The name comes from the name box."""
    global CURRENT_PALETTE, CUSTOM_THEMES
    kind = safe_state_get(THEME_EDITOR, "off")
    editing_id = safe_state_getattr(THEME_EDITOR, "palette_id") or ""
    name = _clean_text(safe_state_get(THEME_NAME_INPUT, ""))[:40]

    bulbs = _snapshot(ROOM_BULBS)
    stair_bulbs = _snapshot(STAIR_BULBS)
    if not [s for s in list(bulbs.values()) + list(stair_bulbs.values()) if not s.get("off")]:
        _theme_notice("Nothing to save: turn on some basement lights first.")
        return

    if as_new or kind in ("new", "off") or not editing_id:
        theme_id = new_theme_id(CUSTOM_THEMES)
        icon = MY_THEME_ICON
        if not name:
            name = f"My theme {theme_id.split('_')[-1]}"
        elif editing_id and name == _palette_label(editing_id):
            name = f"{name} (copy)"
    else:
        theme_id = editing_id
        built_in = PALETTES.get(theme_id) or _team_themes().get(theme_id)
        icon = (built_in or CUSTOM_THEMES.get(theme_id) or {}).get("icon") or MY_THEME_ICON
        name = name or _palette_label(theme_id)

    theme = {
        "name": name,
        "icon": icon,
        "bulbs": bulbs,
        "stair_bulbs": stair_bulbs,
        "saved_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    theme["swatch"] = swatch(theme)
    themes = dict(CUSTOM_THEMES)
    themes[theme_id] = theme
    if not _write_themes(themes):
        return
    CUSTOM_THEMES = themes
    log.info(f"[Basement] Saved theme {theme_id}: {name}")

    # The lights already look like the theme, so it is the one in use.
    CURRENT_PALETTE = theme_id
    _publish_palette_sensor(theme_id)
    close_theme_editor()
    _refresh_library()


@service
def delete_theme():
    """Editor Delete (one of ours) or Reset to original (an edited built-in)."""
    global CURRENT_PALETTE, CUSTOM_THEMES
    kind = safe_state_get(THEME_EDITOR, "off")
    theme_id = safe_state_getattr(THEME_EDITOR, "palette_id") or ""
    if kind not in ("mine", "edited") or theme_id not in CUSTOM_THEMES:
        return
    themes = dict(CUSTOM_THEMES)
    del themes[theme_id]
    if not _write_themes(themes):
        return
    CUSTOM_THEMES = themes

    if CURRENT_PALETTE == theme_id:
        if kind == "edited":
            apply_static_palette(theme_id, transition=2)  # back to the original colors
        else:
            CURRENT_PALETTE = NO_PALETTE
        _publish_palette_sensor(CURRENT_PALETTE)
    close_theme_editor()
    _refresh_library()


@service
def mood_reset_normal():
    """Back to normal: no palette, Daily Driver, Adaptive Lighting on and applied,
    stairs off."""
    global CURRENT_PALETTE
    CURRENT_PALETTE = NO_PALETTE
    _publish_palette_sensor(NO_PALETTE)
    task.unique(PAINT_TASK)

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
    """Flash the bar and stairs amber three times for a toast, then put them back the
    way they were."""
    task.unique(PAINT_TASK)
    toast_amber = [255, 170, 0]
    bar_targets = [ROOM_ZONES[0], STAIRLIGHTS]
    before = _snapshot(BAR_BULBS + STAIR_BULBS)

    for _ in range(3):
        light.turn_on(entity_id=bar_targets, rgb_color=toast_amber, brightness_pct=100, transition=0)
        task.sleep(0.40)
        light.turn_on(entity_id=bar_targets, brightness_pct=10, transition=0)
        task.sleep(0.30)

    light.turn_on(entity_id=bar_targets, rgb_color=toast_amber, brightness_pct=100, transition=0)
    task.sleep(0.8)

    for bulb, settings in before.items():
        _send_light(bulb, settings, 2)
        task.sleep(BULB_STEP_S)


@service
def effect_eagles_chant():
    """Manual trigger: plays the Zigbee-safe solid Kelly Green Philadelphia Eagles touchdown chant."""
    task.unique(PAINT_TASK)
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
