# ==============================================================================
# BASEMENT PALETTES: the color themes on the basement dashboard
# ==============================================================================
# basement.py paints these; this file only holds the colors and turns a palette
# into a list of (light, settings) to send. Saving this file reloads basement.py,
# so edit it with the theater idle.
#
# Adding a palette: add an entry to PALETTES below. The dashboard's theme library
# lists, searches and colors it from this table; nothing else needs changing.
#
# Each palette has a name, a library group (moods or holidays) and an mdi icon.
# A palette is one of two shapes:
#   "zones":   four colors, one per ROOM_ZONES group (bar, then three lounge groups).
#   "pattern": colors repeated bulb by bulb along ROOM_BULBS, e.g. red, green, red...
# Either shape has "stairs": one color for all three stair bulbs, or a list of
# three, one per bulb in STAIR_BULBS order.
#
# Colors are written with hs() (hue 0-360, saturation 0-100) or white() (Kelvin),
# each with a brightness in percent. The stair bulbs only do 2700-6500 K white.
# ==============================================================================
import colorsys

try:
    pyscript_compile
except NameError:  # plain Python (tests)
    def pyscript_compile(func):
        return func

STAIRLIGHTS = "light.stairlights"

# The four groups the "zones" palettes paint, in order.
ROOM_ZONES = [
    "light.zigbee_bar_lights",       # 1. North (Bar)
    "light.zigbee_lounge_lights_1",  # 2. Central Hub (Lounge Front / Stair Landing)
    "light.zigbee_lounge_lights_2",  # 3. Theater Flank (Lounge Mid)
    "light.zigbee_lounge_lights_3",  # 4. South (Lounge Rear)
]

# The nine room bulbs, in the order "pattern" palettes walk them. Reorder this list
# if neighbouring bulbs end up the same color.
BAR_BULBS = ["light.bar_light_1", "light.bar_light_2"]
ROOM_BULBS = BAR_BULBS + [
    "light.lounge_light_1",
    "light.lounge_light_2",
    "light.lounge_light_3",
    "light.lounge_light_4",
    "light.lounge_light_5",
    "light.lounge_light_6",
    "light.lounge_light_7",
]

STAIR_BULBS = ["light.stairlight_1", "light.stairlight_2", "light.stairlight_3"]

# Stair brightness when they show a palette color.
STAIR_COLOR_PCT = 40
STAIR_WHITE_PCT = 35

# Theme library filters on the dashboard. "mine" = themes saved or edited from the
# dashboard (kept in /config/basement_themes.json, see basement.py).
GROUP_MOODS = "moods"
GROUP_HOLIDAYS = "holidays"
GROUP_MINE = "mine"
TAB_ALL = "all"
LIBRARY_TABS = [TAB_ALL, GROUP_MOODS, GROUP_HOLIDAYS, GROUP_MINE]

# Ids of themes made on the dashboard: my_1, my_2...
MY_THEME_PREFIX = "my_"
MY_THEME_ICON = "mdi:bookmark"


def hs(hue, sat, pct):
    """A color: hue 0-360, saturation 0-100, brightness in percent."""
    return {"hs_color": [hue, sat], "brightness_pct": pct}


def white(kelvin, pct):
    """A white: color temperature in Kelvin, brightness in percent."""
    return {"color_temp_kelvin": kelvin, "brightness_pct": pct}


def stair_hs(hue, sat):
    return hs(hue, sat, STAIR_COLOR_PCT)


def stair_white(kelvin):
    return white(kelvin, STAIR_WHITE_PCT)


# Holiday colors used more than once. Untuned by eye on the real bulbs.
RED = hs(0, 100, 80)
GREEN = hs(120, 100, 80)
WARM_WHITE = white(2700, 60)
COOL_WHITE = white(5000, 70)
BLUE = hs(235, 100, 80)

PALETTES = {
    # --- Moods ---------------------------------------------------------------
    "speakeasy": {
        "name": "Speakeasy", "group": GROUP_MOODS, "icon": "mdi:glass-cocktail",
        "zones": [white(2000, 25), white(2200, 15), white(2400, 10), white(2300, 25)],
        "stairs": stair_white(2200),
    },
    "synthwave": {
        "name": "Synthwave", "group": GROUP_MOODS, "icon": "mdi:sine-wave",
        "zones": [hs(35, 95, 70), hs(300, 95, 55), hs(185, 95, 35), hs(320, 95, 25)],
        "stairs": stair_hs(300, 95),
    },
    # --- Holidays: bulb-by-bulb patterns -----------------------------------------
    "christmas": {
        "name": "Christmas", "group": GROUP_HOLIDAYS, "icon": "mdi:pine-tree",
        "pattern": [RED, GREEN],
        "stairs": [stair_hs(0, 100), stair_hs(120, 100), stair_hs(0, 100)],
    },
    "halloween": {
        "name": "Halloween", "group": GROUP_HOLIDAYS, "icon": "mdi:halloween",
        "pattern": [hs(25, 100, 80), hs(275, 95, 60)],
        "stairs": [stair_hs(25, 100), stair_hs(275, 95), stair_hs(25, 100)],
    },
    "fourth_of_july": {
        "name": "4th of July", "group": GROUP_HOLIDAYS, "icon": "mdi:firework",
        "pattern": [RED, COOL_WHITE, BLUE],
        "stairs": [stair_hs(0, 100), stair_white(5000), stair_hs(235, 100)],
    },
    "thanksgiving": {
        "name": "Thanksgiving", "group": GROUP_HOLIDAYS, "icon": "mdi:food-turkey",
        "pattern": [hs(32, 95, 60), hs(18, 95, 45), hs(45, 85, 55)],
        "stairs": stair_hs(32, 95),
    },
    "new_years": {
        "name": "New Year's", "group": GROUP_HOLIDAYS, "icon": "mdi:glass-wine",
        "pattern": [hs(42, 85, 70), COOL_WHITE],
        "stairs": [stair_hs(42, 85), stair_white(5000), stair_hs(42, 85)],
    },
    "valentines": {
        "name": "Valentine's", "group": GROUP_HOLIDAYS, "icon": "mdi:heart",
        "pattern": [hs(350, 100, 70), hs(330, 55, 55)],
        "stairs": stair_hs(330, 55),
    },
    "st_patricks": {
        "name": "St. Patrick's", "group": GROUP_HOLIDAYS, "icon": "mdi:clover",
        "pattern": [GREEN, hs(95, 75, 60)],
        "stairs": stair_hs(120, 100),
    },
    "easter": {
        "name": "Easter", "group": GROUP_HOLIDAYS, "icon": "mdi:egg-easter",
        "pattern": [hs(330, 35, 55), hs(270, 35, 55), hs(150, 35, 55), hs(55, 40, 55)],
        "stairs": stair_hs(270, 35),
    },
}


# ------------------------------------------------------------------------------
# TURNING A PALETTE INTO LIGHT COMMANDS
# A saved preset (from the dashboard) has "bulbs" (room bulb -> settings) and
# "stair_bulbs" (stair bulb -> settings) instead of zones/pattern/stairs.
# Settings may be {"off": True} for a bulb that was off when it was saved.
# ------------------------------------------------------------------------------
def room_plan(palette):
    """[(light, settings)] for the room."""
    if "zones" in palette:
        return list(zip(ROOM_ZONES, palette["zones"]))
    if "pattern" in palette:
        pattern = palette["pattern"]
        return [(bulb, pattern[i % len(pattern)]) for i, bulb in enumerate(ROOM_BULBS)]
    if "bulbs" in palette:
        saved = palette["bulbs"]
        return [(b, saved[b]) for b in ROOM_BULBS if b in saved]
    return []


def stair_plan(palette):
    """[(light, settings)] for the stairs: the whole group for one color, each bulb
    for a list. Empty if the palette has no stair color."""
    if "stair_bulbs" in palette:
        saved = palette["stair_bulbs"]
        return [(b, saved[b]) for b in STAIR_BULBS if b in saved]
    stairs = palette.get("stairs")
    if isinstance(stairs, list):
        return list(zip(STAIR_BULBS, stairs))
    if stairs:
        return [(STAIRLIGHTS, stairs)]
    return []


# ------------------------------------------------------------------------------
# SAVING THE LIGHTS AS THEY ARE NOW
# ------------------------------------------------------------------------------
def settings_from_state(light_state, attrs):
    """The settings that put a bulb back the way it is now, from its HA state and
    attributes. None if it isn't reporting (unavailable)."""
    if light_state == "off":
        return {"off": True}
    if light_state != "on":
        return None
    attrs = attrs or {}
    brightness = attrs.get("brightness") or 255
    pct = max(1, round(brightness * 100 / 255))
    if attrs.get("color_mode") == "color_temp" and attrs.get("color_temp_kelvin"):
        return white(int(attrs["color_temp_kelvin"]), pct)
    if attrs.get("hs_color"):
        hue, sat = attrs["hs_color"]
        return hs(round(hue, 1), round(sat, 1), pct)
    if attrs.get("color_temp_kelvin"):
        return white(int(attrs["color_temp_kelvin"]), pct)
    return {"brightness_pct": pct}


# ------------------------------------------------------------------------------
# SWATCHES: the colors the dashboard pill shows ("r, g, b" strings, up to four)
# ------------------------------------------------------------------------------
def _kelvin_to_rgb(kelvin):
    """Rough RGB for a white, close enough for a dashboard swatch."""
    k = kelvin / 100.0
    if k <= 66:
        r = 255
        g = 99.47 * _ln(k) - 161.12
        b = 0 if k <= 19 else 138.52 * _ln(k - 10) - 305.04
    else:
        r = 329.70 * ((k - 60) ** -0.1332)
        g = 288.12 * ((k - 60) ** -0.0755)
        b = 255
    return [int(max(0, min(255, c))) for c in (r, g, b)]


def _ln(x):
    import math
    return math.log(x)


def settings_rgb(settings):
    """'r, g, b' for one color setting, or None for an off bulb."""
    if not settings or settings.get("off"):
        return None
    if "hs_color" in settings:
        hue, sat = settings["hs_color"]
        r, g, b = colorsys.hsv_to_rgb(hue / 360.0, sat / 100.0, 1.0)
        rgb = [int(r * 255), int(g * 255), int(b * 255)]
    elif "color_temp_kelvin" in settings:
        rgb = _kelvin_to_rgb(settings["color_temp_kelvin"])
    else:
        rgb = [255, 193, 7]
    return ", ".join([str(c) for c in rgb])


def swatch(palette, limit=4):
    """The distinct room colors of a palette, in order, for the dashboard pill."""
    colors = []
    for _, settings in room_plan(palette):
        rgb = settings_rgb(settings)
        if rgb and rgb not in colors:
            colors.append(rgb)
    if not colors:
        for _, settings in stair_plan(palette):
            rgb = settings_rgb(settings)
            if rgb and rgb not in colors:
                colors.append(rgb)
    return colors[:limit] or ["255, 255, 255"]


# ------------------------------------------------------------------------------
# THE THEME LIBRARY: built-in palettes plus the ones made on the dashboard
# `custom` is {theme id: theme} from basement_themes.json. A custom theme under a
# built-in id is an edited copy of that built-in ("Reset to original" removes it);
# under a my_N id it is a theme of our own. Custom themes hold "bulbs" and
# "stair_bulbs" (see room_plan), plus name, icon and swatch.
# ------------------------------------------------------------------------------
def library_entries(custom):
    """Every theme for the library, built-ins first (table order), then ours by name.
    Each is {id, name, icon, group, swatch, edited}."""
    custom = custom or {}
    entries = []
    for pid, pal in PALETTES.items():
        mine = custom.get(pid)
        entries.append({
            "id": pid,
            "name": (mine or {}).get("name") or pal["name"],
            "icon": pal.get("icon", "mdi:palette"),
            "group": pal["group"],
            "swatch": (mine or {}).get("swatch") or swatch(pal),
            "edited": bool(mine),
        })
    own = sorted([((t.get("name") or "").lower(), tid) for tid, t in custom.items() if tid not in PALETTES])
    for _, tid in own:
        theme = custom[tid]
        entries.append({
            "id": tid,
            "name": theme.get("name") or tid,
            "icon": theme.get("icon") or MY_THEME_ICON,
            "group": GROUP_MINE,
            "swatch": theme.get("swatch") or swatch(theme),
            "edited": False,
        })
    return entries


def filter_entries(entries, tab, query):
    """The entries for a library tab and search text (any part of the name, any case).
    "mine" shows our own themes and edited built-ins."""
    query = (query or "").strip().lower()
    found = []
    for entry in entries:
        if tab == GROUP_MINE and not (entry["group"] == GROUP_MINE or entry["edited"]):
            continue
        if tab in (GROUP_MOODS, GROUP_HOLIDAYS) and entry["group"] != tab:
            continue
        if query and query not in entry["name"].lower():
            continue
        found.append(entry)
    return found


def new_theme_id(custom):
    """The first unused my_N id."""
    n = 1
    while f"{MY_THEME_PREFIX}{n}" in (custom or {}):
        n += 1
    return f"{MY_THEME_PREFIX}{n}"


# ------------------------------------------------------------------------------
# THE THEMES FILE (blocking file I/O: basement.py runs these with task.executor)
# ------------------------------------------------------------------------------
@pyscript_compile
def read_themes_file(path):
    """{theme id: theme} from the JSON file, or {} if it doesn't exist yet."""
    import json
    import os
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


@pyscript_compile
def write_themes_file(path, themes):
    """Write the themes atomically (temp file, then rename), readable by hand."""
    import json
    import os
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(themes, f, indent=2, sort_keys=True)
    os.replace(tmp, path)
