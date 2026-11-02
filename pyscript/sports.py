# ==============================================================================
# PYSCRIPT MODULE: SPORTS & GAME-DAY REACTION ENGINE
# ==============================================================================

# ------------------------------------------------------------------------------
# CORE ENTITIES & CONSTANTS
# ------------------------------------------------------------------------------
EAGLES_SENSOR = "sensor.philadelphia_eagles"
AUTOMATION_ALLOWED = "binary_sensor.basement_automation_allowed"
ADAPTIVE_SWITCH = "switch.basement_adaptive_lighting_adaptive_lighting_basement_adaptive_lighting"
LIGHTING_MODE_SELECT = "input_select.basement_lighting_mode"
SOCIAL_SOURCE = "pyscript.basement_social_source"

MASTER_ZIGBEE_GROUP = "light.zigbee_basement_lights"
STAIRLIGHTS = "light.stairlights"
FLASH_TARGETS = [MASTER_ZIGBEE_GROUP, STAIRLIGHTS]

EAGLES_KELLY_GREEN = [0, 170, 35]  # Authentic Philadelphia Eagles Kelly Green (calibrated for RGB LEDs)
# The stair bulbs are hue/saturation only and their green LED is bluer than the
# lounge/bar bulbs, so they can't reach true Kelly green at any hue. 125° looked
# closest by eye (2026-11-01). Raise hue = bluer, lower = yellower.
STAIR_TEAM_HS = [125, 100]

# Dim floor for strobe/chant steps. 15% ensures bulbs stay smoothly
# calibrated without hitting low-end PWM flicker or mesh packet lag.
DIM_FLOOR_PCT = 15


def is_automation_allowed() -> bool:
    """Master safety switch check for basement lighting automations."""
    return state.get(AUTOMATION_ALLOWED) == "on"


@service
def get_team_rgb() -> list:
    """Returns vibrant authentic Philadelphia Eagles Kelly Green."""
    return EAGLES_KELLY_GREEN


@service
def get_stair_team_hs() -> list:
    """Team green for the stair bulbs, tuned to match the main basement bulbs."""
    return STAIR_TEAM_HS


def _team_on(rgb, brightness_pct, transition):
    """Team color on the main group, and on the stairs (own tuned hue) only while they're
    lit: on game day basement.py runs them as a motion path light. Group last."""
    if state.get(STAIRLIGHTS) == "on":
        light.turn_on(entity_id=STAIRLIGHTS, hs_color=STAIR_TEAM_HS, brightness_pct=brightness_pct, transition=transition)
    light.turn_on(entity_id=MASTER_ZIGBEE_GROUP, rgb_color=rgb, brightness_pct=brightness_pct, transition=transition)


def _pulse(rgb, reps, high_pct, low_pct, high_hold, low_hold):
    """Shared strobe primitive: steps brightness high<->low, never OFF."""
    for _ in range(reps):
        _team_on(rgb, high_pct, 0)
        task.sleep(high_hold)
        _team_on(rgb, low_pct, 0)
        task.sleep(low_hold)


def _eagles_chant_cadence(rgb):
    """
    Zigbee-safe Philadelphia Eagles Touchdown Chant Cadence:
    Rhythmic, stadium-pace green power surges calibrated for 3rd Reality Zigbee bulbs.
    Prevents mesh congestion, dropped packets, and out-of-sync flashing:
    1. E - A - G - L - E - S: 6 deliberate, synchronized stadium surges (100% hold 0.65s <-> 15% hold 0.45s).
    2. Anticipation: 0.55s breath at dim floor before climax.
    3. Climax 'EA - GLES!':
       - 'EA-': Surge up to 100% (hold 0.55s), dip to 15% (hold 0.35s).
       - '-GLES!': Grand explosive surge at 100% (hold 0.85s).
    4. Settles cleanly holding solid Kelly Green at 100%.
    """
    for _ in range(6):
        _team_on(rgb, 100, 0)
        task.sleep(0.65)
        _team_on(rgb, DIM_FLOOR_PCT, 0)
        task.sleep(0.45)

    task.sleep(0.55)

    # Syllable 1: 'EA-'
    _team_on(rgb, 100, 0)
    task.sleep(0.55)
    _team_on(rgb, DIM_FLOOR_PCT, 0)
    task.sleep(0.35)

    # Syllable 2: '-GLES!'
    _team_on(rgb, 100, 0)
    task.sleep(0.85)


# ------------------------------------------------------------------------------
# 1. EAGLES GAME STATE CONTROLLER (Kickoff vs. Game Over)
# ------------------------------------------------------------------------------
@state_trigger("sensor.philadelphia_eagles == 'IN'")
def eagles_game_started():
    """Sets basement into Game Day mode when game goes live."""
    if not is_automation_allowed():
        return

    if state.get(LIGHTING_MODE_SELECT) != "Social Mode":
        state.set(SOCIAL_SOURCE, value="sports")
        input_select.select_option(entity_id=LIGHTING_MODE_SELECT, option="Social Mode")
    switch.turn_off(entity_id=ADAPTIVE_SWITCH)

    _team_on(get_team_rgb(), 100, 2)
    # Stairs green too; basement.py times them out (5 min) and relights them on motion.
    pyscript.basement_sports_stairs_on()


@state_trigger("sensor.philadelphia_eagles == 'POST'")
def eagles_game_over(old_value=None):
    """Restores normal lighting when the game concludes."""
    if old_value not in ["IN", "unavailable", "unknown"]:
        return
    if not is_automation_allowed():
        return

    pyscript.mood_reset_normal()


# ------------------------------------------------------------------------------
# 2. HIGH-PERFORMANCE SCORE / TOUCHDOWN FLASH ENGINE
# ------------------------------------------------------------------------------
@state_trigger("sensor.philadelphia_eagles.team_score")
def eagles_score_flash(value=None, old_value=None):
    """Reacts dynamically to score changes (Touchdown Chant vs. Field Goal Strobe)."""
    if state.get(EAGLES_SENSOR) != "IN" or not is_automation_allowed():
        return

    try:
        delta = int(value) - int(old_value)
        if delta <= 0:
            return
    except (ValueError, TypeError):
        return

    # Lights turned off by hand stay off, even for a score.
    if state.get(MASTER_ZIGBEE_GROUP) != "on":
        return

    task.unique("eagles_flash_engine")
    rgb = get_team_rgb()

    # TOUCHDOWN (6+ points) -> authentic Eagles stadium chant cadence
    if delta >= 6:
        _eagles_chant_cadence(rgb)
    # FIELD GOAL OR CONVERSION (< 6 points) -> rhythmic green pulse
    else:
        _pulse(rgb, reps=3, high_pct=100, low_pct=DIM_FLOOR_PCT, high_hold=0.55, low_hold=0.40)

    # Both paths end the same way: settle back on solid game-day green.
    # No snapshot/scene restore, no ambient-palette handoff — the game
    # is still live, so team green is the correct persistent state.
    task.sleep(0.35)
    _team_on(rgb, 100, 2)
