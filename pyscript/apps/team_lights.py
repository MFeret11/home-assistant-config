# ==============================================================================
# PYSCRIPT APP: TEAM LIGHTS
# ==============================================================================
# Paints your lights in your team's color while its game is live and celebrates
# when it scores, for any team tracked by the Team Tracker integration (ESPN).
#
# Everything personal lives in YAML under `pyscript: apps: team_lights:` (this
# house keeps it in packages/sports.yaml). See docs/team-lights.md for every
# option and a minimal example.
#
# How it decides what to do:
#   - Featured team: when several teams play at once, one team owns the lights.
#     Playoff games come first, then the order of `teams`. An optional
#     input_select (`featured_select`) overrides that while the picked team is live.
#   - Kickoff: recolors lights that are already on, only while `only_when`
#     conditions hold. It never turns lights on or changes modes.
#   - Scores: celebrate per sport (SPORT_RULES below). Lights turned off by hand
#     stay off. Celebrations pulse brightness only; the color never changes
#     mid-flash, so Zigbee meshes keep up.
#
# Other code reads the featured team from `pyscript.team_lights_featured`:
# state = team name, attributes = sensor, rgb, light_colors, sport, live.
# ==============================================================================

FEATURED_ENTITY = "pyscript.team_lights_featured"
AUTO = "Auto"

CFG = pyscript.app_config or {}
TEAMS = []
for _i, _t in enumerate(CFG.get("teams", [])):
    _team = dict(_t)
    _team["index"] = _i
    _team.setdefault("name", _team["sensor"])
    TEAMS.append(_team)

LIGHTS = list(CFG.get("lights", []))
LIGHTS_IF_ON = list(CFG.get("lights_if_on", []))
ENABLED_ENTITY = CFG.get("enabled_entity")
FEATURED_SELECT = CFG.get("featured_select")
ONLY_WHEN = dict(CFG.get("only_when") or {})
DIM_FLOOR_PCT = int(CFG.get("dim_floor_pct", 15))
FALLBACK_RGB = [255, 255, 255]

# Last color seen from ESPN per sensor. Team Tracker reports gray placeholder
# colors before a game, so a team without a `color` keeps its last real one.
_espn_colors = {}


# ------------------------------------------------------------------------------
# CELEBRATION RULES
# ------------------------------------------------------------------------------
def _celebration(sport, delta, last_play=None):
    """Which celebration a score earns: "big", "small" or None (no flash).
    Team Tracker polls every 5 s, so one change can hold more than one score."""
    play = (last_play or "").lower()
    if sport == "football":
        # Touchdown big; field goal, extra point, safety small.
        return "big" if delta >= 6 else "small"
    if sport == "basketball":
        # Only threes, or every basket would strobe the room. A jump of 3 is
        # almost always a three; a bigger jump counts only if ESPN says so.
        if delta == 3:
            return "small"
        if delta > 3 and "three point" in play and "makes" in play:
            return "small"
        return None
    if sport == "hockey" or sport == "soccer":
        return "big"
    if sport == "baseball":
        return "big" if ("homer" in play or "home run" in play) else "small"
    return "small"


# ------------------------------------------------------------------------------
# COLOR
# ------------------------------------------------------------------------------
def _hex_to_rgb(value):
    try:
        h = str(value).lstrip("#")
        return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)]
    except (ValueError, IndexError):
        return None


def vivid_color(hex_colors):
    """The most saturated of ESPN's team colors, scaled to full brightness.
    Skips black, white and grays, which look like plain white or off on a bulb."""
    best, best_sat = None, 0.25
    for value in hex_colors or []:
        rgb = _hex_to_rgb(value)
        if not rgb:
            continue
        hi, lo = max(rgb), min(rgb)
        if hi < 40:
            continue
        sat = (hi - lo) / hi
        if sat > best_sat:
            best, best_sat = [round(c * 255 / hi) for c in rgb], sat
    return best


def team_rgb(team):
    """Configured color ([r, g, b] or "#rrggbb"), else the team's ESPN color, else white."""
    color = team.get("color")
    if isinstance(color, str):
        color = _hex_to_rgb(color)
    if color:
        return list(color)
    sensor = team["sensor"]
    rgb = vivid_color(_attr(sensor, "team_colors"))
    if rgb:
        _espn_colors[sensor] = rgb
    return rgb or _espn_colors.get(sensor) or FALLBACK_RGB


# ------------------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------------------
def _state(entity_id):
    try:
        return state.get(entity_id)
    except Exception:
        return None


def _attr(entity_id, name):
    try:
        return (state.getattr(entity_id) or {}).get(name)
    except Exception:
        return None


def _enabled():
    return not ENABLED_ENTITY or _state(ENABLED_ENTITY) == "on"


def _conditions_met(team):
    """`only_when` (the team's own, else the top-level one): every listed entity must
    be in the given state (or one of a list)."""
    conditions = team["only_when"] if "only_when" in team else ONLY_WHEN
    for entity_id, wanted in (conditions or {}).items():
        allowed = wanted if isinstance(wanted, list) else [wanted]
        if _state(entity_id) not in [str(a) for a in allowed]:
            return False
    return True


def _lights_on():
    return any(_state(e) == "on" for e in LIGHTS)


def _live(team):
    return _state(team["sensor"]) == "IN"


def _team_by_name(name):
    for team in TEAMS:
        if team["name"] == name:
            return team
    return None


# ------------------------------------------------------------------------------
# FEATURED TEAM
# ------------------------------------------------------------------------------
def _season_rank(team):
    season = str(_attr(team["sensor"], "season") or "")
    if "post" in season:
        return 0
    if "pre" in season:
        return 2
    return 1


def pick_featured():
    """Manual pick while it's live; else playoffs first, then config order; with no
    game live, the manual pick or the first team (so the TV's sports mode has a color)."""
    if not TEAMS:
        return None
    picked = _team_by_name(_state(FEATURED_SELECT)) if FEATURED_SELECT else None
    if picked and _live(picked):
        return picked
    live = [t for t in TEAMS if _live(t)]
    if live:
        return sorted(live, key=lambda t: (_season_rank(t), t["index"]))[0]
    return picked or TEAMS[0]


def publish_featured():
    """Writes the featured team to FEATURED_ENTITY (only when something changed).
    Returns (team, changed)."""
    team = pick_featured()
    if team is None:
        return None, False
    attrs = {
        "friendly_name": "Featured team",
        "icon": "mdi:scoreboard",
        "sensor": team["sensor"],
        "rgb": team_rgb(team),
        "light_colors": dict(team.get("light_colors") or {}),
        "sport": _attr(team["sensor"], "sport"),
        "live": _live(team),
    }
    old_state = _state(FEATURED_ENTITY)
    old = {k: _attr(FEATURED_ENTITY, k) for k in attrs}
    changed = old_state != team["name"] or old != attrs
    if changed:
        state.set(FEATURED_ENTITY, value=team["name"], new_attributes=attrs)
    return team, changed and old_state != team["name"]


# ------------------------------------------------------------------------------
# LIGHT OUTPUT
# ------------------------------------------------------------------------------
def paint(team, brightness_pct, transition):
    """Team color on `lights_if_on` that are lit, then on `lights`.
    A light listed in the team's `light_colors` gets those settings instead of the RGB."""
    rgb = team_rgb(team)
    overrides = team.get("light_colors") or {}
    for entity_id in LIGHTS_IF_ON:
        if _state(entity_id) == "on":
            _light_on(entity_id, overrides.get(entity_id), rgb, brightness_pct, transition)
    for entity_id in LIGHTS:
        _light_on(entity_id, overrides.get(entity_id), rgb, brightness_pct, transition)


def _light_on(entity_id, override, rgb, brightness_pct, transition):
    color = dict(override) if override else {"rgb_color": rgb}
    light.turn_on(entity_id=entity_id, brightness_pct=brightness_pct, transition=transition, **color)


def celebrate(team, kind):
    """Brightness-only pulses in solid team color, ending at 100%.
    big: six stadium surges, a breath, then a two-beat finish. small: three pulses."""
    task.unique("team_lights_celebration")
    if kind == "big":
        for _ in range(6):
            paint(team, 100, 0)
            task.sleep(0.65)
            paint(team, DIM_FLOOR_PCT, 0)
            task.sleep(0.45)
        task.sleep(0.55)
        paint(team, 100, 0)
        task.sleep(0.55)
        paint(team, DIM_FLOOR_PCT, 0)
        task.sleep(0.35)
        paint(team, 100, 0)
        task.sleep(0.85)
    else:
        for _ in range(3):
            paint(team, 100, 0)
            task.sleep(0.55)
            paint(team, DIM_FLOOR_PCT, 0)
            task.sleep(0.40)
    task.sleep(0.35)
    paint(team, 100, 2)


# ------------------------------------------------------------------------------
# EVENT HANDLERS (plain functions; the triggers below call them)
# ------------------------------------------------------------------------------
def on_game_state(team, value, old_value):
    """Kickoff, final, and any featured-team change that comes with them."""
    if value == "IN" and old_value != "IN":
        featured, _ = publish_featured()
        if featured is team and _enabled() and _conditions_met(team) and _lights_on():
            paint(team, 100, 2)
        return
    _refresh_featured()


def on_score(team, value, old_value):
    """Celebrates a score by the featured team."""
    if not _live(team) or not _enabled() or team.get("celebrate") is False:
        return
    if _state(FEATURED_ENTITY) != team["name"]:
        return
    if not _conditions_met(team):
        return
    try:
        delta = int(value) - int(old_value)
    except (ValueError, TypeError):
        return
    if delta <= 0:
        return
    kind = _celebration(_attr(team["sensor"], "sport"), delta, _attr(team["sensor"], "last_play"))
    # Lights turned off by hand stay off, even for a score.
    if kind is None or not _lights_on():
        return
    celebrate(team, kind)


def _refresh_featured():
    """Republish; if a different live team now owns the lights, recolor them."""
    team, switched = publish_featured()
    if (switched and team and _live(team) and _enabled()
            and _conditions_met(team) and _lights_on()):
        paint(team, 100, 2)


# ------------------------------------------------------------------------------
# TRIGGERS (built from config; pyscript keeps a closure's triggers while it's referenced)
# ------------------------------------------------------------------------------
_triggers = []


def _make_team_triggers(team):
    sensor = team["sensor"]

    @state_trigger(sensor)
    def _game_state(value=None, old_value=None):
        on_game_state(team, value, old_value)

    @state_trigger(f"{sensor}.team_score")
    def _score(value=None, old_value=None):
        on_score(team, value, old_value)

    return [_game_state, _score]


for _team in TEAMS:
    _triggers.extend(_make_team_triggers(_team))

if FEATURED_SELECT:
    @state_trigger(FEATURED_SELECT)
    def _featured_select_changed():
        _refresh_featured()


@time_trigger("startup")
def _team_lights_startup():
    publish_featured()


@service
def team_lights_celebrate(kind="big"):
    """Plays a celebration in the featured team's color (for a dashboard button)."""
    team = _team_by_name(_state(FEATURED_ENTITY)) or pick_featured()
    if team:
        celebrate(team, kind if kind in ("big", "small") else "big")
