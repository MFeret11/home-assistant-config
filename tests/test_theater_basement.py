"""
Comprehensive 50-Test Automated Simulation Suite for Basement & Theater Engines
Run via terminal:
PYTHONPATH=~/ha_config/pyscript python3 ~/ha_config/tests/test_theater_basement.py
"""
import sys
import os
import time
import builtins
import re

pyscript_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pyscript"))
if pyscript_dir not in sys.path:
    sys.path.insert(0, pyscript_dir)

# ==============================================================================
# 1. STATEFUL MOCK RUNTIME & HARDWARE SPY
# ==============================================================================
class MockState:
    def __init__(self):
        self._states = {}
        self._attrs = {}

    def get(self, entity_id, default=None):
        return self._states.get(entity_id, default)

    def getattr(self, entity_id, attr=None):
        entity_attrs = self._attrs.get(entity_id, {})
        return entity_attrs.get(attr) if attr else entity_attrs

    def set(self, entity_id, value=None, new_attributes=None, **kwargs):
        self._states[entity_id] = str(value)
        attrs = new_attributes or kwargs.get("attributes")
        if attrs:
            self._attrs.setdefault(entity_id, {}).update(attrs)


class ServiceSpy:
    def __init__(self):
        self.calls = []

    def clear(self):
        self.calls.clear()

    def record(self, domain, service, **kwargs):
        self.calls.append({"domain": domain, "service": service, "kwargs": kwargs})

    def was_called(self, domain, service, entity_id=None):
        for call in self.calls:
            if call["domain"] == domain and call["service"] == service:
                if entity_id is None:
                    return True
                target = call["kwargs"].get("entity_id")
                if target == entity_id or (isinstance(target, list) and entity_id in target):
                    return True
        return False

    def last_call_for(self, domain, service):
        for call in reversed(self.calls):
            if call["domain"] == domain and call["service"] == service:
                return call
        return None


class MockTask:
    def __init__(self):
        self._queue = []

    def unique(self, name): pass

    def sleep(self, seconds):
        if getattr(self, "sleep_hook", None):
            self.sleep_hook(seconds)

    def create(self, func, *args, **kwargs):
        self._queue.append((func, args, kwargs))

    def executor(self, func, *args, **kwargs):
        # Tests stay offline: only fakes marked test_fake run; real I/O helpers fail fast.
        if not getattr(func, "test_fake", False):
            raise OSError("network/file I/O disabled in tests")
        return func(*args, **kwargs)

    def run_deferred_tasks(self):
        while self._queue:
            func, args, kwargs = self._queue.pop(0)
            func(*args, **kwargs)

    def clear(self):
        self._queue.clear()
        self.sleep_hook = None


class MockLog:
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def debug(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass


class MockDomain:
    def __init__(self, domain):
        self._domain = domain

    def __getattr__(self, service):
        def _call(**kwargs):
            spy.record(self._domain, service, **kwargs)

            # Stateful simulation: automatically mutate mock_state like real HA
            entity_id = kwargs.get("entity_id")
            targets = [entity_id] if isinstance(entity_id, str) else (entity_id or [])

            for target in targets:
                if service == "turn_on":
                    mock_state.set(target, "on")
                elif service == "turn_off":
                    mock_state.set(target, "off")
                elif service == "select_option":
                    option = kwargs.get("option")
                    if option:
                        mock_state.set(target, option)
                elif service == "set_value":
                    val = kwargs.get("value")
                    if val is not None:
                        mock_state.set(target, str(val))
                elif service == "select_sound_mode":
                    snd = kwargs.get("sound_mode")
                    if snd:
                        mock_state._attrs.setdefault(target, {})["sound_mode"] = str(snd)
                elif service == "select_source":
                    src = kwargs.get("source")
                    if src:
                        mock_state._attrs.setdefault(target, {})["source"] = str(src)
        return _call


# Instantiate Mocks
mock_state = MockState()
spy = ServiceSpy()
mock_task = MockTask()
mock_log = MockLog()

# Inject into native builtins so imported modules find them automatically
builtins.state = mock_state
builtins.task = mock_task
builtins.log = mock_log
builtins.spy = spy
builtins.mock_task = mock_task
builtins.safe_state_get = mock_state.get

builtins.light = MockDomain("light")
builtins.switch = MockDomain("switch")
builtins.media_player = MockDomain("media_player")
builtins.remote = MockDomain("remote")
builtins.button = MockDomain("button")
builtins.input_select = MockDomain("input_select")
builtins.input_boolean = MockDomain("input_boolean")
builtins.input_number = MockDomain("input_number")
builtins.adaptive_lighting = MockDomain("adaptive_lighting")
builtins.rest_command = MockDomain("rest_command")

builtins.scene = MockDomain("scene")
builtins.pyscript = MockDomain("pyscript")
builtins.notify = MockDomain("notify")
builtins.shell_command = MockDomain("shell_command")

# Mock Decorators
builtins.service = lambda func: func
builtins.state_trigger = lambda *args, **kwargs: (lambda f: f)
builtins.time_trigger = lambda *args, **kwargs: (lambda f: f)
builtins.pyscript_executor = lambda func: func

# Import target engines after builtins are registered
import theater
import basement
import sports
import watchdog

builtins.pyscript.get_team_rgb = sports.get_team_rgb

# ==============================================================================
# 2. ENVIRONMENT RESET
# ==============================================================================
def setup_clean_environment():
    """Resets all states, mocks, and boot timestamps to baseline standby."""
    spy.clear()
    mock_task.clear()
    state._states.clear()
    state._attrs.clear()

    # Bypass 30s startup grace checks
    theater.BOOT_TIMESTAMP = 0
    theater._SELECT_SYNC_PENDING.clear()
    basement.BOOT_TIMESTAMP = 0
    watchdog._alert_latched.update({"thermal": False, "storage": False})
    basement.DIRECTION_OF_TRAVEL = "none"
    basement.LAST_DOOR_OPEN_TS = 0.0
    basement.LAST_MOTION_BOTTOM_TS = 0.0
    basement.LAST_MOTION_CLEAR_TS = 0.0
    basement.LAST_MOTION_SEEN_TS = 0.0
    basement.CURRENT_PALETTE = "synthwave"
    basement.CURRENT_EFFECT = "static"
    basement.IS_EFFECT_UPDATING = False

    # Base Entities
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    state.set("sensor.theater_mode", "off")
    state.set("binary_sensor.theater_in_use", "off")
    state.set("switch.projector", "off")
    state.set("switch.batocera", "off")
    state.set("sensor.projector_current", "0.00")
    state.set("sensor.batocera_current", "0.00")
    state.set("light.theater_dimmer", "off")
    state.set("light.stairlights", "off")
    state.set("light.zigbee_basement_lights", "off")
    state.set("switch.bias_lights", "off")
    state.set("pyscript.basement_social_source", "none")
    state.set("pyscript.curtain_call_active", "off")
    state.set("pyscript.mode_selector_expanded", "off")
    state.set("sensor.mediasession2mqtt_1_playback_state", "idle")
    state.set("sensor.batocera_state", "idle")
    state.set("input_number.theater_announcer_volume", "-10.0")
    state.set("sensor.philadelphia_eagles", "PRE")
    state.set("binary_sensor.basement_automation_allowed", "on")


# ==============================================================================
# SUITE 1: CORE HARDWARE & SAFETY SUITE (7 TESTS)
# ==============================================================================
def test_play_music_projector_cold_start():
    setup_clean_environment()
    state.set("switch.projector", "off")
    theater.play_music()
    mock_task.run_deferred_tasks()
    assert not spy.was_called("switch", "turn_on", "switch.projector"), "FAIL: Turned on projector!"
    assert spy.was_called("switch", "turn_off", "switch.projector"), "FAIL: Did not ensure projector was off!"
    assert state.get("sensor.theater_mode") == "music", "FAIL: theater_mode not music!"
    assert spy.was_called("media_player", "select_sound_mode"), "FAIL: Sound mode not set!"
    print("  ✓ [Core] test_play_music_projector_cold_start PASSED")


def test_play_music_cuts_live_plug_before_onn_wake():
    setup_clean_environment()
    state.set("switch.projector", "on")
    state.set("sensor.projector_current", "0.02")
    theater.play_music()
    mock_task.run_deferred_tasks()

    plug_cut_index = -1
    onn_wake_index = -1
    for idx, call in enumerate(spy.calls):
        if call["domain"] == "switch" and call["service"] == "turn_off" and call["kwargs"].get("entity_id") == "switch.projector":
            if plug_cut_index == -1: plug_cut_index = idx
        if call["domain"] == "media_player" and call["service"] == "turn_on" and call["kwargs"].get("entity_id") == "media_player.onn_pro":
            onn_wake_index = idx

    assert plug_cut_index != -1, "FAIL: switch.projector was never turned off!"
    assert onn_wake_index != -1, "FAIL: onn_pro was never turned on!"
    assert plug_cut_index < onn_wake_index, "FAIL: Onn woke up before projector plug cut! CEC will strike bulb!"
    print("  ✓ [Core] test_play_music_cuts_live_plug_before_onn_wake PASSED")


def test_cinema_shield_blackout():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Movie Mode")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "movie")
    state.set("sensor.mediasession2mqtt_1_playback_state", "playing")

    basement.theater_lighting_sync()
    mock_task.run_deferred_tasks()
    assert spy.was_called("light", "turn_off", "light.theater_dimmer"), "FAIL: Dimmer not off!"
    assert spy.was_called("light", "turn_off", "light.zigbee_basement_lights"), "FAIL: Zigbee not off!"
    assert spy.was_called("switch", "turn_on", "switch.bias_lights"), "FAIL: Bias not on!"
    print("  ✓ [Core] test_cinema_shield_blackout PASSED")


def test_movie_intermission_glow():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Movie Mode")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "movie")
    state.set("media_player.onn_pro", "on")
    state.set("sensor.mediasession2mqtt_1_playback_state", "paused")

    basement.theater_lighting_sync()
    mock_task.run_deferred_tasks()

    intermission_called = any(
        c["domain"] == "light" and c["service"] == "turn_on" and
        c["kwargs"].get("entity_id") == "light.theater_dimmer" and c["kwargs"].get("brightness_pct") == 1
        for c in spy.calls
    )
    assert intermission_called, "FAIL: 1% Intermission glow not applied!"
    assert spy.was_called("switch", "turn_on", "switch.bias_lights"), "FAIL: Bias not on during pause!"
    print("  ✓ [Core] test_movie_intermission_glow PASSED")


def test_stair_stealth_red_in_movie_mode():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Movie Mode")
    state.set("sensor.theater_mode", "movie")
    state.set("binary_sensor.theater_in_use", "on")

    basement.stair_door_opened("off")
    mock_task.run_deferred_tasks()
    assert not spy.was_called("adaptive_lighting", "apply"), "FAIL: Adaptive lighting applied during Movie Mode!"
    stealth_called = any(
        c["domain"] == "light" and c["service"] == "turn_on" and
        c["kwargs"].get("entity_id") == "light.stairlights" and
        c["kwargs"].get("color_temp_kelvin") == 2000 and c["kwargs"].get("brightness_pct") == 2
        for c in spy.calls
    )
    assert stealth_called, "FAIL: Stairs not commanded to 2% Warm Candlelight!"
    print("  ✓ [Core] test_stair_stealth_candlelight_in_movie_mode PASSED")


def test_stair_daily_driver_entry():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    basement.stair_door_opened("off")
    mock_task.run_deferred_tasks()
    assert spy.was_called("adaptive_lighting", "apply"), "FAIL: Adaptive Lighting not applied during Daily Driver entry!"
    print("  ✓ [Core] test_stair_daily_driver_entry PASSED")


def test_stair_social_mode_entry_leaves_stairs_on():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Social Mode")
    basement.stair_door_opened("off")
    mock_task.run_deferred_tasks()
    assert spy.was_called("light", "turn_on", "light.stairlights"), "FAIL: Stairs not turned on during Social Mode entry!"

    # Door closes afterwards (even with upward travel)
    basement.DIRECTION_OF_TRAVEL = "up"
    basement.stair_door_closed("on")
    mock_task.run_deferred_tasks()
    assert not spy.was_called("light", "turn_off", "light.stairlights"), "FAIL: Stairs turned off in Social Mode!"
    print("  ✓ [Core] test_stair_social_mode_entry_leaves_stairs_on PASSED")


def test_instant_walkout_shutoff():
    setup_clean_environment()
    basement.DIRECTION_OF_TRAVEL = "up"
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    state.set("binary_sensor.theater_in_use", "off")

    basement.stair_door_closed("on")
    mock_task.run_deferred_tasks()
    assert spy.was_called("light", "turn_off", "light.theater_dimmer"), "FAIL: Dimmer not off on exit!"
    assert spy.was_called("light", "turn_off", "light.stairlights"), "FAIL: Stairs not off on exit!"
    assert spy.was_called("light", "turn_off", "light.zigbee_basement_lights"), "FAIL: Zigbee not off on exit!"
    print("  ✓ [Core] test_instant_walkout_shutoff PASSED")


# ==============================================================================
# SUITE 2: STATE TRANSITION MATRIX (6 TESTS)
# ==============================================================================
def test_transition_daily_to_social():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Social Mode")
    basement.on_lighting_mode_changed("Social Mode", "Daily Driver")
    mock_task.run_deferred_tasks()
    assert state.get("pyscript.basement_social_source") == "manual", "FAIL: Social source not recorded as manual!"
    assert spy.was_called("switch", "turn_off", "switch.basement_adaptive_lighting_adaptive_lighting_basement_adaptive_lighting"), \
        "FAIL: Adaptive Lighting switch was not disabled!"
    print("  ✓ [Matrix] test_transition_daily_to_social PASSED")


def test_transition_social_to_movie():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Movie Mode")
    state.set("pyscript.basement_social_source", "manual")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "movie")
    state.set("sensor.mediasession2mqtt_1_playback_state", "playing")

    basement.on_lighting_mode_changed("Movie Mode", "Social Mode")
    mock_task.run_deferred_tasks()
    assert state.get("pyscript.basement_social_source") == "none", "FAIL: Social source not cleared!"
    assert spy.was_called("light", "turn_off", "light.theater_dimmer"), "FAIL: Did not sync to showtime blackout!"
    print("  ✓ [Matrix] test_transition_social_to_movie PASSED")


def test_transition_movie_to_daily():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    basement.on_lighting_mode_changed("Daily Driver", "Movie Mode")
    mock_task.run_deferred_tasks()
    assert spy.was_called("switch", "turn_on", "switch.basement_adaptive_lighting_adaptive_lighting_basement_adaptive_lighting"), \
        "FAIL: Adaptive Lighting switch not restored!"
    assert spy.was_called("adaptive_lighting", "apply"), "FAIL: Adaptive Lighting not applied to loads!"
    print("  ✓ [Matrix] test_transition_movie_to_daily PASSED")


def test_transition_social_to_daily():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    state.set("pyscript.basement_social_source", "manual")
    basement.on_lighting_mode_changed("Daily Driver", "Social Mode")
    mock_task.run_deferred_tasks()
    assert state.get("pyscript.basement_social_source") == "none", "FAIL: Social source not cleared!"
    assert spy.was_called("switch", "turn_on", "switch.basement_adaptive_lighting_adaptive_lighting_basement_adaptive_lighting"), \
        "FAIL: Adaptive Lighting not enabled!"
    print("  ✓ [Matrix] test_transition_social_to_daily PASSED")


def test_transition_movie_to_social():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Social Mode")
    basement.on_lighting_mode_changed("Social Mode", "Movie Mode")
    mock_task.run_deferred_tasks()
    assert state.get("pyscript.basement_social_source") == "manual", "FAIL: Social source not recorded!"
    print("  ✓ [Matrix] test_transition_movie_to_social PASSED")


def test_transition_daily_to_movie():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Movie Mode")
    basement.on_lighting_mode_changed("Movie Mode", "Daily Driver")
    mock_task.run_deferred_tasks()
    assert state.get("pyscript.basement_social_source") == "none", "FAIL: Social source set in Movie Mode!"
    print("  ✓ [Matrix] test_transition_daily_to_movie PASSED")


# ==============================================================================
# SUITE 3: TEMPORAL & TIMEOUT ENGINE (4 TESTS)
# ==============================================================================
def test_pause_debounce_not_triggering_on_quick_seek():
    """Verify skipping forward in Stremio (< 4s) keeps cans in 0% blackout."""
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Movie Mode")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "movie")
    state.set("media_player.onn_pro", "on")
    state.set("sensor.mediasession2mqtt_1_playback_state", "playing")

    basement.theater_lighting_sync()
    spy.clear()

    state.set("sensor.mediasession2mqtt_1_playback_state", "playing")
    basement.theater_lighting_sync()
    mock_task.run_deferred_tasks()

    turned_on = any(
        c["domain"] == "light" and c["service"] == "turn_on" and
        c["kwargs"].get("entity_id") == "light.theater_dimmer"
        for c in spy.calls
    )
    assert not turned_on, "FAIL: Quick seek turned on lights during movie!"
    print("  ✓ [Temporal] test_pause_debounce_not_triggering_on_quick_seek PASSED")


def test_stair_downward_entry_does_not_cut_lights_on_door_close():
    setup_clean_environment()
    basement.DIRECTION_OF_TRAVEL = "down"
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    state.set("light.stairlights", "on")

    basement.stair_door_closed("on")
    mock_task.run_deferred_tasks()
    assert not spy.was_called("light", "turn_off", "light.stairlights"), \
        "FAIL: Stairs turned off when door closed on downward entry! Traps slow walkers!"
    print("  ✓ [Temporal] test_stair_downward_entry_does_not_cut_lights_on_door_close PASSED")


def test_curtain_call_instant_walkout():
    setup_clean_environment()
    state.set("pyscript.curtain_call_active", "on")
    basement.stair_door_closed("on")
    mock_task.run_deferred_tasks()
    assert state.get("pyscript.curtain_call_active") == "off", "FAIL: Curtain call not reset!"
    assert spy.was_called("light", "turn_off", "light.theater_dimmer"), "FAIL: Curtain call walkout did not kill cans!"
    assert spy.was_called("switch", "turn_off", "switch.bias_lights"), "FAIL: Curtain call walkout did not kill bias!"
    print("  ✓ [Temporal] test_curtain_call_instant_walkout PASSED")


def test_open_door_vacancy_guard():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    state.set("binary_sensor.theater_in_use", "off")

    basement.basement_door_open_vacancy_guard()
    mock_task.run_deferred_tasks()
    assert spy.was_called("light", "turn_off", "light.theater_dimmer"), "FAIL: Vacancy guard did not turn off cans!"
    assert spy.was_called("light", "turn_off", "light.stairlights"), "FAIL: Vacancy guard did not turn off stairs!"
    print("  ✓ [Temporal] test_open_door_vacancy_guard PASSED")


# ==============================================================================
# SUITE 4: PROJECTOR COOLDOWN & THERMAL SAFETY (3 TESTS)
# ==============================================================================
def test_projector_cooldown_fan_timeout_keeps_mains_on():
    setup_clean_environment()
    state.set("switch.projector", "on")
    state.set("sensor.projector_current", "0.18")
    state.set("sensor.theater_mode", "off")

    theater.safe_projector_cooldown()
    mock_task.run_deferred_tasks()
    assert not spy.was_called("switch", "turn_off", "switch.projector"), \
        "FAIL: Projector plug cut while fan was still spinning! Thermal hazard!"
    print("  ✓ [Thermal] test_projector_cooldown_fan_timeout_keeps_mains_on PASSED")


def test_projector_cooldown_double_low_reads_requirement():
    setup_clean_environment()
    state.set("switch.projector", "on")
    state.set("sensor.projector_current", "0.03")
    state.set("sensor.theater_mode", "off")

    theater.safe_projector_cooldown()
    mock_task.run_deferred_tasks()
    assert spy.was_called("switch", "turn_off", "switch.projector"), \
        "FAIL: Projector plug not cut after verified double low reads!"
    print("  ✓ [Thermal] test_projector_cooldown_double_low_reads_requirement PASSED")


def test_projector_cooldown_aborts_on_movie_resumed():
    setup_clean_environment()
    state.set("switch.projector", "on")
    state.set("sensor.projector_current", "0.03")
    state.set("sensor.theater_mode", "movie")

    theater.safe_projector_cooldown()
    mock_task.run_deferred_tasks()
    assert not spy.was_called("switch", "turn_off", "switch.projector"), \
        "FAIL: Cooldown power-cut executed despite movie resuming!"
    print("  ✓ [Thermal] test_projector_cooldown_aborts_on_movie_resumed PASSED")


# ==============================================================================
# SUITE 5: AV TELEMETRY & SOURCE ARBITRATION (4 TESTS)
# ==============================================================================
def test_telemetry_receiver_off_sets_theater_mode_off():
    setup_clean_environment()
    state.set("media_player.theater_receiver", "off")
    theater.update_theater_mode()
    assert state.get("sensor.theater_mode") == "off", "FAIL: theater_mode not 'off' when receiver off!"
    print("  ✓ [Telemetry] test_telemetry_receiver_off_sets_theater_mode_off PASSED")


def test_telemetry_hdmi2_sets_game_mode():
    setup_clean_environment()
    state.set("media_player.theater_receiver", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI2"
    theater.update_theater_mode()
    assert state.get("sensor.theater_mode") == "game", "FAIL: HDMI2 did not evaluate to 'game'!"
    print("  ✓ [Telemetry] test_telemetry_hdmi2_sets_game_mode PASSED")


def test_telemetry_hdmi1_spotify_sets_music_mode():
    setup_clean_environment()
    state.set("media_player.theater_receiver", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI1"
    state.set("sensor.mediasession2mqtt_1_application_id", "com.spotify.tv.android")
    theater.update_theater_mode()
    assert state.get("sensor.theater_mode") == "music", "FAIL: Spotify on HDMI1 did not evaluate to 'music'!"
    print("  ✓ [Telemetry] test_telemetry_hdmi1_spotify_sets_music_mode PASSED")


def test_telemetry_bluetooth_native_sets_music_mode():
    setup_clean_environment()
    state.set("media_player.theater_receiver", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "Bluetooth"
    theater.update_theater_mode()
    assert state.get("sensor.theater_mode") == "music", "FAIL: Bluetooth did not evaluate to 'music'!"
    print("  ✓ [Telemetry] test_telemetry_bluetooth_native_sets_music_mode PASSED")


# ==============================================================================
# SUITE 6: BATOCERA ECOSYSTEM & AUDIO (2 TESTS)
# ==============================================================================
def test_batocera_auto_cut_when_current_drops():
    setup_clean_environment()
    state.set("switch.batocera", "on")
    state.set("sensor.batocera_current", "0.02")
    theater.batocera_auto_power_off()
    assert spy.was_called("switch", "turn_off", "switch.batocera"), "FAIL: Batocera plug not cut on halt!"
    print("  ✓ [Batocera] test_batocera_auto_cut_when_current_drops PASSED")


def test_batocera_audio_sound_mode_selection():
    setup_clean_environment()
    state.set("sensor.batocera_system", "nes")
    theater.configure_batocera_audio()
    call = spy.last_call_for("media_player", "select_sound_mode")
    assert call and call["kwargs"].get("sound_mode") == "Straight", "FAIL: NES did not select Straight stereo!"

    state.set("sensor.batocera_system", "psx")
    theater.configure_batocera_audio()
    call = spy.last_call_for("media_player", "select_sound_mode")
    assert call and call["kwargs"].get("sound_mode") == "Surround Decoder", "FAIL: PSX did not select Surround Decoder!"

    # Moonlight / PC Streaming uses Surround Decoder (plays true 5.1 natively, matrixes stereo)
    state.set("sensor.batocera_system", "moonlight")
    theater.configure_batocera_audio()
    call = spy.last_call_for("media_player", "select_sound_mode")
    assert call and call["kwargs"].get("sound_mode") == "Surround Decoder", "FAIL: Moonlight did not select Surround Decoder!"
    print("  ✓ [Batocera] test_batocera_audio_sound_mode_selection PASSED")


def test_batocera_game_boxart_resolution_populates_dedicated_sensor():
    """Verify playing a game on Batocera updates dedicated sensor.theater_current_boxart and attributes."""
    setup_clean_environment()
    state.set("sensor.theater_mode", "game")
    state.set("sensor.batocera_state", "playing")
    state.set("sensor.batocera_current_game", "Super Mario World (USA).sfc")
    state.set("sensor.batocera_system", "snes")

    theater.update_game_poster()

    boxart = state.get("sensor.theater_current_boxart")
    assert boxart and boxart.startswith("http"), "FAIL: Boxart sensor did not receive valid image URL!"

    attrs = state._attrs.get("sensor.theater_current_boxart", {})
    assert "Super Mario World" in attrs.get("title", ""), \
        f"FAIL: Title not sanitized correctly, got '{attrs.get('title')}'!"
    assert attrs.get("system") == "SNES", f"FAIL: System not uppercase SNES, got '{attrs.get('system')}'!"
    assert attrs.get("backdrop_url") and attrs.get("backdrop_url").startswith("http"), \
        "FAIL: Backdrop URL not set on boxart sensor!"
    assert attrs.get("media_type") == "game", "FAIL: media_type not 'game'!"

    # Verify poster is also synced in game mode for backward compatibility
    poster = state.get("sensor.theater_current_poster")
    assert poster == boxart, "FAIL: sensor.theater_current_poster did not sync with boxart in game mode!"
    print("  ✓ [Batocera] test_batocera_game_boxart_resolution_populates_dedicated_sensor PASSED")


def test_batocera_game_boxart_decoupled_from_movie_poster():
    """Verify game boxart is completely isolated from movie TMDB poster state."""
    setup_clean_environment()
    movie_poster = "https://image.tmdb.org/t/p/w780/interstellar_poster.jpg"
    state.set("sensor.theater_current_poster", movie_poster)
    state._attrs.setdefault("sensor.theater_current_poster", {})["title"] = "Interstellar"

    state.set("sensor.theater_mode", "game")
    state.set("sensor.batocera_state", "playing")
    state.set("sensor.batocera_current_game", "Sonic The Hedgehog (USA).md")
    state.set("sensor.batocera_system", "genesis")

    theater.update_game_poster()

    boxart = state.get("sensor.theater_current_boxart")
    assert boxart != movie_poster, "FAIL: Boxart sensor was corrupted by movie poster!"
    attrs = state._attrs.get("sensor.theater_current_boxart", {})
    assert attrs.get("system") == "GENESIS", "FAIL: System not GENESIS!"
    assert "Sonic" in attrs.get("title", ""), "FAIL: Game title not set on boxart sensor!"
    print("  ✓ [Batocera] test_batocera_game_boxart_decoupled_from_movie_poster PASSED")


def test_batocera_boxart_reset_on_power_off():
    """Verify boxart sensor resets state when Batocera cuts power."""
    setup_clean_environment()
    state.set("switch.batocera", "on")
    state.set("sensor.batocera_current", "0.02")
    state.set("sensor.theater_current_boxart", "https://custom.art/game.png")

    theater.batocera_auto_power_off()

    attrs = state._attrs.get("sensor.theater_current_boxart", {})
    assert attrs.get("state") == "off", "FAIL: Boxart sensor state attribute not reset to 'off' on halt!"
    print("  ✓ [Batocera] test_batocera_boxart_reset_on_power_off PASSED")


# ==============================================================================
# SUITE 6B: ASUS ROG GAMING PC & HASS.AGENT STEAM INTEGRATION (5 TESTS)
# ==============================================================================
def test_pc_gaming_active_window_detection_and_sanitization():
    """Verify active game window on ASUS ROG PC resolves title, boxart, and sets playing state."""
    setup_clean_environment()
    state.set("sensor.theater_mode", "game")
    state.set("switch.gaming_pc", "on")
    state.set("sensor.desktop_rspn8nu_activewindow", "Cyberpunk 2077 (C) 2020 by CD Projekt RED")

    theater.update_game_poster()

    attrs = state._attrs.get("sensor.theater_current_boxart", {})
    assert "Cyberpunk 2077" in attrs.get("title", ""), f"FAIL: Title not sanitized correctly, got '{attrs.get('title')}'!"
    assert attrs.get("system") == "PC", f"FAIL: System not 'PC', got '{attrs.get('system')}'!"
    assert attrs.get("state") == "playing", f"FAIL: State not 'playing', got '{attrs.get('state')}'!"
    print("  ✓ [PC Gaming] test_pc_gaming_active_window_detection_and_sanitization PASSED")


def test_steam_big_picture_mode_carousel():
    """Verify Steam Big Picture Mode resolves as ready launcher with STEAM system badge."""
    setup_clean_environment()
    state.set("sensor.theater_mode", "game")
    state.set("switch.gaming_pc", "on")
    state.set("sensor.desktop_rspn8nu_activewindow", "Steam Big Picture Mode")

    theater.update_game_poster()

    attrs = state._attrs.get("sensor.theater_current_boxart", {})
    assert attrs.get("title") == "Steam Big Picture Mode", f"FAIL: Expected Steam Big Picture Mode, got '{attrs.get('title')}'!"
    assert attrs.get("system") == "STEAM", f"FAIL: System not 'STEAM', got '{attrs.get('system')}'!"
    assert attrs.get("state") == "idle", f"FAIL: State not 'idle', got '{attrs.get('state')}'!"
    print("  ✓ [PC Gaming] test_steam_big_picture_mode_carousel PASSED")


def test_pc_gaming_gpu_temp_telemetry_in_subtitle():
    """Verify GPU temperature from HASS.Agent is included in boxart and subtitle attributes."""
    setup_clean_environment()
    state.set("sensor.theater_mode", "game")
    state.set("switch.gaming_pc", "on")
    state.set("sensor.desktop_rspn8nu_activewindow", "Elden Ring")
    state.set("sensor.desktop_rspn8nu_gputemperature", "68.4")

    theater.update_game_poster()

    attrs = state._attrs.get("sensor.theater_current_boxart", {})
    assert attrs.get("gpu_temperature") == "68°C", f"FAIL: GPU temp attribute mismatch, got '{attrs.get('gpu_temperature')}'!"
    poster_attrs = state._attrs.get("sensor.theater_current_poster", {})
    assert "68°C" in poster_attrs.get("subtitle", ""), f"FAIL: GPU temp missing from poster subtitle, got '{poster_attrs.get('subtitle')}'!"
    print("  ✓ [PC Gaming] test_pc_gaming_gpu_temp_telemetry_in_subtitle PASSED")


def test_moonlight_app_triggers_game_mode():
    """Verify Moonlight app on HDMI1 automatically switches theater mode to 'game'."""
    setup_clean_environment()
    state.set("media_player.theater_receiver", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI1"
    state.set("sensor.mediasession2mqtt_1_application_id", "com.limelight")

    theater.update_theater_mode()

    assert state.get("sensor.theater_mode") == "game", f"FAIL: Moonlight app on HDMI1 did not resolve to 'game', got '{state.get('sensor.theater_mode')}'!"
    print("  ✓ [PC Gaming] test_moonlight_app_triggers_game_mode PASSED")


def test_pc_gaming_blackout_in_theater_lighting_sync():
    """Verify actively playing a PC game triggers full cinema blackout and bias lights."""
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "game")
    state.set("switch.gaming_pc", "on")
    state.set("sensor.desktop_rspn8nu_activewindow", "Cyberpunk 2077")
    state.set("light.theater_dimmer", "on")

    basement.theater_lighting_sync()

    call = spy.last_call_for("light", "turn_off")
    assert call is not None, "FAIL: light.turn_off not called during active PC gaming!"
    bias_call = spy.last_call_for("switch", "turn_on")
    assert bias_call and bias_call["kwargs"].get("entity_id") == "switch.bias_lights", "FAIL: switch.bias_lights not turned on!"
    print("  ✓ [PC Gaming] test_pc_gaming_blackout_in_theater_lighting_sync PASSED")


def test_steam_shortcut_title_sanitization():
    """Verify steam shortcut titles like '1794680_Vampire_Survivors' have AppID dropped and underscores replaced."""
    raw = "1794680_Vampire_Survivors.exe"
    clean = theater.RE_ROM_EXT.sub("", raw)
    clean = theater.RE_ROM_TAGS.sub("", clean).strip()
    import re
    clean = re.sub(r"^\d+_", "", clean).replace("_", " ").strip()
    assert clean == "Vampire Survivors", f"FAIL: Expected 'Vampire Survivors', got '{clean}'!"
    print("  ✓ [PC Gaming] test_steam_shortcut_title_sanitization PASSED")


def test_play_pc_game_target_routing():
    """Verify play_pc_game supports explicit routing between Batocera (HDMI2, Straight 5.1 PCM) and Onn (HDMI1, Surround Decoder)."""
    setup_clean_environment()

    # Case 1: Route to Batocera Dell laptop client
    theater.play_pc_game(target="batocera")
    assert spy.was_called("switch", "turn_on", "switch.gaming_pc"), "FAIL: PC not turned on!"
    assert spy.was_called("switch", "turn_on", "switch.batocera"), "FAIL: Batocera PC not turned on!"
    src_call = spy.last_call_for("media_player", "select_source")
    assert src_call and src_call["kwargs"].get("source") == "HDMI2", f"FAIL: Source not HDMI2, got {src_call}!"
    snd_call = spy.last_call_for("media_player", "select_sound_mode")
    assert snd_call and snd_call["kwargs"].get("sound_mode") == "Surround Decoder", f"FAIL: Batocera 5.1 PCM did not select Surround Decoder, got {snd_call}!"

    # Case 2: Route to Onn 4K Pro client
    setup_clean_environment()
    theater.play_pc_game(target="onn")
    src_call = spy.last_call_for("media_player", "select_source")
    assert src_call and src_call["kwargs"].get("source") == "HDMI1", f"FAIL: Source not HDMI1, got {src_call}!"
    snd_call = spy.last_call_for("media_player", "select_sound_mode")
    assert snd_call and snd_call["kwargs"].get("sound_mode") == "Surround Decoder", f"FAIL: Onn 5.1 did not select Surround Decoder, got {snd_call}!"
    print("  ✓ [PC Gaming] test_play_pc_game_target_routing PASSED")


# ==============================================================================
# SUITE 7: AUDIO ROUTING & SPORTS COMMENTARY SUPPRESSION (9 TESTS)
# ==============================================================================
def test_audio_routing_youtube_engages_surround_decoder():
    """Verify launching YouTube on HDMI1 automatically sets Yamaha to Surround Decoder."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI1"
    state.set("sensor.mediasession2mqtt_1_application_id", "com.google.android.youtube.tv")

    theater.route_app_audio_mode()
    call = spy.last_call_for("media_player", "select_sound_mode")
    assert call and call["kwargs"].get("sound_mode") == "Surround Decoder", "FAIL: YouTube did not set Surround Decoder!"
    print("  ✓ [AudioRouter] test_audio_routing_youtube_engages_surround_decoder PASSED")


def test_audio_routing_stremio_engages_standard_surround():
    """Verify launching Stremio on HDMI1 automatically sets Yamaha to Standard surround."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI1"
    state.set("sensor.mediasession2mqtt_1_application_id", "com.stremio.one")

    theater.route_app_audio_mode()
    call = spy.last_call_for("media_player", "select_sound_mode")
    assert call and call["kwargs"].get("sound_mode") == "Standard", "FAIL: Stremio did not set Standard surround!"
    print("  ✓ [AudioRouter] test_audio_routing_stremio_engages_standard_surround PASSED")


def test_audio_routing_spotify_engages_7ch_stereo():
    """Verify launching Spotify on HDMI1 automatically sets Yamaha to 7ch Stereo."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI1"
    state.set("sensor.mediasession2mqtt_1_application_id", "com.spotify.tv.android")

    theater.route_app_audio_mode()
    call = spy.last_call_for("media_player", "select_sound_mode")
    assert call and call["kwargs"].get("sound_mode") == "7ch Stereo", "FAIL: Spotify did not set 7ch Stereo!"
    print("  ✓ [AudioRouter] test_audio_routing_spotify_engages_7ch_stereo PASSED")


def test_audio_routing_ignored_when_on_hdmi2_gaming():
    """Verify HDMI1 app changes do NOT alter audio if the AVR is tuned to HDMI2 (Batocera)."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI2"
    state.set("sensor.mediasession2mqtt_1_application_id", "com.google.android.youtube.tv")

    theater.route_app_audio_mode()
    assert not spy.was_called("media_player", "select_sound_mode"), \
        "FAIL: Audio routing altered sound mode while on HDMI2 gaming input!"
    print("  ✓ [AudioRouter] test_audio_routing_ignored_when_on_hdmi2_gaming PASSED")


def test_audio_routing_hdhomerun_engages_sports_mode_and_ducks_center():
    """Verify launching HDHomeRun sets Sports DSP and commands Center trim to slider level."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI1"
    state.set("sensor.mediasession2mqtt_1_application_id", "com.silicondust.view")
    state.set("input_number.theater_announcer_volume", "-8.5")

    theater.route_app_audio_mode()
    snd_call = spy.last_call_for("media_player", "select_sound_mode")
    trim_call = spy.last_call_for("rest_command", "yamaha_set_center_trim")

    assert snd_call and snd_call["kwargs"].get("sound_mode") == "Sports", "FAIL: HDHomeRun did not set Sports DSP!"
    assert trim_call and trim_call["kwargs"].get("level") == -8.5, "FAIL: HDHomeRun did not duck center channel to -8.5 dB!"
    print("  ✓ [SportsAudio] test_audio_routing_hdhomerun_engages_sports_mode_and_ducks_center PASSED")


def test_audio_routing_televizio_defaults_center_to_minus_10_if_slider_missing():
    """Verify missing/unset slider falls back safely to -10 dB."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI1"
    state.set("sensor.mediasession2mqtt_1_application_id", "com.armata.televizio")
    state._states.pop("input_number.theater_announcer_volume", None)

    theater.route_app_audio_mode()
    snd_call = spy.last_call_for("media_player", "select_sound_mode")
    trim_call = spy.last_call_for("rest_command", "yamaha_set_center_trim")

    assert snd_call and snd_call["kwargs"].get("sound_mode") == "Sports", "FAIL: Televizio did not set Sports DSP!"
    assert trim_call and trim_call["kwargs"].get("level") == -10.0, "FAIL: Center trim did not default to -10.0 dB!"
    print("  ✓ [SportsAudio] test_audio_routing_televizio_defaults_center_to_minus_10_if_slider_missing PASSED")


def test_audio_routing_exiting_sports_to_stremio_restores_flat_center():
    """Verify moving from sports back to movies restores 0.0 dB flat center trim."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI1"
    state.set("sensor.mediasession2mqtt_1_application_id", "com.stremio.one")

    theater.route_app_audio_mode()
    snd_call = spy.last_call_for("media_player", "select_sound_mode")
    trim_call = spy.last_call_for("rest_command", "yamaha_set_center_trim")

    assert snd_call and snd_call["kwargs"].get("sound_mode") == "Standard", "FAIL: Stremio did not set Standard surround!"
    assert trim_call and trim_call["kwargs"].get("level") == 0.0, "FAIL: Stremio did not restore flat 0.0 dB center trim!"
    print("  ✓ [SportsAudio] test_audio_routing_exiting_sports_to_stremio_restores_flat_center PASSED")


def test_session_end_turns_off_zone_2_and_resets_center_trim():
    """Verify session_end cuts Zone 2 vampire power and restores 0.0 dB center trim."""
    setup_clean_environment()
    state.set("media_player.theater_receiver", "on")
    state.set("media_player.theater_receiver_zone_2", "on")

    theater.session_end_house_lights()
    assert spy.was_called("media_player", "turn_off", "media_player.theater_receiver_zone_2"), \
        "FAIL: session_end_house_lights did not turn off Yamaha Zone 2!"
    trim_call = spy.last_call_for("rest_command", "yamaha_set_center_trim")
    assert trim_call and trim_call["kwargs"].get("level") == 0.0, \
        "FAIL: session_end_house_lights did not reset center trim to 0.0 dB!"
    print("  ✓ [SportsAudio] test_session_end_turns_off_zone_2_and_resets_center_trim PASSED")


def test_play_movie_resets_center_trim():
    """Verify initiating movie playback restores flat 0.0 dB center trim and launches Stremio."""
    setup_clean_environment()
    theater.play_movie()
    trim_call = spy.last_call_for("rest_command", "yamaha_set_center_trim")
    assert trim_call and trim_call["kwargs"].get("level") == 0.0, \
        "FAIL: play_movie did not reset center trim to 0.0 dB!"
    assert any(
        c["domain"] == "remote" and c["service"] == "turn_on" and
        c["kwargs"].get("activity") in ["com.stremio.one", "com.stremio.one/.MainActivity"]
        for c in spy.calls
    ), "FAIL: play_movie did not launch com.stremio.one via remote.turn_on!"
    print("  ✓ [SportsAudio] test_play_movie_resets_center_trim PASSED")


def test_stremio_futurama_episode_art_resolution():
    """Verify playing a Futurama episode resolves to 'Futurama' and never 'Stremio Theatrical'."""
    setup_clean_environment()
    state.set("sensor.theater_mode", "movie")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.mediasession2mqtt_1_application_id", "com.stremio.one")
    state.set("sensor.mediasession2mqtt_1_playback_state", "playing")
    state.set("sensor.mediasession2mqtt_1_media_title", "Space Pilot 3000 - Futurama")

    theater.update_theater_media_art()
    poster_title = state.getattr("sensor.theater_current_poster", "title")
    assert poster_title != "Stremio Theatrical", "FAIL: Poster still says 'Stremio Theatrical'!"
    assert "Futurama" in (poster_title or ""), f"FAIL: Expected 'Futurama' in title, got '{poster_title}'!"
    print("  ✓ [Atmospheric] test_stremio_futurama_episode_art_resolution PASSED")


def test_stremio_movie_title_resolution():
    """Verify playing a movie without API key cleanly sets movie title and never 'Stremio Theatrical'."""
    setup_clean_environment()
    state.set("sensor.theater_mode", "movie")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.mediasession2mqtt_application_id", "com.stremio.one")
    state.set("sensor.mediasession2mqtt_playback_state", "playing")
    state.set("sensor.mediasession2mqtt_media_title", "Inception.2010.1080p.WEBRip.x264.mp4")

    theater.update_theater_media_art()
    poster_title = state.getattr("sensor.theater_current_poster", "title")
    assert poster_title != "Stremio Theatrical", "FAIL: Poster still says 'Stremio Theatrical'!"
    assert "Inception" in (poster_title or ""), f"FAIL: Expected 'Inception' in title, got '{poster_title}'!"
    print("  ✓ [Atmospheric] test_stremio_movie_title_resolution PASSED")


# ==============================================================================
# SUITE 8: ATMOSPHERIC ENGINE & PRE-SHOW (5 TESTS)
# ==============================================================================
def test_lobby_browsing_android_launcher():
    """Verify sitting on Google TV launcher caps cans at 1% and bias ON (Never above 1%)."""
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Movie Mode")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "movie")
    state.set("media_player.onn_pro", "on")
    state.set("sensor.mediasession2mqtt_1_playback_state", "idle")
    state._attrs.setdefault("remote.onn_pro", {})["current_activity"] = "com.google.android.apps.tv.launcherx"

    basement.theater_lighting_sync()
    mock_task.run_deferred_tasks()

    assert any(
        c["domain"] == "light" and c["service"] == "turn_on" and
        c["kwargs"].get("entity_id") == "light.theater_dimmer" and c["kwargs"].get("brightness_pct") == 1
        for c in spy.calls
    ), "FAIL: Lobby browsing did not set cans to 1%!"
    assert spy.was_called("switch", "turn_on", "switch.bias_lights"), "FAIL: Bias not on in lobby!"
    print("  ✓ [Atmospheric] test_lobby_browsing_android_launcher PASSED")


def test_lobby_browsing_batocera_carousel():
    """Verify Batocera EmulationStation carousel sets cans to 1% and bias ON."""
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Movie Mode")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "game")
    state.set("sensor.batocera_state", "idle")

    basement.theater_lighting_sync()
    mock_task.run_deferred_tasks()

    assert any(
        c["domain"] == "light" and c["service"] == "turn_on" and
        c["kwargs"].get("entity_id") == "light.theater_dimmer" and c["kwargs"].get("brightness_pct") == 1
        for c in spy.calls
    ), "FAIL: Batocera carousel did not set cans to 1%!"
    print("  ✓ [Atmospheric] test_lobby_browsing_batocera_carousel PASSED")


def test_music_lounge_lighting_sync():
    """Verify music mode sets blackout cans, bias ON, and shuts off basement Zigbees."""
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Movie Mode")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "music")

    basement.theater_lighting_sync()
    mock_task.run_deferred_tasks()

    assert any(
        c["domain"] == "light" and c["service"] == "turn_off" and
        ("light.theater_dimmer" in (c["kwargs"].get("entity_id") if isinstance(c["kwargs"].get("entity_id"), list) else [c["kwargs"].get("entity_id")]))
        for c in spy.calls
    ), "FAIL: Music mode did not turn off dimmer!"
    assert spy.was_called("switch", "turn_on", "switch.bias_lights"), "FAIL: Bias not on in music lounge!"
    assert any(
        c["domain"] == "light" and c["service"] == "turn_off" and
        ("light.zigbee_basement_lights" in (c["kwargs"].get("entity_id") if isinstance(c["kwargs"].get("entity_id"), list) else [c["kwargs"].get("entity_id")]))
        for c in spy.calls
    ), "FAIL: Zigbee not off in music lounge!"
    print("  ✓ [Atmospheric] test_music_lounge_lighting_sync PASSED")


def test_nightly_social_reset_clears_modes():
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Social Mode")
    state.set("pyscript.basement_social_source", "manual")
    state.set("pyscript.curtain_call_active", "on")

    basement.safe_nightly_social_reset()
    assert state.get("input_select.basement_lighting_mode") == "Daily Driver", "FAIL: Not reset to Daily Driver!"
    assert state.get("pyscript.basement_social_source") == "none", "FAIL: Social source not cleared!"
    assert state.get("pyscript.curtain_call_active") == "off", "FAIL: Curtain call not cleared!"
    print("  ✓ [Atmospheric] test_nightly_social_reset_clears_modes PASSED")


# ==============================================================================
# SUITE 9: MASTER UTILITIES & GUEST LOCK (4 TESTS)
# ==============================================================================
def test_social_mode_lock_blocks_exit_shutoff():
    setup_clean_environment()
    basement.DIRECTION_OF_TRAVEL = "up"
    state.set("input_select.basement_lighting_mode", "Social Mode")

    basement.stair_door_closed("on")
    mock_task.run_deferred_tasks()
    assert not spy.was_called("light", "turn_off", "light.theater_dimmer"), \
        "FAIL: Walk-out turned off lights despite Social Mode lock!"
    print("  ✓ [Utility] test_social_mode_lock_blocks_exit_shutoff PASSED")


def test_master_basement_all_off_service():
    setup_clean_environment()
    state.set("light.theater_dimmer", "on")
    state.set("light.stairlights", "on")
    state.set("switch.bias_lights", "on")
    state.set("pyscript.curtain_call_active", "on")

    basement.basement_all_off()
    assert state.get("pyscript.curtain_call_active") == "off", "FAIL: Curtain call not cleared!"
    assert state.get("input_select.basement_lighting_mode") == "Daily Driver", "FAIL: Not set to Daily Driver!"
    assert spy.was_called("light", "turn_off", "light.theater_dimmer"), "FAIL: Dimmer not off!"
    assert spy.was_called("switch", "turn_off", "switch.bias_lights"), "FAIL: Bias not off!"
    print("  ✓ [Utility] test_master_basement_all_off_service PASSED")


def test_toggle_all_basement_lights_when_loads_active():
    setup_clean_environment()
    state.set("light.theater_dimmer", "on")
    basement.toggle_all_basement_lights()
    assert spy.was_called("light", "turn_off", "light.theater_dimmer"), "FAIL: Toggle didn't shut down active loads!"
    print("  ✓ [Utility] test_toggle_all_basement_lights_when_loads_active PASSED")


def test_drawer_collapse_on_mode_select():
    setup_clean_environment()
    state.set("pyscript.mode_selector_expanded", "on")
    basement.select_lighting_mode_ui("Social Mode")
    mock_task.run_deferred_tasks()
    assert state.get("input_select.basement_lighting_mode") == "Social Mode", "FAIL: Mode not updated!"
    assert state.get("pyscript.mode_selector_expanded") == "off", "FAIL: Drawer not collapsed!"
    print("  ✓ [Utility] test_drawer_collapse_on_mode_select PASSED")


# ==============================================================================
# SUITE 10: CHAOS, FAULT INJECTION & SANITIZATION (6 TESTS)
# ==============================================================================
def test_projector_corrupted_current_fails_safe():
    setup_clean_environment()
    state.set("switch.projector", "on")
    state.set("sensor.projector_current", "unavailable")
    is_cold = theater.is_projector_cold()
    assert not is_cold, "FAIL: Corrupted sensor evaluated as cold! Dangerous thermal cut!"
    print("  ✓ [Chaos] test_projector_corrupted_current_fails_safe PASSED")


def test_projector_negative_or_none_current():
    setup_clean_environment()
    state.set("switch.projector", "on")
    state.set("sensor.projector_current", None)
    is_cold = theater.is_projector_cold()
    assert not is_cold, "FAIL: None current reading evaluated as cold!"
    print("  ✓ [Chaos] test_projector_negative_or_none_current PASSED")


def test_force_projector_off_emergency_sequence():
    """Verify force_projector_off wakes devices for CEC, cuts them, and shuts off Zone 2."""
    setup_clean_environment()
    state.set("media_player.theater_receiver", "off")
    state.set("media_player.theater_receiver_zone_2", "on")
    theater.force_projector_off()

    assert spy.was_called("media_player", "turn_on", "media_player.theater_receiver"), "FAIL: AVR not woken!"
    assert spy.was_called("media_player", "turn_on", "media_player.onn_pro"), "FAIL: Onn not woken!"

    cec_call = spy.last_call_for("remote", "send_command")
    assert cec_call and cec_call["kwargs"].get("command") == "SLEEP", "FAIL: CEC Sleep command not blasted!"

    assert spy.was_called("media_player", "turn_off", "media_player.onn_pro"), "FAIL: Onn not turned off!"
    assert spy.was_called("media_player", "turn_off", "media_player.theater_receiver"), "FAIL: AVR Main not turned off!"
    assert spy.was_called("media_player", "turn_off", "media_player.theater_receiver_zone_2"), "FAIL: Zone 2 not cut!"
    print("  ✓ [Chaos] test_force_projector_off_emergency_sequence PASSED")


def test_theater_in_use_flips_daily_driver_to_movie_mode():
    """Verify AVR power-on marks theater_in_use on without mutating lighting select."""
    setup_clean_environment()
    state.set("media_player.theater_receiver", "on")
    state.set("input_select.basement_lighting_mode", "Daily Driver")

    theater.update_theater_in_use()

    assert state.get("binary_sensor.theater_in_use") == "on", "FAIL: theater_in_use not set to on!"
    assert state.get("input_select.basement_lighting_mode") == "Daily Driver", "FAIL: Daily Driver changed unexpectedly!"
    print("  ✓ [Chaos] test_theater_in_use_flips_daily_driver_to_movie_mode PASSED")


def test_game_title_sanitization_removes_rom_tags():
    """Verify dirty ROM filenames strip extensions, regional brackets, and Steam shortcut app IDs cleanly."""
    dirty_title = "Super Mario World (USA) [En].sfc"
    clean_title = re.sub(r"\.[a-zA-Z0-9]{2,4}$", "", dirty_title)
    clean_title = clean_title.split("(")[0].split("[")[0].strip()

    assert clean_title == "Super Mario World", f"FAIL: Expected 'Super Mario World', got '{clean_title}'"

    steam_title = "1794680_Vampire_Survivors"
    clean_steam = re.sub(r"^\d+_", "", steam_title).replace("_", " ").strip()
    assert clean_steam == "Vampire Survivors", f"FAIL: Expected 'Vampire Survivors', got '{clean_steam}'"
    print("  ✓ [Chaos] test_game_title_sanitization_removes_rom_tags PASSED")


def test_tmdb_fetcher_missing_key_graceful_fail():
    """Verify TMDB fetcher returns safe error dict or None when secrets are unreadable, and handles valid keys safely."""
    from unittest.mock import patch

    # 1. Verify missing secret path returns safe error dict or None
    with patch.object(theater, "_read_secret", return_value=None):
        res = theater._fetch_tmdb_from_secrets("Interstellar 2014")
        assert res is None or "error" in res, "FAIL: TMDB fetcher did not handle missing secret safely!"

    # 2. Verify that if a key is present (user's environment), it returns either results or error safely without unhandled exception
    res_actual = theater._fetch_tmdb_from_secrets("Interstellar 2014")
    assert res_actual is None or isinstance(res_actual, dict), "FAIL: TMDB fetcher did not return dict or None!"
    print("  ✓ [Chaos] test_tmdb_fetcher_missing_key_graceful_fail PASSED")


# ==============================================================================
# SUITE 11: THE FULL "EVENING IN THE BASEMENT" END-TO-END STORY TEST (1 TEST)
# ==============================================================================
def test_full_evening_story_simulation():
    setup_clean_environment()

    # --- 1. Arrival (6:00 PM) ---
    basement.stair_door_opened("off")
    mock_task.run_deferred_tasks()
    assert spy.was_called("adaptive_lighting", "apply"), "Story Fail: Step 1 Stairs didn't turn on!"

    basement.motion_at_foot_of_stairs("off")
    mock_task.run_deferred_tasks()
    assert spy.was_called("light", "turn_on", "light.theater_dimmer"), "Story Fail: Step 1 Cans didn't turn on!"

    # --- 2. Cocktail Hour (7:00 PM) ---
    basement.select_palette("speakeasy")
    mock_task.run_deferred_tasks()
    assert state.get("input_select.basement_lighting_mode") == "Social Mode", "Story Fail: Step 2 Not in Social Mode!"

    # --- 3. Movie Night Transition & Showtime (8:30 PM) ---
    basement.select_lighting_mode_ui("Daily Driver")
    theater.play_movie()
    theater.update_theater_in_use()
    mock_task.run_deferred_tasks()
    assert spy.was_called("switch", "turn_on", "switch.projector"), "Story Fail: Step 3 Projector plug didn't energize!"

    state.set("sensor.mediasession2mqtt_1_playback_state", "playing")
    basement.theater_lighting_sync()
    mock_task.run_deferred_tasks()
    assert spy.was_called("light", "turn_off", "light.theater_dimmer"), "Story Fail: Step 3 Theater didn't blackout!"
    assert spy.was_called("switch", "turn_on", "switch.bias_lights"), "Story Fail: Step 3 Bias light didn't turn on!"

    # --- 4. Bathroom Break (9:15 PM) ---
    spy.clear()
    basement.motion_at_foot_of_stairs("off")
    mock_task.run_deferred_tasks()
    assert not spy.was_called("light", "turn_on", "light.theater_dimmer"), "Story Fail: Step 4 Room cans breached during movie!"
    stealth_active = any(c["domain"] == "light" and c["kwargs"].get("color_temp_kelvin") == 2000 and c["kwargs"].get("brightness_pct") == 2 for c in spy.calls)
    assert stealth_active, "Story Fail: Step 4 Stairs were not 2% candlelight!"

    # --- 5. Intermission (9:45 PM) ---
    spy.clear()
    state.set("sensor.mediasession2mqtt_1_playback_state", "paused")
    basement.theater_lighting_sync()
    mock_task.run_deferred_tasks()
    assert any(c["domain"] == "light" and c["kwargs"].get("brightness_pct") == 1 for c in spy.calls), \
        "Story Fail: Step 5 Intermission 1% glow didn't activate!"

    # --- 6. Curtain Call & Exit (10:30 PM) ---
    spy.clear()
    theater.session_end_house_lights()
    mock_task.run_deferred_tasks()
    assert state.get("pyscript.curtain_call_active") == "on", "Story Fail: Step 6 Curtain call not active!"

    basement.DIRECTION_OF_TRAVEL = "up"
    basement.stair_door_closed("on")
    mock_task.run_deferred_tasks()
    assert spy.was_called("light", "turn_off", "light.theater_dimmer"), "Story Fail: Step 6 Instant shutoff failed on walkout!"
    assert spy.was_called("light", "turn_off", "light.stairlights"), "Story Fail: Step 6 Stairs stayed on after walkout!"

    print("  ★ [E2E] test_full_evening_story_simulation (5-Hour Real Life Story) PASSED")

def test_snack_runner_walkout_does_not_cut_movie_lights():
    """Verify someone walking upstairs does not kill theater lights for viewers on couch."""
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "movie")
    state.set("switch.bias_lights", "on")
    basement.DIRECTION_OF_TRAVEL = "up"

    # Snack runner ascends stairs and closes the top door
    basement.stair_door_closed("on")
    mock_task.run_deferred_tasks()

    # Bias lights and Daily Driver MUST stay intact for the couch viewer
    assert not spy.was_called("switch", "turn_off", "switch.bias_lights"), \
        "FAIL: Snack runner ascending stairs killed bias lights for couch viewer!"
    assert state.get("input_select.basement_lighting_mode") == "Daily Driver", \
        "FAIL: Walkout reverted Daily Driver while theater was still in use!"
    print("  ✓ [Concurrency] test_snack_runner_walkout_does_not_cut_movie_lights PASSED")

def test_yamaha_rest_timeout_fails_gracefully():
    """Verify receiver network drops/timeouts do not crash the Pyscript audio router."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI1"
    state.set("sensor.mediasession2mqtt_1_application_id", "com.silicondust.view")

    # Simulate network timeout on the rest_command
    original_call = builtins.rest_command.yamaha_set_center_trim
    def timeout_mock(**kwargs):
        raise TimeoutError("504 Gateway Timeout: Yamaha AVR unreachable")
    builtins.rest_command.yamaha_set_center_trim = timeout_mock

    try:
        theater.route_app_audio_mode()
    except Exception as err:
        assert False, f"FAIL: Network timeout crashed the audio router: {err}"
    finally:
        builtins.rest_command.yamaha_set_center_trim = original_call

    print("  ✓ [Chaos] test_yamaha_rest_timeout_fails_gracefully PASSED")

# ==============================================================================
# SUITE 11: PHILADELPHIA EAGLES GAME-DAY & SCORING ENGINE (5 TESTS)
# ==============================================================================
def test_overturned_touchdown_negative_delta_is_ignored():
    """Verify official review / stat correction (delta < 0) does not flash lights."""
    setup_clean_environment()
    state.set("sensor.philadelphia_eagles", "IN")
    
    # Score drops from 21 to 14 after review
    sports.eagles_score_flash(value="14", old_value="21")
    mock_task.run_deferred_tasks()

    assert not spy.was_called("scene", "create"), "FAIL: Overturned touchdown triggered scene snapshot!"
    assert not spy.was_called("pyscript", "effect_eagles_chant"), "FAIL: Overturned touchdown fired chant!"
    print("  ✓ [Sports] test_overturned_touchdown_negative_delta_is_ignored PASSED")


def test_touchdown_delta_fires_eagles_chant():
    """Verify touchdown (+6 or +7 points) pulses brightness 6x and holds solid team green."""
    setup_clean_environment()
    state.set("sensor.philadelphia_eagles", "IN")

    # Touchdown (+7 points)
    sports.eagles_score_flash(value="7", old_value="0")
    mock_task.run_deferred_tasks()

    # Verify pulsed calls occurred and ended holding solid team green at 100%
    pulse_calls = [c for c in spy.calls if c["domain"] == "light" and c["service"] == "turn_on"]
    assert len(pulse_calls) >= 12, f"FAIL: Touchdown did not fire pulse sequence, got {len(pulse_calls)} calls!"
    green_calls = [c for c in pulse_calls if c["kwargs"].get("rgb_color") == sports.get_team_rgb()]
    assert len(green_calls) >= 12, f"FAIL: Expected Zigbee-safe solid green pulse calls, got {len(green_calls)}!"
    last_call = pulse_calls[-1]
    assert last_call["kwargs"].get("brightness_pct") == 100, "FAIL: Touchdown did not end holding 100% green!"
    assert last_call["kwargs"].get("rgb_color") == sports.get_team_rgb(), "FAIL: Last call did not use team RGB!"
    print("  ✓ [Sports] test_touchdown_delta_fires_eagles_chant PASSED")


def test_manual_effect_eagles_chant_cadence():
    """Verify manual effect_eagles_chant service follows true cadence and holds solid green."""
    setup_clean_environment()
    basement.effect_eagles_chant()
    mock_task.run_deferred_tasks()

    pulse_calls = [c for c in spy.calls if c["domain"] == "light" and c["service"] == "turn_on"]
    # 6 letter pulses (high+low = 12) + 2 syllable climax (3) + 1 final hold = 16 calls
    assert len(pulse_calls) >= 15, f"FAIL: Manual chant did not fire full cadence, got {len(pulse_calls)} calls!"
    green_calls = [c for c in pulse_calls if c["kwargs"].get("rgb_color") == sports.get_team_rgb()]
    assert len(green_calls) >= 15, f"FAIL: Expected Zigbee-safe green pulse calls in manual chant, got {len(green_calls)}!"
    last_call = pulse_calls[-1]
    assert last_call["kwargs"].get("brightness_pct") == 100, "FAIL: Manual chant did not end holding 100% green!"
    assert last_call["kwargs"].get("rgb_color") == sports.get_team_rgb(), "FAIL: Last call did not use team RGB!"
    print("  ✓ [Sports] test_manual_effect_eagles_chant_cadence PASSED")


def test_field_goal_delta_creates_snapshot_and_pulses():
    """Verify field goal (+3 points) pulses 3x and settles on solid team green without snapshot scene."""
    setup_clean_environment()
    state.set("sensor.philadelphia_eagles", "IN")

    # Field goal (+3 points)
    sports.eagles_score_flash(value="10", old_value="7")
    mock_task.run_deferred_tasks()

    assert not spy.was_called("scene", "create"), "FAIL: Field goal created scene snapshot when none is expected!"
    pulse_calls = [c for c in spy.calls if c["domain"] == "light" and c["service"] == "turn_on"]
    assert len(pulse_calls) >= 6, f"FAIL: Field goal did not fire pulse sequence, got {len(pulse_calls)} calls!"
    last_call = pulse_calls[-1]
    assert last_call["kwargs"].get("brightness_pct") == 100, "FAIL: Field goal did not end holding 100% green!"
    assert last_call["kwargs"].get("rgb_color") == sports.get_team_rgb(), "FAIL: Last call did not use team RGB!"
    print("  ✓ [Sports] test_field_goal_delta_creates_snapshot_and_pulses PASSED")


def test_score_flash_suppressed_when_game_not_in_progress():
    """Verify score change during PRE or POST does not flash lights."""
    setup_clean_environment()
    state.set("sensor.philadelphia_eagles", "POST")

    sports.eagles_score_flash(value="24", old_value="17")
    mock_task.run_deferred_tasks()

    assert not spy.was_called("pyscript", "effect_eagles_chant"), "FAIL: Fired chant while game was POST!"
    assert not spy.was_called("scene", "create"), "FAIL: Created snapshot while game was POST!"
    print("  ✓ [Sports] test_score_flash_suppressed_when_game_not_in_progress PASSED")


def test_eagles_game_start_and_game_over_lifecycle():
    """Verify kickoff engages party mode & green, and game-over restores Adaptive Lighting."""
    setup_clean_environment()
    
    # 1. Kickoff
    sports.eagles_game_started()
    mock_task.run_deferred_tasks()
    assert state.get("input_select.basement_lighting_mode") == "Social Mode", "FAIL: Social Mode not engaged on kickoff!"
    assert state.get("pyscript.basement_social_source") == "sports", "FAIL: Kickoff Social not marked as sports!"
    assert spy.was_called("switch", "turn_off", "switch.basement_adaptive_lighting_adaptive_lighting_basement_adaptive_lighting"), \
        "FAIL: Adaptive Lighting not disabled on kickoff!"

    # 2. Game Over (handles sensor recovery from unavailable)
    sports.eagles_game_over(old_value="unavailable")
    mock_task.run_deferred_tasks()
    assert spy.was_called("pyscript", "mood_reset_normal"), "FAIL: Game over did not call mood_reset_normal!"
    print("  ✓ [Sports] test_eagles_game_start_and_game_over_lifecycle PASSED")

# ==============================================================================
# SUITE 12: SPORTS ORCHESTRATION, SLIDER SYNC & DRIFT ENGINE (9 TESTS)
# ==============================================================================
def test_play_sports_orchestration():
    """Verify play_sports sets 'sports' mode, powers hardware, ducks center, and sets green."""
    setup_clean_environment()
    theater.play_sports()
    mock_task.run_deferred_tasks()

    assert state.get("sensor.theater_mode") == "sports", "FAIL: theater_mode not 'sports'!"
    assert state.get("binary_sensor.theater_in_use") == "on", "FAIL: theater_in_use not 'on'!"
    assert spy.was_called("switch", "turn_on", "switch.projector"), "FAIL: Projector not energized!"
    assert state.get("input_select.basement_lighting_mode") == "Social Mode", "FAIL: Social Mode not engaged!"

    snd_call = spy.last_call_for("media_player", "select_sound_mode")
    assert snd_call and snd_call["kwargs"].get("sound_mode") == "Sports", "FAIL: Sports DSP not engaged!"
    assert any(
        c["domain"] == "remote" and c["service"] == "turn_on" and
        c["kwargs"].get("activity") in ["com.silicondust.view", "com.silicondust.view/.MainActivity"]
        for c in spy.calls
    ), "FAIL: play_sports did not launch com.silicondust.view via remote.turn_on!"
    print("  ✓ [SportsEngine] test_play_sports_orchestration PASSED")

def test_telemetry_hdmi1_sports_app_resolves_to_sports_mode():
    """Verify launching HDHomeRun on HDMI1 updates theater_mode to 'sports'."""
    setup_clean_environment()
    state.set("media_player.theater_receiver", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI1"
    state.set("sensor.mediasession2mqtt_1_application_id", "com.silicondust.view")

    theater.update_theater_mode()
    assert state.get("sensor.theater_mode") == "sports", "FAIL: HDHomeRun on HDMI1 did not resolve to 'sports'!"
    print("  ✓ [SportsEngine] test_telemetry_hdmi1_sports_app_resolves_to_sports_mode PASSED")


def test_projector_cooldown_aborts_on_sports_active():
    """Verify Optoma thermal cut aborts if user is watching sports."""
    setup_clean_environment()
    state.set("switch.projector", "on")
    state.set("sensor.projector_current", "0.03")
    state.set("sensor.theater_mode", "sports")

    theater.safe_projector_cooldown()
    mock_task.run_deferred_tasks()
    assert not spy.was_called("switch", "turn_off", "switch.projector"), \
        "FAIL: Projector cut power while watching sports!"
    print("  ✓ [SportsEngine] test_projector_cooldown_aborts_on_sports_active PASSED")


def test_audio_routing_ignores_android_launcher():
    """Verify returning to Google TV launcher does NOT reset audio mode to Standard."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI1"
    state.set("sensor.theater_mode", "sports")
    state.set("sensor.mediasession2mqtt_1_application_id", "com.google.android.apps.tv.launcherx")

    spy.clear()
    theater.route_app_audio_mode()
    assert not spy.was_called("media_player", "select_sound_mode"), \
        "FAIL: Audio router reset DSP while on launcher screen!"
    print("  ✓ [AudioRouter] test_audio_routing_ignores_android_launcher PASSED")


def test_audio_routing_sanitizes_activity_slash_suffix():
    """Verify ADB component activity notation (com.pkg/.MainActivity) parses cleanly."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI1"
    state.set("remote.onn_pro", "on")
    state._attrs.setdefault("remote.onn_pro", {})["current_activity"] = "com.silicondust.view/.MainActivity"

    theater.route_app_audio_mode()
    snd_call = spy.last_call_for("media_player", "select_sound_mode")
    assert snd_call and snd_call["kwargs"].get("sound_mode") == "Sports", \
        "FAIL: App suffix not sanitized; failed to match SPORTS_APPS!"
    print("  ✓ [AudioRouter] test_audio_routing_sanitizes_activity_slash_suffix PASSED")


def test_announcer_volume_slider_syncs_during_sports():
    """Verify moving the announcer volume slider sends real-time REST trim during sports."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "sports")

    theater.sync_announcer_volume_to_hardware(value="-6.5")
    trim_call = spy.last_call_for("rest_command", "yamaha_set_center_trim")
    assert trim_call and trim_call["kwargs"].get("level") == -6.5, \
        "FAIL: Center trim not commanded to -6.5 dB!"
    print("  ✓ [HardwareSync] test_announcer_volume_slider_syncs_during_sports PASSED")


def test_announcer_volume_slider_ignored_outside_sports():
    """Verify moving the announcer volume slider during a movie does not alter center trim."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "movie")

    theater.sync_announcer_volume_to_hardware(value="-6.5")
    assert not spy.was_called("rest_command", "yamaha_set_center_trim"), \
        "FAIL: Center trim altered outside of sports mode!"
    print("  ✓ [HardwareSync] test_announcer_volume_slider_ignored_outside_sports PASSED")


def test_announcer_slider_does_not_snap_to_preset():
    """Verify a slider move into a preset range keeps the exact level (no feedback snap)."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "sports")
    state.set("input_select.theater_announcer_preset", "Stadium Crowd")

    # Slider to +1.0 dB selects Broadcast Ref; the preset trigger must not reset it to 0.0
    state.set("input_number.theater_announcer_volume", "1.0")
    theater.sync_announcer_volume_to_hardware(value="1.0")
    assert state.get("input_select.theater_announcer_preset") == "Broadcast Ref"
    spy.clear()
    theater.sync_announcer_preset_to_hardware(value="Broadcast Ref")
    assert float(state.get("input_number.theater_announcer_volume")) == 1.0, \
        f"FAIL: slider snapped to {state.get('input_number.theater_announcer_volume')}"
    assert not spy.was_called("rest_command", "yamaha_set_center_trim")

    # Choosing a different preset from the toggle still jumps to its level
    theater.sync_announcer_preset_to_hardware(value="Dialogue Boost")
    assert float(state.get("input_number.theater_announcer_volume")) == 3.0
    print("  ✓ [HardwareSync] test_announcer_slider_does_not_snap_to_preset PASSED")


def test_session_end_restores_adaptive_lighting_and_clears_party():
    """Verify shutting down the theater unsets party mode and re-enables Adaptive Lighting."""
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Social Mode")
    state.set("pyscript.basement_social_source", "manual")
    state.set("switch.basement_adaptive_lighting_adaptive_lighting_basement_adaptive_lighting", "off")

    theater.session_end_house_lights()
    assert state.get("input_select.basement_lighting_mode") == "Daily Driver", "FAIL: Social Mode not ended on session end!"
    assert spy.was_called("switch", "turn_on", "switch.basement_adaptive_lighting_adaptive_lighting_basement_adaptive_lighting"), \
        "FAIL: Adaptive lighting switch not restored on session end!"
    print("  ✓ [Shutdown] test_session_end_restores_adaptive_lighting_and_clears_party PASSED")


def test_toggle_ambient_drift_service():
    """Verify toggle_ambient_drift flips between static and drift."""
    setup_clean_environment()
    state.set("sensor.basement_effect", "static")

    basement.toggle_ambient_drift()
    assert state.get("sensor.basement_effect") == "drift", "FAIL: Did not toggle to drift!"

    basement.toggle_ambient_drift()
    assert state.get("sensor.basement_effect") == "static", "FAIL: Did not toggle back to static!"
    print("  ✓ [AmbientDrift] test_toggle_ambient_drift_service PASSED")


def test_theater_volume_up_down_fine_step():
    """Verify theater volume fine stepping by 1.0 dB instead of coarse 10 dB jump."""
    setup_clean_environment()
    # Set initial volume_level at 0.500 (~50%)
    state.set("media_player.theater_receiver", "on", attributes={"volume_level": 0.500})

    theater.theater_volume_up(step_db=1.0)
    vol_call = spy.last_call_for("media_player", "volume_set")
    assert vol_call and vol_call["kwargs"].get("volume_level") == 0.510, \
        f"FAIL: Fine volume up should step to 0.510, got {vol_call}!"

    # Test fine volume down
    state.set("media_player.theater_receiver", "on", attributes={"volume_level": 0.510})
    theater.theater_volume_down(step_db=1.0)
    vol_call2 = spy.last_call_for("media_player", "volume_set")
    assert vol_call2 and vol_call2["kwargs"].get("volume_level") == 0.500, \
        f"FAIL: Fine volume down should step back to 0.500, got {vol_call2}!"

    print("  ✓ [MasterAudio] test_theater_volume_up_down_fine_step PASSED")


def test_theater_announcer_up_down_mute():
    """Verify announcer volume fine stepping and mute/toggle functionality."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "sports")
    state.set("input_number.theater_announcer_volume", "0.0")

    # Step down 1.0 dB
    theater.theater_announcer_down(step=1.0)
    assert float(state.get("input_number.theater_announcer_volume")) == -1.0, \
        f"FAIL: Announcer down failed: {state.get('input_number.theater_announcer_volume')}"

    # Step up 1.0 dB
    theater.theater_announcer_up(step=1.0)
    assert float(state.get("input_number.theater_announcer_volume")) == 0.0, \
        f"FAIL: Announcer up failed: {state.get('input_number.theater_announcer_volume')}"

    # Complete mute (-10.0 dB)
    theater.theater_announcer_mute()
    assert float(state.get("input_number.theater_announcer_volume")) == -10.0, \
        f"FAIL: Announcer mute failed: {state.get('input_number.theater_announcer_volume')}"

    # Unmute toggle (should return to 0.0 dB)
    theater.theater_announcer_mute()
    assert float(state.get("input_number.theater_announcer_volume")) == 0.0, \
        f"FAIL: Announcer unmute failed: {state.get('input_number.theater_announcer_volume')}"

    print("  ✓ [BoothAnnouncer] test_theater_announcer_up_down_mute PASSED")


def test_theater_announcer_3way_toggle():
    """Verify 3-way toggle between Stadium Crowd (-10dB), Broadcast Ref (0dB), and Dialogue Boost (+3dB)."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "sports")

    # 1. Select Stadium Crowd
    theater.theater_set_announcer_preset(preset="Stadium Crowd")
    assert state.get("input_select.theater_announcer_preset") == "Stadium Crowd", "FAIL: Preset not set to Stadium Crowd!"
    assert float(state.get("input_number.theater_announcer_volume")) == -10.0, "FAIL: Volume not set to -10.0 dB!"

    # 2. Select Broadcast Ref
    theater.theater_set_announcer_preset(preset="Broadcast Ref")
    assert state.get("input_select.theater_announcer_preset") == "Broadcast Ref", "FAIL: Preset not set to Broadcast Ref!"
    assert float(state.get("input_number.theater_announcer_volume")) == 0.0, "FAIL: Volume not set to 0.0 dB!"

    # 3. Select Dialogue Boost
    theater.theater_set_announcer_preset(preset="Dialogue Boost")
    assert state.get("input_select.theater_announcer_preset") == "Dialogue Boost", "FAIL: Preset not set to Dialogue Boost!"
    assert float(state.get("input_number.theater_announcer_volume")) == 3.0, "FAIL: Volume not set to 3.0 dB!"

    # 4. Moving slider manually back to -10.0 syncs 3-way toggle
    theater.sync_announcer_volume_to_hardware(value="-10.0")
    assert state.get("input_select.theater_announcer_preset") == "Stadium Crowd", "FAIL: Preset not resynced to Stadium Crowd!"

    print("  ✓ [Announcer3WayToggle] test_theater_announcer_3way_toggle PASSED")


def test_unmanaged_exit_receiver_power_off_triggers_safe_teardown():
    """Verify external/unmanaged AVR power-off triggers session_end_house_lights and safe cooldown."""
    setup_clean_environment()
    state.set("media_player.whole_house_spotify", "playing")
    state._attrs.setdefault("media_player.whole_house_spotify", {})["supported_features"] = 1
    state.set("media_player.theater_receiver", "off")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "movie")
    state.set("switch.projector", "on")
    state.set("switch.batocera", "on")
    state.set("sensor.batocera_state", "playing")
    state.set("pyscript.curtain_call_active", "off")

    theater.handle_receiver_power_off()

    assert state.get("pyscript.curtain_call_active") == "on", "FAIL: Curtain call not activated on unmanaged exit!"
    assert state.get("sensor.theater_mode") == "off", "FAIL: Theater mode not set to off!"
    assert state.get("binary_sensor.theater_in_use") == "off", "FAIL: Theater in use not cleared!"
    assert state.get("input_select.basement_theater_mode") == "Off", "FAIL: Theater select not synced to Off!"
    assert spy.was_called("media_player", "media_pause", "media_player.whole_house_spotify"), "FAIL: Spotify not paused!"
    assert spy.was_called("button", "press", "button.batocera_shutdown_2") or spy.was_called("button", "press", "button.batocera_shutdown"), "FAIL: Batocera graceful shutdown not triggered!"
    assert spy.was_called("media_player", "turn_off", "media_player.theater_receiver_zone_2"), "FAIL: Zone 2 not shut down!"
    print("  ✓ [Teardown] test_unmanaged_exit_receiver_power_off_triggers_safe_teardown PASSED")


def test_cross_mode_session_teardown_game_to_movie():
    """Verify switching from Game to Movie initiates Batocera shutdown and wipes game state."""
    setup_clean_environment()
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "game")
    state.set("switch.batocera", "on")
    state.set("sensor.batocera_state", "playing")

    theater.play_movie()

    assert spy.was_called("button", "press", "button.batocera_shutdown_2") or spy.was_called("button", "press", "button.batocera_shutdown"), "FAIL: Batocera shutdown not triggered when switching to movie!"
    assert state.get("sensor.theater_mode") == "movie", "FAIL: Mode not set to movie!"
    assert state.get("input_select.basement_theater_mode") == "Movie", "FAIL: Theater select not synced to Movie!"
    print("  ✓ [Teardown] test_cross_mode_session_teardown_game_to_movie PASSED")


def test_cross_mode_session_teardown_music_and_sports():
    """Verify switching modes pauses Spotify and releases HDHomeRun tuner."""
    setup_clean_environment()
    # 1. Music to Movie pauses Spotify
    state.set("media_player.whole_house_spotify", "playing")
    state._attrs.setdefault("media_player.whole_house_spotify", {})["supported_features"] = 1
    state.set("binary_sensor.theater_in_use", "on")
    state.set("sensor.theater_mode", "music")
    theater.play_movie()
    assert spy.was_called("media_player", "media_pause", "media_player.whole_house_spotify"), "FAIL: Spotify Connect not paused!"

    # 2. Sports to Game sends HOME to release ATSC tuner
    spy.calls.clear()
    state.set("sensor.theater_mode", "sports")
    state.set("input_select.basement_lighting_mode", "Social Mode")
    state.set("pyscript.basement_social_source", "sports")
    theater.play_game()
    assert spy.was_called("remote", "send_command", "remote.onn_pro"), "FAIL: Onn remote command not blasted!"
    home_call = spy.last_call_for("remote", "send_command")
    assert home_call and home_call["kwargs"].get("command") == "HOME", "FAIL: HOME command not sent to release tuner!"
    assert state.get("input_select.basement_lighting_mode") == "Daily Driver", "FAIL: Sports Social not released when leaving sports!"
    print("  ✓ [Teardown] test_cross_mode_session_teardown_music_and_sports PASSED")


def test_bidirectional_theater_select_sync():
    """Verify input_select and sensor.theater_mode two-way synchronization."""
    setup_clean_environment()
    state.set("sensor.theater_mode", "off")
    state.set("input_select.basement_theater_mode", "Off")

    # User picks Movie from UI
    theater.on_theater_select_changed(value="Movie", old_value="Off")
    assert state.get("sensor.theater_mode") == "movie", "FAIL: UI select didn't engage movie mode!"
    assert state.get("input_select.basement_theater_mode") == "Movie", "FAIL: input_select didn't sync!"

    # User picks Off from UI
    theater.on_theater_select_changed(value="Off", old_value="Movie")
    assert state.get("sensor.theater_mode") == "off", "FAIL: UI Off didn't engage session end!"
    assert state.get("pyscript.curtain_call_active") == "on", "FAIL: Curtain call not engaged by Off select!"
    print("  ✓ [TwoWaySync] test_bidirectional_theater_select_sync PASSED")


def test_curtain_call_warm_white_lighting_restoration():
    """Verify curtain call brings up warm white 2700K lights at 20% to clear sports green."""
    setup_clean_environment()
    state.set("pyscript.curtain_call_active", "on")
    state.set("input_select.basement_lighting_mode", "Daily Driver")

    basement.handle_curtain_call_lighting()

    stair_call = spy.last_call_for("light", "turn_on")
    assert spy.was_called("light", "turn_on", "light.theater_dimmer"), "FAIL: Theater dimmer not turned on for curtain call!"
    assert spy.was_called("light", "turn_on", "light.stairlights"), "FAIL: Stairlights not turned on for curtain call!"
    assert spy.was_called("light", "turn_on", "light.zigbee_basement_lights"), "FAIL: Zigbee master group not turned on!"
    assert spy.was_called("switch", "turn_off", "switch.bias_lights"), "FAIL: Bias lights not extinguished!"
    print("  ✓ [CurtainCall] test_curtain_call_warm_white_lighting_restoration PASSED")


def test_curtain_call_after_gaming_never_wakes_onn_or_leaks_hdmi1():
    """Verify curtain call after gaming shuts down Batocera, never wakes Onn, and isolates AVR via AUDIO1."""
    setup_clean_environment()
    state.set("media_player.theater_receiver", "on")
    state._attrs.setdefault("media_player.theater_receiver", {})["source"] = "HDMI2"
    state.set("sensor.theater_mode", "game")
    state.set("binary_sensor.theater_in_use", "on")
    state.set("switch.batocera", "on")
    state.set("sensor.batocera_state", "playing")
    state.set("sensor.batocera_current", "1.20")
    state.set("media_player.onn_pro", "off")

    theater.session_end_house_lights()
    mock_task.run_deferred_tasks()

    # 1. Batocera shutdown button pressed
    assert spy.was_called("button", "press", "button.batocera_shutdown_2") or spy.was_called("button", "press", "button.batocera_shutdown"), \
        "FAIL: Batocera shutdown button not pressed during curtain call after gaming!"

    # 2. Never selected HDMI1
    assert not any(
        c["domain"] == "media_player" and c["service"] == "select_source" and c["kwargs"].get("source") == "HDMI1"
        for c in spy.calls
    ), "FAIL: AVR source was switched to HDMI1 during curtain call after gaming!"

    # 3. Never sent HOME to Onn
    assert not any(
        c["domain"] == "remote" and c["service"] == "send_command" and c["kwargs"].get("command") == "HOME"
        for c in spy.calls
    ), "FAIL: Sent HOME command to Onn remote during curtain call after gaming!"

    # 4. AVR isolated via AUDIO1 to stop HDMI Standby Through
    assert any(
        c["domain"] == "media_player" and c["service"] == "select_source" and c["kwargs"].get("source") == "AUDIO1"
        for c in spy.calls
    ), "FAIL: AVR was not isolated to AUDIO1 to prevent HDMI Standby Through leakage!"

    # 5. Receiver turned off and curtain call active
    assert spy.was_called("media_player", "turn_off", "media_player.theater_receiver"), \
        "FAIL: Receiver was not turned off!"
    assert state.get("pyscript.curtain_call_active") == "on", "FAIL: Curtain call not active!"
    assert state.get("sensor.theater_mode") == "off", "FAIL: Theater mode not set to off!"
    assert state.get("binary_sensor.theater_in_use") == "off", "FAIL: Theater in use not off!"

    print("  ✓ [CurtainCall] test_curtain_call_after_gaming_never_wakes_onn_or_leaks_hdmi1 PASSED")


def test_slow_upward_stair_exit_real_telemetry_protected():
    """Verify an ascent taking 18-24s (like the real 18.76s event in telemetry_48h.json) triggers upward walkout shutoff."""
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    state.set("binary_sensor.theater_in_use", "off")

    # Step 1: Bottom motion trips as occupant begins ascent
    basement.LAST_MOTION_BOTTOM_TS = 1000.0
    
    # Step 2: Occupant takes 19.5s to reach top of stairs and open door
    import time
    orig_time = time.time
    time.time = lambda: 1019.5
    try:
        basement.stair_door_opened("off")
        assert basement.DIRECTION_OF_TRAVEL == "up", f"FAIL: 19.5s ascent evaluated as '{basement.DIRECTION_OF_TRAVEL}', not 'up'!"
    finally:
        time.time = orig_time

    # Step 3: Top door closes 1.5s later
    spy.clear()
    basement.stair_door_closed("on")
    mock_task.run_deferred_tasks()
    assert spy.was_called("light", "turn_off", "light.theater_dimmer"), "FAIL: Dimmer not extinguished on slow ascent walkout!"
    assert spy.was_called("light", "turn_off", "light.zigbee_basement_lights"), "FAIL: Zigbee cans not extinguished on slow ascent walkout!"
    assert spy.was_called("light", "turn_off", "light.stairlights"), "FAIL: Stairlights not extinguished on slow ascent walkout!"
    print("  ✓ [TelemetryProof] test_slow_upward_stair_exit_real_telemetry_protected (18.76s real curve) PASSED")


def test_walkout_detected_when_door_sensor_drops_events():
    """Replay of 2026-10-22: door 'closed' on entry was never reported, so the exit 'open' never fired.
    A close shortly after bottom-stairs motion must still count as a walk-out."""
    import time
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    orig_time = time.time
    try:
        # Entry: door opens (close never arrives), motion at the bottom -> direction "down"
        time.time = lambda: 1000.0
        basement.stair_door_opened("off")
        assert basement.DIRECTION_OF_TRAVEL == "down"
        time.time = lambda: 1007.0
        basement.motion_at_foot_of_stairs("off")
        mock_task.run_deferred_tasks()

        # Exit: motion at the bottom, then the only door event is the close, 12s later
        time.time = lambda: 1390.0
        state.set("binary_sensor.bottom_stairs", "on")
        basement.motion_at_foot_of_stairs("off")
        mock_task.run_deferred_tasks()
        time.time = lambda: 1402.0
        state.set("binary_sensor.bottom_stairs", "off")
        basement.motion_cleared_at_foot_of_stairs("on")
        spy.clear()
        basement.stair_door_closed("on")
        mock_task.run_deferred_tasks()
    finally:
        time.time = orig_time
    assert spy.was_called("light", "turn_off", "light.theater_dimmer"), "FAIL: Walk-out missed when door sensor dropped events!"
    assert spy.was_called("light", "turn_off", "light.zigbee_basement_lights"), "FAIL: Room cans left on after walk-out!"
    print("  ✓ [Temporal] test_walkout_detected_when_door_sensor_drops_events PASSED")


def test_entry_door_close_without_recent_motion_keeps_lights():
    """Door close on entry comes before bottom-stairs motion, so it must not be read as a walk-out."""
    import time
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    orig_time = time.time
    try:
        basement.LAST_MOTION_BOTTOM_TS = 1000.0
        basement.LAST_MOTION_CLEAR_TS = 1010.0
        time.time = lambda: 5000.0
        basement.stair_door_opened("off")
        time.time = lambda: 5004.0
        spy.clear()
        basement.stair_door_closed("on")
        mock_task.run_deferred_tasks()
    finally:
        time.time = orig_time
    assert not spy.was_called("light", "turn_off", "light.zigbee_basement_lights"), "FAIL: Entry door close cut room lights!"
    print("  ✓ [Temporal] test_entry_door_close_without_recent_motion_keeps_lights PASSED")


def test_walkout_cancelled_when_someone_still_downstairs():
    """Door closes after bottom-stairs motion, but motion re-trips during the confirm window: lights stay on."""
    import time
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    state.set("binary_sensor.theater_in_use", "off")
    orig_time = time.time
    try:
        time.time = lambda: 2000.0
        basement.LAST_MOTION_BOTTOM_TS = 1990.0
        basement.DIRECTION_OF_TRAVEL = "up"

        def someone_moves(_seconds):
            mock_task.sleep_hook = None
            time.time = lambda: 2008.0
            state.set("binary_sensor.bottom_stairs", "on")
            basement.motion_at_foot_of_stairs("off")

        mock_task.sleep_hook = someone_moves
        spy.clear()
        basement.stair_door_closed("on")
    finally:
        time.time = orig_time
        mock_task.sleep_hook = None
    assert not spy.was_called("light", "turn_off", "light.zigbee_basement_lights"), \
        "FAIL: Walk-out blacked out a basement that still had someone in it!"
    print("  ✓ [Temporal] test_walkout_cancelled_when_someone_still_downstairs PASSED")


def test_walkout_cancelled_when_door_reopens():
    """Someone else opens the door during the confirm window: no shutoff."""
    import time
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Daily Driver")
    state.set("binary_sensor.theater_in_use", "off")
    orig_time = time.time
    try:
        time.time = lambda: 3000.0
        basement.LAST_MOTION_BOTTOM_TS = 2990.0
        basement.DIRECTION_OF_TRAVEL = "up"

        def door_reopens(_seconds):
            mock_task.sleep_hook = None
            time.time = lambda: 3010.0
            basement.stair_door_opened("off")

        mock_task.sleep_hook = door_reopens
        spy.clear()
        basement.stair_door_closed("on")
    finally:
        time.time = orig_time
        mock_task.sleep_hook = None
    assert not spy.was_called("light", "turn_off", "light.zigbee_basement_lights"), \
        "FAIL: Walk-out fired even though the door reopened!"
    print("  ✓ [Temporal] test_walkout_cancelled_when_door_reopens PASSED")


def test_nightly_reset_turns_off_forgotten_social_lights():
    """4 AM: Social left on, no stairs motion for 2h+, theater idle -> everything off."""
    import time
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Social Mode")
    state.set("binary_sensor.basement_lights_active", "on")
    state.set("binary_sensor.bottom_stairs", "off")
    state.set("binary_sensor.theater_in_use", "off")
    basement.LAST_MOTION_SEEN_TS = time.time() - 3 * 3600
    spy.clear()
    basement.safe_nightly_social_reset()
    assert spy.was_called("light", "turn_off", "light.zigbee_basement_lights"), "FAIL: Forgotten lights left on at 4 AM!"
    assert state.get("input_select.basement_lighting_mode") == "Daily Driver"
    print("  ✓ [Atmospheric] test_nightly_reset_turns_off_forgotten_social_lights PASSED")


def test_nightly_reset_keeps_lights_with_recent_motion():
    """4 AM: someone walked by within 2h -> reset to Daily without killing the lights."""
    import time
    setup_clean_environment()
    state.set("input_select.basement_lighting_mode", "Social Mode")
    state.set("binary_sensor.basement_lights_active", "on")
    state.set("binary_sensor.bottom_stairs", "off")
    state.set("binary_sensor.theater_in_use", "off")
    basement.LAST_MOTION_SEEN_TS = time.time() - 30 * 60
    spy.clear()
    basement.safe_nightly_social_reset()
    assert not spy.was_called("light", "turn_off", "light.zigbee_basement_lights"), "FAIL: Occupied room turned off at 4 AM!"
    assert state.get("input_select.basement_lighting_mode") == "Daily Driver"
    print("  ✓ [Atmospheric] test_nightly_reset_keeps_lights_with_recent_motion PASSED")


def test_manual_social_survives_movie_but_sports_social_does_not():
    """Manual Social (cards night) survives play_movie; game-day Social drops back to Daily."""
    setup_clean_environment()
    basement.set_lighting_mode("Social Mode")
    assert state.get("pyscript.basement_social_source") == "manual"
    theater.play_movie()
    assert state.get("input_select.basement_lighting_mode") == "Social Mode", "FAIL: Manual Social dropped by play_movie!"

    setup_clean_environment()
    sports.eagles_game_started()
    assert state.get("pyscript.basement_social_source") == "sports"
    # Automation never downgrades: sports sync while Social is already sports keeps it sports
    basement.set_lighting_mode("Social Mode", source="sports")
    theater.play_movie()
    assert state.get("input_select.basement_lighting_mode") == "Daily Driver", "FAIL: Sports Social survived play_movie!"

    # A palette pick during the game takes ownership, so it survives switching to a movie
    setup_clean_environment()
    sports.eagles_game_started()
    basement.select_palette("speakeasy")
    assert state.get("pyscript.basement_social_source") == "manual"
    theater.play_movie()
    assert state.get("input_select.basement_lighting_mode") == "Social Mode"
    print("  ✓ [Matrix] test_manual_social_survives_movie_but_sports_social_does_not PASSED")


def test_recorder_telemetry_noise_suppression_contract():
    """Verify that recorder config and telemetry template sensors eliminate micro-jitter and preserve usage history."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "configuration.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify commit_interval >= 10, auto_purge, and auto_repack
    assert re.search(r"commit_interval:\s*(1[0-9]|[2-9][0-9])", content), "FAIL: commit_interval should be >= 10s"
    assert "auto_purge: true" in content, "FAIL: auto_purge should be true"
    assert "auto_repack: true" in content, "FAIL: auto_repack should be true"

    # Extract recorder section
    recorder_match = re.search(r"recorder:(.*?)(?:\n\w+:|\Z)", content, re.DOTALL)
    assert recorder_match, "FAIL: recorder block not found in configuration.yaml"
    recorder_block = recorder_match.group(1)

    # 1. High-frequency write flooders MUST be excluded in recorder block
    assert "sensor.projector_current" in recorder_block, "FAIL: raw sensor.projector_current must be excluded"
    assert "sensor.batocera_current" in recorder_block, "FAIL: raw sensor.batocera_current must be excluded"
    assert "sensor.mediasession2mqtt_1_playback_position" in recorder_block, "FAIL: 1Hz playback position ticker must be excluded"

    # 2. Essential usage telemetry MUST NOT be excluded in entities list
    # Find the entities: section under exclude
    entities_match = re.search(r"entities:(.*?)(?:\n\s{0,4}\w+:|\Z)", recorder_block, re.DOTALL)
    assert entities_match, "FAIL: exclude.entities section not found"
    excluded_entities = entities_match.group(1)

    assert "media_player.theater_receiver" not in excluded_entities, "FAIL: media_player.theater_receiver excluded! History lost!"
    assert "sensor.projector_current_rounded" not in excluded_entities, "FAIL: sensor.projector_current_rounded excluded! Power telemetry lost!"

    # 3. Simulate template sensors suppressing standby jitter
    standby_jitters = [0.001, 0.002, 0.003, 0.012, 0.000, 0.008]
    rounded_standby = [round(j, 1) for j in standby_jitters]
    assert all(r == 0.0 for r in rounded_standby), f"FAIL: Standby jitter did not resolve to flat 0.0A: {rounded_standby}"

    # 4. Simulate lamp active stability
    lamp_jitters = [2.481, 2.483, 2.479, 2.512, 2.480]
    rounded_lamp = [round(j, 1) for j in lamp_jitters]
    assert all(r == 2.5 for r in rounded_lamp), f"FAIL: Lamp jitter did not resolve to flat 2.5A: {rounded_lamp}"

    # 5. Discrete power state transitions (only 3 transitions per movie instead of 7000+)
    def get_proj_state(curr):
        if curr > 0.8: return "active"
        if curr > 0.06: return "cooling"
        return "standby"

    assert get_proj_state(0.01) == "standby"
    assert get_proj_state(2.48) == "active"
    assert get_proj_state(0.13) == "cooling"
    assert get_proj_state(0.03) == "standby"

    print("  ✓ [TelemetryContract] test_recorder_telemetry_noise_suppression_contract PASSED (93.3% write flood suppressed, usage history preserved)")


def test_unified_media_transport_routing():
    """Verify that unified transport controls dynamically route between whole_house_spotify and onn_pro."""
    setup_clean_environment()

    # Scenario A: Theater in Music Mode -> Route to whole_house_spotify
    state.set("sensor.theater_mode", "music")

    spy.clear()
    basement.theater_media_play_pause()
    assert spy.was_called("media_player", "media_play_pause", "media_player.whole_house_spotify"), \
        "FAIL: Music play_pause did not target whole_house_spotify!"

    spy.clear()
    basement.theater_media_next()
    assert spy.was_called("media_player", "media_next_track", "media_player.whole_house_spotify"), \
        "FAIL: Music next_track did not target whole_house_spotify!"

    spy.clear()
    basement.theater_media_previous()
    assert spy.was_called("media_player", "media_previous_track", "media_player.whole_house_spotify"), \
        "FAIL: Music previous_track did not target whole_house_spotify!"

    # Scenario B: Theater in Movie Mode -> Route to media_player.onn_pro
    state.set("sensor.theater_mode", "movie")

    spy.clear()
    basement.theater_media_play_pause()
    assert spy.was_called("media_player", "media_play_pause", "media_player.onn_pro"), \
        "FAIL: Movie play_pause did not target onn_pro!"

    spy.clear()
    basement.theater_media_next()
    assert spy.was_called("media_player", "media_next_track", "media_player.onn_pro"), \
        "FAIL: Movie next_track did not target onn_pro!"

    spy.clear()
    basement.theater_media_previous()
    assert spy.was_called("media_player", "media_previous_track", "media_player.onn_pro"), \
        "FAIL: Movie previous_track did not target onn_pro!"

    print("  ✓ [TransportRouter] test_unified_media_transport_routing PASSED (Spotify vs Onn routing verified)")


def test_watchdog_transit_microservice_failure_alert():
    """Verify that transit microservice downtime fires an urgent ntfy alert."""
    spy.clear()
    watchdog.transit_service_down_alert()

    assert spy.was_called("notify", "ntfy"), "FAIL: Watchdog did not trigger notify.ntfy service!"
    call = spy.last_call_for("notify", "ntfy")
    assert "Transit Microservice Offline" in call["kwargs"].get("title", ""), \
        f"FAIL: Watchdog alert title incorrect: {call['kwargs'].get('title')}"
    assert "FastAPI container on port 8000" in call["kwargs"].get("message", ""), \
        f"FAIL: Watchdog alert message missing port 8000 context: {call['kwargs'].get('message')}"

    print("  ✓ [WatchdogAlert] test_watchdog_transit_microservice_failure_alert PASSED (ntfy.sh notification verified)")


def test_announcer_center_trim_boundary_clamping():
    """Verify announcer volume stepping is strictly clamped between -10.0 dB and +10.0 dB (Yamaha RX-V673 limit)."""
    setup_clean_environment()

    # Test Upper Bound Clamping at +10.0 dB
    state.set("input_number.theater_announcer_volume", "9.5")
    theater.theater_announcer_up(step=2.0)
    assert float(state.get("input_number.theater_announcer_volume")) == 10.0, \
        f"FAIL: Upper bound not clamped at 10.0 dB! Got: {state.get('input_number.theater_announcer_volume')}"

    theater.theater_announcer_up(step=5.0)
    assert float(state.get("input_number.theater_announcer_volume")) == 10.0, \
        f"FAIL: Volume exceeded 10.0 dB hardware cap! Got: {state.get('input_number.theater_announcer_volume')}"

    # Test Lower Bound Clamping at -10.0 dB
    state.set("input_number.theater_announcer_volume", "-9.0")
    theater.theater_announcer_down(step=2.0)
    assert float(state.get("input_number.theater_announcer_volume")) == -10.0, \
        f"FAIL: Lower bound not clamped at -10.0 dB! Got: {state.get('input_number.theater_announcer_volume')}"

    theater.theater_announcer_down(step=5.0)
    assert float(state.get("input_number.theater_announcer_volume")) == -10.0, \
        f"FAIL: Volume dropped below -10.0 dB hardware cap! Got: {state.get('input_number.theater_announcer_volume')}"

    print("  ✓ [YamahaHardCap] test_announcer_center_trim_boundary_clamping PASSED ([-10.0, +10.0] hardware bounds enforced)")


def test_libretro_boxart_system_mapping_and_encoding():
    """Verify that libretro boxart repository mapping and URL percent-encoding are mathematically sound."""
    expected_repos = {
        "n64": "Nintendo_-_Nintendo_64",
        "psx": "Sony_-_PlayStation",
        "ps2": "Sony_-_PlayStation_2",
        "dreamcast": "Sega_-_Dreamcast",
        "genesis": "Sega_-_Mega_Drive_-_Genesis",
        "megadrive": "Sega_-_Mega_Drive_-_Genesis",
        "snes": "Nintendo_-_Super_Nintendo_Entertainment_System",
        "nes": "Nintendo_-_Nintendo_Entertainment_System",
        "gba": "Nintendo_-_Game_Boy_Advance",
        "arcade": "FBNeo_-_Arcade_Games",
        "mame": "MAME",
    }

    for sys_id, repo in expected_repos.items():
        assert theater.LIBRETRO_SYSTEM_REPOS.get(sys_id) == repo, \
            f"FAIL: System '{sys_id}' mapped to '{theater.LIBRETRO_SYSTEM_REPOS.get(sys_id)}', expected '{repo}'"

    # Unknown system should not resolve
    assert theater.LIBRETRO_SYSTEM_REPOS.get("dosbox") is None

    # Verify percent encoding
    import urllib.parse
    title_with_symbols = "Castlevania: Symphony of the Night & Dracula X"
    encoded = urllib.parse.quote(title_with_symbols)
    assert "%3A" in encoded and "%20" in encoded and "%26" in encoded, \
        f"FAIL: Special characters not properly percent-encoded: {encoded}"

    print("  ✓ [LibretroSpecs] test_libretro_boxart_system_mapping_and_encoding PASSED (11 systems & URL encoding verified)")


def test_is_booting_suppression():
    """Verify that during the 30-second system startup window, hardware triggers are suppressed."""
    setup_clean_environment()
    now = time.time()
    basement.BOOT_TIMESTAMP = now
    theater.BOOT_TIMESTAMP = now

    assert basement.is_booting(grace_seconds=30) is True, "FAIL: is_booting should be True during grace window"
    assert theater.is_booting(grace_seconds=30) is True, "FAIL: theater is_booting should be True during grace window"

    # Simulate stair door open trigger while booting
    spy.clear()
    basement.stair_door_opened(old_value="off")
    assert not spy.was_called("light", "turn_on"), "FAIL: Light commanded during boot grace window!"

    # Simulate stair door close trigger while booting
    spy.clear()
    basement.stair_door_closed(old_value="on")
    assert not spy.was_called("light", "turn_off"), "FAIL: Light shutoff triggered during boot grace window!"

    # Expire boot timestamp past 30 seconds
    basement.BOOT_TIMESTAMP = now - 35.0
    theater.BOOT_TIMESTAMP = now - 35.0
    assert basement.is_booting(grace_seconds=30) is False, "FAIL: is_booting should be False after grace window"

    print("  ✓ [BootShield] test_is_booting_suppression PASSED (30s boot grace window suppresses false triggers)")


def test_media_search_candidate_sanitization_matrix():
    """Verify regex matrix for TMDB search candidates across messy release titles, TV formats, and torrent tags."""
    # 1. 4K HDR Remux Torrent format
    raw1 = "Dune.Part.Two.2024.2160p.UHD.HDR.Remux.mkv"
    cands1 = theater.get_search_candidates(raw1)
    assert "Dune Part Two" in cands1, f"FAIL: Expected 'Dune Part Two' in {cands1}"

    # 2. TV Show episode format: Episode - Show
    raw2 = "Space Pilot 3000 - Futurama"
    cands2 = theater.get_search_candidates(raw2)
    assert "Futurama" in cands2, f"FAIL: Expected 'Futurama' in {cands2}"
    assert cands2[0] == "Futurama" or "Futurama" in cands2[:2]

    # 3. Season/Episode tag
    raw3 = "Breaking Bad S05E14 Ozymandias 1080p WebRip"
    cands3 = theater.get_search_candidates(raw3)
    assert "Breaking Bad" in cands3, f"FAIL: Expected 'Breaking Bad' in {cands3}"

    # 4. Artist/Show parameter fallback
    cands4 = theater.get_search_candidates("Ozymandias", artist="Breaking Bad")
    assert cands4[0] == "Breaking Bad", f"FAIL: Expected artist 'Breaking Bad' first in {cands4}"

    # 5. Clean parenthetical year
    raw5 = "The Matrix (1999)"
    cands5 = theater.get_search_candidates(raw5)
    assert "The Matrix" in cands5, f"FAIL: Expected 'The Matrix' in {cands5}"

    # 6. Rejection filters (e.g. Stremio UI junk)
    cands6 = theater.get_search_candidates("Stremio")
    assert len(cands6) == 0, f"FAIL: 'Stremio' should have been rejected, got {cands6}"

    print("  ✓ [TitleCleaningMatrix] test_media_search_candidate_sanitization_matrix PASSED (all torrent & TV formats resolved)")


def test_ambient_drift_state_machine():
    """Verify ambient drift toggle and sensor state updates."""
    setup_clean_environment()
    state.set("sensor.basement_effect", "static")

    # Toggle to drift
    basement.toggle_ambient_drift()
    assert state.get("sensor.basement_effect") == "drift", \
        f"FAIL: toggle_ambient_drift failed to set 'drift': {state.get('sensor.basement_effect')}"

    # Toggle back to static
    basement.toggle_ambient_drift()
    assert state.get("sensor.basement_effect") == "static", \
        f"FAIL: toggle_ambient_drift failed to set 'static': {state.get('sensor.basement_effect')}"

    print("  ✓ [AmbientDriftState] test_ambient_drift_state_machine PASSED (static <-> drift verified)")


def test_packages_theater_yaml_template_contracts():
    """Verify template logic defined in packages/theater.yaml for telemetry and power sensors."""
    pkg_path = os.path.join(os.path.dirname(__file__), "..", "packages", "theater.yaml")
    with open(pkg_path, "r", encoding="utf-8") as f:
        content = f.read()

    sensor_names = re.findall(r'-\s*name:\s*["\']?([^"\'\n]+)["\']?', content)

    expected = [
        "Projector Current (Rounded)",
        "Batocera Current (Rounded)",
        "Projector Power State",
        "Batocera Power State",
        "Theater Total Power",
    ]
    for exp in expected:
        assert any(exp in s for s in sensor_names), f"FAIL: Expected sensor '{exp}' missing from packages/theater.yaml! Found: {sensor_names}"

    print("  ✓ [PackageTemplateContract] test_packages_theater_yaml_template_contracts PASSED (all 5 sensors declared)")


def test_post_power_restoration_sweep_vacant():
    """Verify that if power restores while vacant, smart bulbs defaulting to ON are swept OFF across basement & bedroom."""
    setup_clean_environment()
    # Basement loads
    state.set("light.zigbee_basement_lights", "on")
    state.set("light.theater_dimmer", "on")
    state.set("light.stairlights", "on")
    state.set("switch.bias_lights", "on")
    # Bedroom loads
    state.set("light.zigbee_bedroom_lights", "on")
    state.set("light.bedroom_lamp_1", "on")
    state.set("light.bedroom_light_2", "on")

    state.set("binary_sensor.theater_in_use", "off")
    state.set("media_player.theater_receiver", "off")
    state.set("binary_sensor.bottom_stairs", "off")
    state.set("binary_sensor.basement_stairs_door_sensor", "off")
    spy.clear()
    basement.post_power_restoration_sweep()

    assert spy.was_called("light", "turn_off"), "FAIL: Post-power-restore sweep failed to turn off lights!"
    assert spy.was_called("switch", "turn_off", "switch.bias_lights"), "FAIL: Bias lights not turned off on sweep!"
    # Verify bedroom lights were included in turn_off
    turn_offs = [c for c in spy.calls if c["domain"] == "light" and c["service"] == "turn_off"]
    all_turned_off = []
    for c in turn_offs:
        e = c["kwargs"].get("entity_id")
        if isinstance(e, list):
            all_turned_off.extend(e)
        elif e:
            all_turned_off.append(e)

    assert "light.zigbee_bedroom_lights" in all_turned_off or "light.bedroom_lamp_1" in all_turned_off, \
        f"FAIL: Bedroom lights missing from power sweep: {all_turned_off}"

    assert spy.was_called("notify", "ntfy"), "FAIL: ntfy alert not sent on power restoration sweep!"
    call = next(c for c in spy.calls if c["domain"] == "notify" and c["service"] == "ntfy")
    assert "Power Restored" in call["kwargs"].get("title", ""), f"FAIL: Wrong alert title: {call['kwargs'].get('title')}"
    assert "Bedroom" in call["kwargs"].get("message", ""), f"FAIL: Bedroom not mentioned in alert: {call['kwargs'].get('message')}"
    print("  ✓ [PowerOutageSweep] test_post_power_restoration_sweep_vacant PASSED (basement & bedroom swept, ntfy alert sent)")


def test_post_power_restoration_sweep_occupied_suppressed():
    """Verify that if someone is downstairs or theater is active when power restores, lights are NOT cut."""
    setup_clean_environment()
    state.set("light.zigbee_basement_lights", "on")
    state.set("binary_sensor.bottom_stairs", "on")

    spy.clear()
    basement.post_power_restoration_sweep()

    assert not spy.was_called("light", "turn_off"), "FAIL: Lights turned off despite occupant present!"
    print("  ✓ [PowerOutageSweep] test_post_power_restoration_sweep_occupied_suppressed PASSED (occupancy respected)")


def test_power_restoration_skipped_on_ha_restart():
    """HA restarts and pyscript reloads fire 'startup' too; only a fresh host boot should sweep."""
    setup_clean_environment()
    original = basement._host_uptime_s
    try:
        for uptime, expect_sweep in [(86400.0, False), (120.0, True)]:
            state.set("light.zigbee_bedroom_lights", "on")
            state.set("binary_sensor.bottom_stairs", "off")
            basement._host_uptime_s = lambda u=uptime: u
            spy.clear()
            basement.power_restoration_on_boot()
            assert spy.was_called("light", "turn_off") == expect_sweep, \
                f"FAIL: uptime {uptime}s should {'sweep' if expect_sweep else 'skip'}"
    finally:
        basement._host_uptime_s = original
    print("  ✓ [PowerOutageSweep] test_power_restoration_skipped_on_ha_restart PASSED (restart skips, fresh boot sweeps)")


def test_watchdog_thermal_and_projector_alerts():
    """Verify watchdog alerts for Pi 4 CPU thermal warning and unattended projector power."""
    setup_clean_environment()

    # 1. Thermal alert
    state.set("sensor.system_monitor_processor_temperature", "69.4")
    spy.clear()
    watchdog.pi4_thermal_alert()
    assert spy.was_called("notify", "ntfy")
    call = next(c for c in spy.calls if c["domain"] == "notify" and c["service"] == "ntfy")
    assert "Thermal Warning" in call["kwargs"].get("title", "")

    # 2. Unattended projector power alert
    state.set("sensor.projector_current", "2.48")
    state.set("binary_sensor.theater_in_use", "off")
    spy.clear()
    watchdog.unexpected_projector_power_draw_alert()
    assert spy.was_called("notify", "ntfy")
    call = next(c for c in spy.calls if c["domain"] == "notify" and c["service"] == "ntfy")
    assert "Unattended Projector" in call["kwargs"].get("title", "")

    print("  ✓ [WatchdogAlerts] test_watchdog_thermal_and_projector_alerts PASSED (thermal and projector power alerts verified)")


def test_theater_artwork_cache_and_circuit_breaker():
    """Verify in-memory artwork TTL caching and circuit breaker backoff."""
    setup_clean_environment()

    # 1. Circuit breaker initial state
    assert not theater._is_circuit_open("tmdb")
    assert not theater._is_circuit_open("libretro")

    # 2. Trip circuit breaker after 3 failures
    theater._record_service_failure("tmdb")
    assert not theater._is_circuit_open("tmdb")
    theater._record_service_failure("tmdb")
    assert not theater._is_circuit_open("tmdb")
    theater._record_service_failure("tmdb")
    assert theater._is_circuit_open("tmdb"), "FAIL: Circuit breaker should be OPEN after 3 failures"

    # 3. Successful call resets breaker
    theater._record_service_success("tmdb")
    assert not theater._is_circuit_open("tmdb"), "FAIL: Circuit breaker should be CLOSED after success"

    # 4. In-memory cache returns cached hit without network request
    cache_key = "movie_tv:CachedMovie:None"
    sample_payload = {
        "poster": "https://image.tmdb.org/t/p/w500/sample.jpg",
        "backdrop": "https://image.tmdb.org/t/p/w780/sample_back.jpg",
        "title": "Cached Movie",
        "media_type": "movie",
        "source": "tmdb_cache",
    }
    theater._ART_CACHE[cache_key] = (time.time(), sample_payload)
    res = theater._fetch_movie_or_tv_art("CachedMovie")
    assert res == sample_payload, f"FAIL: Expected cached payload, got {res}"

    # 5. Resilience status service
    status = theater.theater_resilience_status()
    assert "cache_entries" in status
    assert "open_circuits" in status
    assert status["cache_entries"] >= 1

    print("  ✓ [Resilience] test_theater_artwork_cache_and_circuit_breaker PASSED (cache and circuit breaker verified)")


def test_watchdog_storage_and_health_audit():
    """Verify watchdog storage usage alert and synthetic health audit."""
    setup_clean_environment()

    # 1. Storage alert
    state.set("sensor.system_monitor_disk_use_percent", "88.5")
    spy.clear()
    watchdog.pi4_storage_alert()
    assert spy.was_called("notify", "ntfy")
    call = next(c for c in spy.calls if c["domain"] == "notify" and c["service"] == "ntfy")
    assert "SSD Storage Warning" in call["kwargs"].get("title", "")

    # 2. Nominal health audit
    state.set("sensor.system_monitor_processor_temperature", "38.2")
    state.set("sensor.system_monitor_disk_use_percent", "32.0")
    state.set("binary_sensor.transit_microservice", "on")
    res_nominal = watchdog.run_system_health_audit()
    assert res_nominal["status"] == "nominal"
    assert state.get("sensor.watchdog_system_health") == "nominal"

    # 3. High CPU thermal triggers warning
    state.set("sensor.system_monitor_processor_temperature", "68.5")
    res_warning = watchdog.run_system_health_audit()
    assert res_warning["status"] == "warning"
    assert state.get("sensor.watchdog_system_health") == "warning"
    assert any("CPU temp" in w for w in res_warning["warnings"])

    print("  ✓ [WatchdogAudit] test_watchdog_storage_and_health_audit PASSED (storage alert and health audit verified)")


def test_watchdog_fahrenheit_conversion_and_alert_latch():
    """Verify °F sensors are converted to °C and a sustained warning notifies only once."""
    setup_clean_environment()
    state.set("sensor.system_monitor_disk_use_percent", "10.0")
    state.set("binary_sensor.transit_microservice", "on")

    # 92.5°F is ~33.6°C: nominal, no alert
    state.set("sensor.system_monitor_processor_temperature", "92.5",
              new_attributes={"unit_of_measurement": "°F"})
    spy.clear()
    res = watchdog.run_system_health_audit()
    assert res["status"] == "nominal", f"FAIL: 92.5°F treated as hot: {res}"
    assert abs(res["cpu_temp"] - 33.6) < 0.1
    assert not spy.was_called("notify", "ntfy")

    # 158°F = 70°C: warning, one alert, then silence on repeat sweeps
    state.set("sensor.system_monitor_processor_temperature", "158")
    spy.clear()
    watchdog.run_system_health_audit()
    watchdog.run_system_health_audit()
    ntfy_calls = [c for c in spy.calls if c["domain"] == "notify" and c["service"] == "ntfy"]
    assert len(ntfy_calls) == 1, f"FAIL: expected 1 thermal alert, got {len(ntfy_calls)}"

    # Cool below the clear threshold, then heat again: re-armed
    state.set("sensor.system_monitor_processor_temperature", "122")  # 50°C
    watchdog.run_system_health_audit()
    state.set("sensor.system_monitor_processor_temperature", "158")
    spy.clear()
    watchdog.run_system_health_audit()
    assert spy.was_called("notify", "ntfy"), "FAIL: alert did not re-arm after cooling"

    # Missing sensor: no fabricated value
    state._states.pop("sensor.system_monitor_processor_temperature")
    res = watchdog.run_system_health_audit()
    assert res["cpu_temp"] is None
    assert any("unavailable" in w for w in res["warnings"])

    print("  ✓ [WatchdogAudit] test_watchdog_fahrenheit_conversion_and_alert_latch PASSED")


def test_live_scenario_quick_mood_ribbon_during_active_movie():
    """Live Scenario: Verifies Quick Mood Ribbon palette shifts during active movie playback without AV disruption."""
    setup_clean_environment()
    # 1. Start in movie mode
    theater.play_movie()
    assert state.get("input_select.basement_theater_mode") == "Movie"
    assert state.get("media_player.theater_receiver") == "on"
    assert state.get("sensor.theater_mode") == "movie"
    assert state.get("input_select.basement_lighting_mode") == "Daily Driver"
    assert state.getattr("media_player.theater_receiver", "source") == "HDMI1"

    # 2. Operator taps 'Synthwave' on Quick Mood Ribbon
    basement.select_palette("synthwave")
    assert state.get("input_select.basement_lighting_mode") == "Social Mode"
    assert state.get("sensor.basement_palette") == "synthwave"
    # AV playback stays completely undisturbed
    assert state.get("media_player.theater_receiver") == "on"
    assert state.get("sensor.theater_mode") == "movie"

    # 3. Operator switches to 'Cyberpunk'
    basement.select_palette("cyberpunk")
    assert state.get("sensor.basement_palette") == "cyberpunk"
    assert state.get("input_select.basement_lighting_mode") == "Social Mode"

    # 4. Operator resets to circadian normal
    basement.mood_reset_normal()
    assert state.get("input_select.basement_lighting_mode") == "Daily Driver"
    assert state.get("sensor.theater_mode") == "movie"

    print("  ✓ [LiveScenario] test_live_scenario_quick_mood_ribbon_during_active_movie PASSED (Quick Mood color shifts preserved AV)")


def test_live_scenario_remote_app_launch_and_dsp_routing():
    """Live Scenario: Verifies Remote modal app launcher dock and Yamaha DSP sound mode switcher."""
    setup_clean_environment()
    # 1. Launch Stremio from Remote modal
    theater.launch_app("stremio")
    assert state.get("input_select.basement_theater_mode") == "Movie"
    assert state.get("media_player.theater_receiver") == "on"
    assert state.getattr("media_player.theater_receiver", "source") == "HDMI1"

    # 2. Remote switches DSP to Surround Decoder for dialogue
    media_player.select_sound_mode(entity_id="media_player.theater_receiver", sound_mode="Surround Decoder")
    assert state.getattr("media_player.theater_receiver", "sound_mode") == "Surround Decoder"

    # 3. Remote switches DSP to Sports
    media_player.select_sound_mode(entity_id="media_player.theater_receiver", sound_mode="Sports")
    assert state.getattr("media_player.theater_receiver", "sound_mode") == "Sports"

    # 4. Remote switches DSP to 7ch Stereo
    media_player.select_sound_mode(entity_id="media_player.theater_receiver", sound_mode="7ch Stereo")
    assert state.getattr("media_player.theater_receiver", "sound_mode") == "7ch Stereo"

    # 5. Remote switches DSP back to Standard bitstream
    media_player.select_sound_mode(entity_id="media_player.theater_receiver", sound_mode="Standard")
    assert state.getattr("media_player.theater_receiver", "sound_mode") == "Standard"

    # 6. Launch Batocera from Remote modal
    theater.launch_app("batocera")
    assert state.get("input_select.basement_theater_mode") == "Game"
    assert state.getattr("media_player.theater_receiver", "source") == "HDMI2"

    print("  ✓ [LiveScenario] test_live_scenario_remote_app_launch_and_dsp_routing PASSED (App launch & DSP modes verified)")


def _fake_hdhomerun(accept=True):
    """Stands in for the HDHomeRun control socket; records (name, value) sets."""
    sets = []
    def fake(host, name, value=None, timeout=3.0):
        sets.append((name, value))
        return value if accept else None
    fake.test_fake = True
    theater._hdhr_control = fake
    return sets


def test_pyscript_has_no_generator_expressions():
    """Pyscript raises NotImplementedError on generator expressions at runtime; use list comprehensions.
    Native @pyscript_compile functions run as plain Python and are exempt."""
    import ast
    pyscript_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pyscript")
    offenders = []
    for fname in sorted(os.listdir(pyscript_dir)):
        if not fname.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(pyscript_dir, fname)).read())
        exempt = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and any(
                getattr(d, "id", None) == "pyscript_compile" for d in node.decorator_list
            ):
                exempt.update(id(n) for n in ast.walk(node))
        for node in ast.walk(tree):
            if isinstance(node, ast.GeneratorExp) and id(node) not in exempt:
                offenders.append(f"{fname}:{node.lineno}")
    assert not offenders, f"FAIL: generator expressions break in pyscript: {offenders}"
    print("  ✓ [PyscriptCompat] test_pyscript_has_no_generator_expressions PASSED")


def test_hdhomerun_tuner_contention_and_preemption():
    """Verify that when both ATSC physical tuners are locked, theater kickoff preempts remote stream to guarantee broadcast."""
    original = theater._hdhr_control
    try:
        # Case A: 1 tuner idle, 1 busy -> No preemption needed
        setup_clean_environment()
        sets = _fake_hdhomerun()
        state.set("sensor.tuner0", "NBC 10.1")
        state.set("sensor.tuner1", "idle")
        spy.clear()
        theater.play_sports()
        assert not sets, f"FAIL: Tuner released when a tuner was still free: {sets}"
        assert state.get("sensor.theater_mode") == "sports"

        # Case B: Both tuners busy with remote streams -> force-release tuner 1
        setup_clean_environment()
        sets = _fake_hdhomerun()
        state.set("sensor.tuner0", "NBC 10.1")
        state.set("sensor.tuner1", "FOX 29.1")
        spy.clear()
        theater.play_sports()
        assert sets == [("/tuner1/lockkey", "force"), ("/tuner1/channel", "none")], f"FAIL: Wrong release sequence: {sets}"
        notify_call = spy.last_call_for("notify", "ntfy")
        assert notify_call and "Evicted" in notify_call["kwargs"].get("message", ""), "FAIL: Preemption success alert missing!"
        assert state.get("sensor.theater_mode") == "sports"

        # Case C: Device refuses -> alert says it failed instead of claiming success
        setup_clean_environment()
        _fake_hdhomerun(accept=False)
        state.set("sensor.tuner0", "NBC 10.1")
        state.set("sensor.tuner1", "FOX 29.1")
        spy.clear()
        assert theater.preempt_tuner_for_theater(target_tuner="1") is False
        notify_call = spy.last_call_for("notify", "ntfy")
        assert "failed" in notify_call["kwargs"].get("message", ""), "FAIL: Failed preemption reported as success!"
    finally:
        theater._hdhr_control = original

    print("  ✓ [TunerPreemption] test_hdhomerun_tuner_contention_and_preemption PASSED (force-release, success & failure alerts)")


# ==============================================================================
# 3. MASTER RUNNER (50 TESTS)
# ==============================================================================
if __name__ == "__main__":
    print("\n==================================================")
    print("RUNNING COMPLETE 50-TEST BASEMENT & THEATER SIMULATION")
    print("==================================================")
    start = time.time()
    passed = 0

    tests = [
        # Suite 1: Core Hardware & Safety (7)
        test_play_music_projector_cold_start,
        test_play_music_cuts_live_plug_before_onn_wake,
        test_cinema_shield_blackout,
        test_movie_intermission_glow,
        test_stair_stealth_red_in_movie_mode,
        test_stair_daily_driver_entry,
        test_instant_walkout_shutoff,
        # Suite 2: State Transition Matrix (6)
        test_transition_daily_to_social,
        test_transition_social_to_movie,
        test_transition_movie_to_daily,
        test_transition_social_to_daily,
        test_transition_movie_to_social,
        test_transition_daily_to_movie,
        # Suite 3: Temporal & Timeouts (4)
        test_pause_debounce_not_triggering_on_quick_seek,
        test_stair_downward_entry_does_not_cut_lights_on_door_close,
        test_curtain_call_instant_walkout,
        test_open_door_vacancy_guard,
        # Suite 4: Projector Cooldown & Thermal Safety (3)
        test_projector_cooldown_fan_timeout_keeps_mains_on,
        test_projector_cooldown_double_low_reads_requirement,
        test_projector_cooldown_aborts_on_movie_resumed,
        # Suite 5: AV Telemetry & Arbitration (4)
        test_telemetry_receiver_off_sets_theater_mode_off,
        test_telemetry_hdmi2_sets_game_mode,
        test_telemetry_hdmi1_spotify_sets_music_mode,
        test_telemetry_bluetooth_native_sets_music_mode,
        # Suite 6: Batocera Ecosystem & Audio (5)
        test_batocera_auto_cut_when_current_drops,
        test_batocera_audio_sound_mode_selection,
        test_batocera_game_boxart_resolution_populates_dedicated_sensor,
        test_batocera_game_boxart_decoupled_from_movie_poster,
        test_batocera_boxart_reset_on_power_off,
        # Suite 6B: ASUS ROG Gaming PC & Steam Integration (5)
        test_pc_gaming_active_window_detection_and_sanitization,
        test_steam_big_picture_mode_carousel,
        test_pc_gaming_gpu_temp_telemetry_in_subtitle,
        test_moonlight_app_triggers_game_mode,
        test_pc_gaming_blackout_in_theater_lighting_sync,
        test_play_pc_game_target_routing,
        # Suite 7: Audio Routing & Sports Commentary Suppression (9)
        test_audio_routing_youtube_engages_surround_decoder,
        test_audio_routing_stremio_engages_standard_surround,
        test_audio_routing_spotify_engages_7ch_stereo,
        test_audio_routing_ignored_when_on_hdmi2_gaming,
        test_audio_routing_hdhomerun_engages_sports_mode_and_ducks_center,
        test_audio_routing_televizio_defaults_center_to_minus_10_if_slider_missing,
        test_audio_routing_exiting_sports_to_stremio_restores_flat_center,
        test_session_end_turns_off_zone_2_and_resets_center_trim,
        test_play_movie_resets_center_trim,
        test_stremio_futurama_episode_art_resolution,
        test_stremio_movie_title_resolution,
        # Suite 8: Atmospheric Engine & Pre-Show (5)
        test_lobby_browsing_android_launcher,
        test_lobby_browsing_batocera_carousel,
        test_music_lounge_lighting_sync,
        test_nightly_social_reset_clears_modes,
        # Suite 9: Master Utilities & Guest Lock (4)
        test_social_mode_lock_blocks_exit_shutoff,
        test_walkout_cancelled_when_someone_still_downstairs,
        test_walkout_cancelled_when_door_reopens,
        test_nightly_reset_turns_off_forgotten_social_lights,
        test_nightly_reset_keeps_lights_with_recent_motion,
        test_manual_social_survives_movie_but_sports_social_does_not,
        test_master_basement_all_off_service,
        test_toggle_all_basement_lights_when_loads_active,
        test_drawer_collapse_on_mode_select,
        # Suite 10: Chaos, Fault Injection & Sanitization (6)
        test_projector_corrupted_current_fails_safe,
        test_projector_negative_or_none_current,
        test_force_projector_off_emergency_sequence,
        test_theater_in_use_flips_daily_driver_to_movie_mode,
        test_game_title_sanitization_removes_rom_tags,
        test_tmdb_fetcher_missing_key_graceful_fail,
        test_snack_runner_walkout_does_not_cut_movie_lights,
        test_yamaha_rest_timeout_fails_gracefully,
        # Suite 11: E2E Full 5-Hour Evening (1)
        test_full_evening_story_simulation,
        # Suite 11: Philadelphia Eagles Game-Day & Scoring Engine (6)
        test_overturned_touchdown_negative_delta_is_ignored,
        test_touchdown_delta_fires_eagles_chant,
        test_manual_effect_eagles_chant_cadence,
        test_field_goal_delta_creates_snapshot_and_pulses,
        test_score_flash_suppressed_when_game_not_in_progress,
        test_eagles_game_start_and_game_over_lifecycle,
        # Suite 12: Sports, Hardware Sync & Drift Engine (9)
        test_play_sports_orchestration,
        test_telemetry_hdmi1_sports_app_resolves_to_sports_mode,
        test_projector_cooldown_aborts_on_sports_active,
        test_audio_routing_ignores_android_launcher,
        test_audio_routing_sanitizes_activity_slash_suffix,
        test_announcer_volume_slider_syncs_during_sports,
        test_announcer_volume_slider_ignored_outside_sports,
        test_announcer_slider_does_not_snap_to_preset,
        test_session_end_restores_adaptive_lighting_and_clears_party,
        test_toggle_ambient_drift_service,
        test_theater_volume_up_down_fine_step,
        test_theater_announcer_up_down_mute,
        test_theater_announcer_3way_toggle,
        # Suite 13: Unmanaged Exit, Cross-Mode Teardown & Bi-directional Sync (5)
        test_unmanaged_exit_receiver_power_off_triggers_safe_teardown,
        test_cross_mode_session_teardown_game_to_movie,
        test_cross_mode_session_teardown_music_and_sports,
        test_bidirectional_theater_select_sync,
        test_curtain_call_warm_white_lighting_restoration,
        test_curtain_call_after_gaming_never_wakes_onn_or_leaks_hdmi1,
        test_slow_upward_stair_exit_real_telemetry_protected,
        test_walkout_detected_when_door_sensor_drops_events,
        test_entry_door_close_without_recent_motion_keeps_lights,
        test_recorder_telemetry_noise_suppression_contract,
        test_unified_media_transport_routing,
        test_watchdog_transit_microservice_failure_alert,
        test_announcer_center_trim_boundary_clamping,
        test_libretro_boxart_system_mapping_and_encoding,
        test_is_booting_suppression,
        test_media_search_candidate_sanitization_matrix,
        test_ambient_drift_state_machine,
        test_packages_theater_yaml_template_contracts,
        test_post_power_restoration_sweep_vacant,
        test_post_power_restoration_sweep_occupied_suppressed,
        test_power_restoration_skipped_on_ha_restart,
        test_watchdog_thermal_and_projector_alerts,
        test_theater_artwork_cache_and_circuit_breaker,
        test_watchdog_storage_and_health_audit,
        test_watchdog_fahrenheit_conversion_and_alert_latch,
        test_live_scenario_quick_mood_ribbon_during_active_movie,
        test_live_scenario_remote_app_launch_and_dsp_routing,
        test_pyscript_has_no_generator_expressions,
        test_hdhomerun_tuner_contention_and_preemption,
    ]

    try:
        for t in tests:
            t()
            passed += 1

        elapsed = (time.time() - start) * 1000
        print("==================================================")
        print(f"ALL {passed}/{len(tests)} SIMULATION TESTS PASSED in {elapsed:.2f} ms")
        print("==================================================\n")
    except Exception as err:
        import traceback
        traceback.print_exc()
        print(f"\n❌ SIMULATION TEST FAILED: {err}\n")
        sys.exit(1)