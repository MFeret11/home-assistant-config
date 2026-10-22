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
SNAPSHOT_SCENE_ID = "eagles_flash_before_snapshot"

EAGLES_KELLY_GREEN = [0, 170, 35]  # Authentic Philadelphia Eagles Kelly Green (calibrated for RGB LEDs)
DEFAULT_EAGLES_RGB = EAGLES_KELLY_GREEN

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


def _pulse(rgb, reps, high_pct, low_pct, high_hold, low_hold):
    """Shared strobe primitive: steps brightness high<->low, never OFF."""
    for _ in range(reps):
        light.turn_on(entity_id=FLASH_TARGETS, rgb_color=rgb, brightness_pct=high_pct, transition=0)
        task.sleep(high_hold)
        light.turn_on(entity_id=FLASH_TARGETS, rgb_color=rgb, brightness_pct=low_pct, transition=0)
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
        light.turn_on(entity_id=FLASH_TARGETS, rgb_color=rgb, brightness_pct=100, transition=0)
        task.sleep(0.65)
        light.turn_on(entity_id=FLASH_TARGETS, rgb_color=rgb, brightness_pct=DIM_FLOOR_PCT, transition=0)
        task.sleep(0.45)

    task.sleep(0.55)

    # Syllable 1: 'EA-'
    light.turn_on(entity_id=FLASH_TARGETS, rgb_color=rgb, brightness_pct=100, transition=0)
    task.sleep(0.55)
    light.turn_on(entity_id=FLASH_TARGETS, rgb_color=rgb, brightness_pct=DIM_FLOOR_PCT, transition=0)
    task.sleep(0.35)

    # Syllable 2: '-GLES!'
    light.turn_on(entity_id=FLASH_TARGETS, rgb_color=rgb, brightness_pct=100, transition=0)
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

    light.turn_on(
        entity_id=FLASH_TARGETS,
        rgb_color=get_team_rgb(),
        brightness_pct=100,
        transition=2,
    )


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
    light.turn_on(entity_id=FLASH_TARGETS, rgb_color=rgb, brightness_pct=100, transition=2)
