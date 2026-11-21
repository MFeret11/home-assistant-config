# ==============================================================================
# PYSCRIPT MODULE: SHARED THEATER & BASEMENT ENTITY IDS
# ==============================================================================
# Entity IDs and mode names used by more than one pyscript file, kept in one
# place so a renamed device only needs one edit. theater.py and basement.py
# import from here.
#
# interlocks.py keeps its own copies on purpose: pyscript reloads every file
# that imports a module when the module is saved, and a reload of interlocks.py
# would kill a running projector cooldown. tests/test_shared_entities.py fails
# if those copies drift from this file.
#
# Saving this file reloads theater.py and basement.py, so edit it with the
# theater idle. Check docs/entities.md before adding or renaming an ID.
# ==============================================================================

# Theater state
THEATER_MODE = "sensor.theater_mode"
THEATER_IN_USE = "binary_sensor.theater_in_use"
THEATER_BOXART = "sensor.theater_current_boxart"
CURTAIN_CALL = "pyscript.curtain_call_active"

# Basement lighting modes
LIGHTING_MODE_SELECT = "input_select.basement_lighting_mode"
MODE_DAILY = "Daily Driver"
MODE_SOCIAL = "Social Mode"
# Adaptive Lighting switch for the basement (circadian brightness and color).
ADAPTIVE_SWITCH = "switch.basement_adaptive_lighting_adaptive_lighting_basement_adaptive_lighting"
# Who engaged Social Mode: "manual" (user) or "sports" (game day). Only sports-engaged
# Social drops back to Daily when the theater switches to a movie or game.
SOCIAL_SOURCE = "pyscript.basement_social_source"
# Featured team, published by the Team Lights app (apps/team_lights.py). State is the
# team name; attributes include rgb, light_colors and `sensor` (the Team Tracker sensor).
FEATURED_TEAM = "pyscript.team_lights_featured"

# Onn streamer. media_player.onn_pro's app_id is the source of truth for the
# foreground app; the ADB player reports playing/paused.
ONN_PRO = "media_player.onn_pro"
ONN_ADB = "media_player.theater_onn_pro_adb"
ONN_REMOTE = "remote.onn_pro"

# Audio
RECEIVER = "media_player.theater_receiver"
RECEIVER_ZONE_2 = "media_player.theater_receiver_zone_2"
SPOTIFY_PLAYER = "media_player.whole_house_spotify"

# Projector and Batocera power (the interlocks themselves live in interlocks.py)
PROJECTOR_SWITCH = "switch.projector"
PROJECTOR_CURRENT = "sensor.projector_current"
BATOCERA_SWITCH = "switch.batocera"
BATOCERA_CURRENT = "sensor.batocera_current"
BATOCERA_STATE = "sensor.batocera_state"

# Gaming PC. Pre-filtered by the "Gaming PC Active Game" template
# (configuration.yaml): a game title, "Steam Big Picture" or "Idle / Desktop".
PC_ACTIVE_WINDOW = "sensor.gaming_pc_active_game"

# mmWave presence sensor (Sonoff SNZB-06P) covering the basement. Unlike the PIR at
# the foot of the stairs, it sees people sitting still. Its own clear delay is set
# on the device (number.theater_mmwave_sensor_presence_detection_timeout).
MMWAVE_PRESENCE = "binary_sensor.theater_mmwave_sensor"
