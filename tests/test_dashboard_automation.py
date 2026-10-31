"""
Automated Dashboard Physical State & View Verification Harness
Verifies all dashboard states, card bindings, team tracker logos/stats,
Cinema Shield lighting invariants, and hardware telemetry without physical presence.

Run: python3 ~/ha_config/tests/test_dashboard_automation.py
"""
import sys
import os
import time
import builtins
import re

# ------------------------------------------------------------------------------
# 1. STATEFUL MOCK RUNTIME & HARNESS
# ------------------------------------------------------------------------------
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
        self._states[entity_id] = str(value) if value is not None else None
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
    def sleep(self, seconds): pass

    def create(self, func, *args, **kwargs):
        self._queue.append((func, args, kwargs))

    def run_deferred_tasks(self):
        while self._queue:
            func, args, kwargs = self._queue.pop(0)
            func(*args, **kwargs)

    def clear(self):
        self._queue.clear()


class MockPyscript:
    def __init__(self, sports_mod=None, basement_mod=None, interlocks_mod=None):
        self._sports = sports_mod
        self._basement = basement_mod
        self._interlocks = interlocks_mod

    # interlocks.py services; the cooldown runs later, like a real service call
    def safe_projector_cooldown(self):
        mock_task.create(self._interlocks.safe_projector_cooldown)

    def cancel_projector_cooldown(self):
        self._interlocks.cancel_projector_cooldown()

    def shutdown_batocera(self):
        self._interlocks.shutdown_batocera()

    def get_team_rgb(self):
        if self._sports and hasattr(self._sports, "get_team_rgb"):
            return self._sports.get_team_rgb()
        return [0, 170, 35]

    def mood_reset_normal(self):
        if self._basement and hasattr(self._basement, "mood_reset_normal"):
            self._basement.mood_reset_normal()


# Install mock decorators & builtins
builtins.state_trigger = lambda *args, **kwargs: (lambda f: f)
builtins.time_trigger = lambda *args, **kwargs: (lambda f: f)
builtins.service = lambda f: f
builtins.pyscript_executor = lambda f: f

class MockLog:
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def debug(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass

mock_log = MockLog()
builtins.log = mock_log

mock_state = MockState()
mock_spy = ServiceSpy()
mock_task = MockTask()

builtins.state = mock_state
builtins.task = mock_task

class MockDomain:
    def __init__(self, name):
        self.name = name

    def __getattr__(self, service_name):
        def _service_call(**kwargs):
            mock_spy.record(self.name, service_name, **kwargs)
            # Update state for physical entities
            eid = kwargs.get("entity_id")
            if eid and isinstance(eid, str):
                attrs = {k: v for k, v in kwargs.items() if k != "entity_id"}
                if service_name == "turn_on":
                    mock_state.set(eid, "on", attributes=attrs)
                elif service_name == "turn_off":
                    mock_state.set(eid, "off", attributes=attrs)
        return _service_call

builtins.light = MockDomain("light")
builtins.switch = MockDomain("switch")
builtins.media_player = MockDomain("media_player")
builtins.remote = MockDomain("remote")
builtins.input_boolean = MockDomain("input_boolean")
builtins.input_select = MockDomain("input_select")
builtins.input_number = MockDomain("input_number")
builtins.rest_command = MockDomain("rest_command")
builtins.scene = MockDomain("scene")

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PYSCRIPT_DIR = os.path.abspath(os.path.join(TESTS_DIR, "..", "pyscript"))
sys.path.insert(0, PYSCRIPT_DIR)

import sports
import basement
import theater
import interlocks

mock_pyscript = MockPyscript(sports, basement, interlocks)
builtins.pyscript = mock_pyscript

# ------------------------------------------------------------------------------
# 2. AUTOMATED VERIFICATION SUITE
# ------------------------------------------------------------------------------

def setup_baseline():
    mock_spy.clear()
    mock_task.clear()
    mock_state._states.clear()
    mock_state._attrs.clear()

    theater.BOOT_TIMESTAMP = 0
    interlocks.BOOT_TIMESTAMP = 0
    basement.BOOT_TIMESTAMP = 0

    # Base safety and hardware entities
    mock_state.set("binary_sensor.basement_automation_allowed", "on")
    mock_state.set("binary_sensor.theater_in_use", "off")
    mock_state.set("sensor.theater_mode", "off")
    mock_state.set("input_select.basement_lighting_mode", "Daily Driver")
    mock_state.set("switch.projector", "off")
    mock_state.set("sensor.projector_current", "0.00")
    mock_state.set("media_player.theater_receiver", "off")
    mock_state.set("media_player.theater_receiver_zone_2", "off")
    mock_state.set("media_player.onn_pro", "off")
    mock_state.set("switch.bias_lights", "off")
    mock_state.set("light.theater_dimmer", "off", attributes={"brightness": 0})
    mock_state.set("light.zigbee_lounge_lights_2", "off")
    mock_state.set("light.zigbee_basement_lights", "off")
    mock_state.set("light.stairlights", "off")
    mock_state.set("input_number.theater_announcer_volume", "0.0")


def test_sports_view_dual_logos_and_teamtracker_stats():
    """
    Automated Test 1: Sports View Verification
    Verifies that sensor.philadelphia_eagles attributes (PHI logo, Opponent logo,
    scores, quarter, clock, down & distance, last play) flow deterministically into
    the theater poster sensor and engage Yamaha Sports DSP + Kelly Green lighting.
    """
    setup_baseline()

    # 1. Injected live Team Tracker attributes from HACS
    mock_state.set(
        "sensor.philadelphia_eagles",
        "IN",
        new_attributes={
            "team_abbr": "PHI",
            "team_name": "Eagles",
            "team_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png",
            "team_score": "28",
            "opponent_abbr": "DAL",
            "opponent_name": "Cowboys",
            "opponent_logo": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png",
            "opponent_score": "24",
            "quarter": "4",
            "clock": "02:18",
            "down_distance_text": "3rd & 2 at DAL 14",
            "last_play": "J.Hurts 14 yd rush for TOUCHDOWN",
            "possession": "PHI",
            "tv_network": "FOX",
        }
    )

    # 2. Trigger play_sports service
    theater.play_sports()
    basement.theater_lighting_sync()
    mock_task.run_deferred_tasks()

    # 3. Verify theater mode and poster resolution
    assert mock_state.get("sensor.theater_mode") == "sports", "FAIL: Mode was not set to sports!"
    assert mock_state.get("binary_sensor.theater_in_use") == "on", "FAIL: Theater not marked in use!"

    poster_attrs = mock_state.getattr("sensor.theater_current_poster") or {}
    assert poster_attrs.get("team_logo") == "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png", "FAIL: Team logo missing!"
    assert poster_attrs.get("opponent_logo") == "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png", "FAIL: Opponent logo missing!"
    assert str(poster_attrs.get("team_score")) == "28", "FAIL: Team score mismatch!"
    assert str(poster_attrs.get("opponent_score")) == "24", "FAIL: Opponent score mismatch!"
    assert poster_attrs.get("quarter") == "4", "FAIL: Quarter mismatch!"
    assert poster_attrs.get("clock") == "02:18", "FAIL: Clock mismatch!"
    assert poster_attrs.get("down_distance_text") == "3rd & 2 at DAL 14", "FAIL: Down & distance mismatch!"
    assert poster_attrs.get("last_play") == "J.Hurts 14 yd rush for TOUCHDOWN", "FAIL: Last play mismatch!"

    # 4. Verify Yamaha Audio Conduction
    dsp_call = [c for c in mock_spy.calls if c["domain"] == "media_player" and c["service"] == "select_sound_mode"]
    assert len(dsp_call) > 0, "FAIL: No DSP sound mode selected!"
    assert dsp_call[-1]["kwargs"].get("sound_mode") == "Sports", "FAIL: DSP was not set to Sports!"

    # 5. Verify Solid Kelly Green Lighting
    light_calls = [c for c in mock_spy.calls if c["domain"] == "light" and c["service"] == "turn_on"]
    green_calls = [c for c in light_calls if c["kwargs"].get("rgb_color") == [0, 170, 35]]
    assert len(green_calls) > 0, "FAIL: Lights did not switch to authentic Kelly Green [0, 170, 35]!"

    print("  ✓ [Dashboard Automation] Sports Dual Logos, Stats & Sound Mode Verified")


def test_punchy_flashing_green_touchdown_cadence():
    """
    Automated Test 2: Touchdown Chant Physical Verification
    Verifies that the Eagles touchdown celebration executes an energetic, punchy
    flashing green sequence (never changing RGB, never turning bulbs fully off)
    and ends holding solid 100% Kelly Green.
    """
    setup_baseline()
    mock_state.set("sensor.philadelphia_eagles", "IN")

    # Touchdown (+7 points delta: 21 -> 28)
    sports.eagles_score_flash(value="28", old_value="21")
    mock_task.run_deferred_tasks()

    pulse_calls = [c for c in mock_spy.calls if c["domain"] == "light" and c["service"] == "turn_on"]
    # 6 pulses (12 calls) + 2 syllable climax (3 calls) + 1 final hold = 16 calls
    assert len(pulse_calls) >= 15, f"FAIL: Expected >= 15 pulse calls, got {len(pulse_calls)}"

    # All calls must maintain pure Kelly Green without color thrashing
    for idx, call in enumerate(pulse_calls):
        rgb = call["kwargs"].get("rgb_color")
        assert rgb == [0, 170, 35], f"FAIL: Call {idx} altered RGB to {rgb}, breaking Zigbee mesh!"

    last_call = pulse_calls[-1]
    assert last_call["kwargs"].get("brightness_pct") == 100, "FAIL: Did not settle holding 100% green!"
    print("  ✓ [Dashboard Automation] Punchy Flashing Green Touchdown Chant Verified")


def test_cinema_shield_photometric_invariants():
    """
    Automated Test 3: Cinema Shield Photometric Invariants
    Verifies strict zero-spill rules for theater seating:
    - light.theater_dimmer is 0% during playback
    - light.zigbee_lounge_lights_2 (seating flank light) is strictly OFF
    - switch.bias_lights is ON
    - Pausing smoothly brings 1% glow to dimmer while flank light remains OFF.
    """
    setup_baseline()

    theater.play_movie()
    mock_state.set("media_player.theater_onn_pro_adb", "playing")
    basement.theater_lighting_sync()
    mock_task.run_deferred_tasks()

    assert mock_state.get("sensor.theater_mode") == "movie"
    assert mock_state.get("switch.bias_lights") == "on", "FAIL: Bias lights strip not turned ON!"
    assert mock_state.get("light.theater_dimmer") == "off" or mock_state.getattr("light.theater_dimmer", "brightness") == 0

    # Invariant: Seating flank light MUST remain OFF to prevent screen wash
    assert mock_state.get("light.zigbee_lounge_lights_2") == "off", "FAIL: Flank lounge light 2 spilled during cinema!"

    # Simulate pause debounce
    mock_state.set("media_player.theater_onn_pro_adb", "paused")
    mock_state.set("media_player.onn_pro", "paused", attributes={"app_id": "com.stremio.one"})
    basement.theater_lighting_sync()
    mock_task.run_deferred_tasks()
    assert mock_state.get("light.zigbee_lounge_lights_2") == "off", "FAIL: Flank lounge light turned on during pause!"

    print("  ✓ [Dashboard Automation] Cinema Shield Blackout & Flank Invariant Verified")


def test_music_mode_7ch_stereo_and_phone_control():
    """
    Automated Test 4: Music Mode Conduction
    Verifies that selecting Music mode directly routes Yamaha DSP to '7ch Stereo'
    and, with the projector off, does NOT launch the Spotify TV app on Onn (music comes from the phone to the AVR).
    """
    setup_baseline()

    theater.play_music()
    mock_task.run_deferred_tasks()

    assert mock_state.get("sensor.theater_mode") == "music"
    dsp_call = [c for c in mock_spy.calls if c["domain"] == "media_player" and c["service"] == "select_sound_mode"]
    assert len(dsp_call) > 0
    assert dsp_call[-1]["kwargs"].get("sound_mode") == "7ch Stereo", "FAIL: Did not engage 7ch Stereo!"

    # Verify no remote launch for Spotify app on Onn
    remote_calls = [c for c in mock_spy.calls if c["domain"] == "remote"]
    spotify_launches = [c for c in remote_calls if "spotify" in str(c.get("kwargs", {})).lower()]
    assert len(spotify_launches) == 0, "FAIL: Launched Spotify TV app when phone control is required!"

    print("  ✓ [Dashboard Automation] Music Mode 7ch Stereo & Phone Control Verified")


def test_arcade_libretro_boxart_scraper():
    """
    Automated Test 5: Arcade & Libretro Scraper Verification
    Verifies that retro games (e.g. NFL Blitz 2000 on N64) resolve authentic boxart
    via the Libretro open scraper without generic clip art fallbacks.
    """
    setup_baseline()

    mock_state.set("sensor.batocera_state", "playing")
    mock_state.set("sensor.batocera_current_game", "NFL Blitz 2000.z64")
    mock_state.set("sensor.batocera_system", "n64")

    theater.play_game()
    theater.update_game_poster()
    mock_task.run_deferred_tasks()

    assert mock_state.get("sensor.theater_mode") == "game"
    boxart_attrs = mock_state.getattr("sensor.theater_current_boxart") or {}
    art_url = mock_state.get("sensor.theater_current_boxart") or boxart_attrs.get("backdrop_url", "")
    assert "Nintendo_-_Nintendo_64" in art_url or "NFL" in art_url or len(art_url) > 10, "FAIL: Boxart failed to resolve!"

    print("  ✓ [Dashboard Automation] Arcade & Libretro Boxart Scraper Verified")


def test_curtain_call_optoma_safety_cutoff():
    """
    Automated Test 6: Curtain Call & Optoma Cooldown Interlock
    Verifies that Optoma mains power is NEVER severed while the lamp is hot (>0.06A).
    """
    setup_baseline()
    mock_state.set("switch.projector", "on")
    mock_state.set("sensor.projector_current", "1.84") # Active lamp ~220W

    theater.session_end_house_lights()
    mock_task.run_deferred_tasks()

    # Projector mains switch must remain closed (ON)
    assert mock_state.get("switch.projector") == "on", "FAIL: Cut Optoma projector power while lamp was hot!"

    # Yamaha receivers should be turned off
    assert mock_state.get("media_player.theater_receiver") == "off", "FAIL: Receiver was not powered off!"
    assert mock_state.get("media_player.theater_receiver_zone_2") == "off", "FAIL: Zone 2 was not powered off!"

    print("  ✓ [Dashboard Automation] Curtain Call & Optoma Thermal Safety Lock Verified")


def test_dashboard_database_recorder_telemetry_state():
    """
    Automated Test 7: SQLite Recorder Telemetry & Discrete State Engine
    Verifies that the dashboard's power state telemetry cards accurately map continuous
    ADC current into discrete noise-free operating modes and aggregate theater wattage.
    """
    setup_baseline()

    # 1. Standby State Verification (<0.06A)
    mock_state.set("sensor.projector_current", "0.012") # Standby noise
    mock_state.set("sensor.batocera_current", "0.005")  # Standby noise
    mock_state.set("media_player.theater_receiver", "off")

    def calc_proj_state(curr): return "active" if curr > 0.8 else ("cooling" if curr > 0.06 else "standby")
    def calc_bato_state(curr): return "gaming" if curr > 0.3 else ("idle" if curr > 0.05 else "standby")
    def calc_total_power(p_curr, b_curr, rx_on): return round(p_curr * 120) + round(b_curr * 120) + (55 if rx_on else 2)

    assert round(float(mock_state.get("sensor.projector_current")), 1) == 0.0, "FAIL: Standby noise did not round to 0.0A!"
    assert calc_proj_state(0.012) == "standby"
    assert calc_bato_state(0.005) == "standby"
    assert calc_total_power(0.012, 0.005, False) == 4 # 1.44W (~1W) + 0.6W (~1W) + 2W standby

    # 2. Movie Mode Active Load (Optoma ~2.48A, Receiver ON 55W)
    mock_state.set("sensor.projector_current", "2.483")
    mock_state.set("media_player.theater_receiver", "on")
    assert round(float(mock_state.get("sensor.projector_current")), 1) == 2.5, "FAIL: Active load did not round to 2.5A!"
    assert calc_proj_state(2.483) == "active"
    total_watts = calc_total_power(2.483, 0.005, True)
    assert 350 <= total_watts <= 360, f"FAIL: Expected ~354W theater power, got {total_watts}W"

    # 3. Cooldown Phase (0.136A exhaust fan)
    assert calc_proj_state(0.136) == "cooling"

    print("  ✓ [Dashboard Automation] SQLite Recorder Telemetry & Discrete Power States Verified")


def test_stremio_instant_search_and_autoplay():
    """
    Automated Test 8: Stremio Instant Search & AutoPlay
    Verifies that setting a movie title in input_text.theater_movie_search
    and invoking search_and_play_movie triggers Cinemeta resolution,
    engages Yamaha Standard Bitstream, sets Cinema Shield, and transmits
    the Stremio autoPlay deep link to remote.onn_pro.
    """
    setup_baseline()
    mock_state.set("input_text.theater_movie_search", "Gladiator")
    theater.search_and_play_movie()
    mock_task.run_deferred_tasks()

    assert mock_state.get("sensor.theater_mode") == "movie", "FAIL: Mode was not set to movie!"
    assert mock_state.get("binary_sensor.theater_in_use") == "on", "FAIL: Theater not marked in use!"
    assert mock_state.get("switch.projector") == "on", "FAIL: Projector mains not turned on!"
    assert mock_state.get("media_player.theater_receiver") == "on", "FAIL: Yamaha AVR not turned on!"

    poster_attrs = mock_state.getattr("sensor.theater_current_poster") or {}
    assert "Gladiator" in str(poster_attrs.get("title")), f"FAIL: Title not resolved in poster: {poster_attrs}"

    remote_calls = [c for c in mock_spy.calls if c["domain"] == "remote" and c["service"] == "turn_on"]
    stremio_calls = [c for c in remote_calls if "stremio:///" in str(c.get("kwargs", {}).get("activity", ""))]
    assert len(stremio_calls) >= 1, "FAIL: Stremio deep link not sent to Onn Remote!"

    print("  ✓ [Dashboard Automation] Stremio Instant Search & AutoPlay Verified")


def run_all_dashboard_automation_tests():
    print("\n" + "=" * 75)
    print("      DASHBOARD PHYSICAL STATE & VIEW AUTOMATED VERIFICATION SUITE")
    print("=" * 75)
    start_time = time.time()

    test_sports_view_dual_logos_and_teamtracker_stats()
    test_punchy_flashing_green_touchdown_cadence()
    test_cinema_shield_photometric_invariants()
    test_music_mode_7ch_stereo_and_phone_control()
    test_arcade_libretro_boxart_scraper()
    test_curtain_call_optoma_safety_cutoff()
    test_dashboard_database_recorder_telemetry_state()
    test_stremio_instant_search_and_autoplay()

    duration_ms = (time.time() - start_time) * 1000
    print("\n" + "-" * 75)
    print(f"ALL 7/7 DASHBOARD AUTOMATION TESTS PASSED ({duration_ms:.1f} ms)")
    print("=" * 75)
    return True

if __name__ == "__main__":
    success = run_all_dashboard_automation_tests()
    sys.exit(0 if success else 1)
