"""
Comprehensive Multi-Dashboard Integrity & Defect Audit
Audits all YAML dashboards in dashboards/*.yaml against the verified entity dictionary,
action syntax standards (perform-action vs call-service), and cross-dashboard navigation paths.

Run: python3 ~/ha_config/tests/test_dashboard_integrity.py
"""
import os
import sys
import re
import glob

REGISTERED_ENTITIES = {
    # Theater AV & Hardware
    "switch.projector", "sensor.projector_current", "sensor.projector_current_rounded",
    "sensor.projector_power_state", "sensor.batocera_current_rounded", "sensor.batocera_power_state",
    "sensor.theater_total_power", "media_player.theater_receiver",
    "media_player.theater_receiver_zone_2", "media_player.onn_pro", "media_player.onn_pro_2",
    "remote.onn_pro", "switch.batocera", "switch.batocera_console", "sensor.batocera_current",
    "sensor.batocera_state", "sensor.batocera_current_game", "sensor.batocera_system",
    "button.batocera_shutdown", "button.batocera_shutdown_2", "switch.bias_lights",
    "switch.gaming_pc", "binary_sensor.gaming_pc_online", "button.desktop_rspn8nu_shutdown",
    "sensor.desktop_rspn8nu_activewindow", "sensor.desktop_rspn8nu_gputemperature",
    "sensor.gaming_pc_active_game", "sensor.gaming_pc_gpu_temperature",
    "input_number.theater_announcer_volume", "sensor.theater_current_poster",
    "sensor.theater_current_boxart", "input_text.theater_movie_search",
    "sensor.mediasession2mqtt_1_playback_state", "sensor.mediasession2mqtt_1_media_title",
    "sensor.mediasession2mqtt_1_application_id", "media_player.whole_house_spotify",

    # Zone Lighting & Environmental Sensors
    "light.theater_dimmer", "light.theater_lights", "light.stairlights",
    "light.zigbee_basement_lights", "light.zigbee_bar_lights",
    "light.zigbee_lounge_lights_1", "light.zigbee_lounge_lights_2", "light.zigbee_lounge_lights_3",
    "light.zigbee_lounge_lights", "binary_sensor.basement_stairs_door_sensor",
    "binary_sensor.bottom_stairs", "switch.basement_adaptive_lighting_adaptive_lighting_basement_adaptive_lighting",
    "switch.adaptive_lighting_basement_adaptive_lighting_adaptive_lighting_sleep_mode_basement_adaptive_lighting",
    "switch.adaptive_lighting_basement_adaptive_lighting_adaptive_lighting_adapt_brightness_basement_adaptive_lighting",
    "switch.adaptive_lighting_basement_adaptive_lighting_adaptive_lighting_adapt_color_basement_adaptive_lighting",

    # Bedroom Lights
    "light.bedroom_lamp_1", "light.bedroom_light_2", "light.zigbee_bedroom_lights",

    # Sports, State Flags & Virtual Entities
    "sensor.philadelphia_eagles", "binary_sensor.basement_automation_allowed",
    "binary_sensor.theater_in_use", "binary_sensor.theater_announcer_bar", "binary_sensor.basement_lights_active",
    "input_select.basement_lighting_mode", "input_select.basement_theater_mode",
    "input_select.basement_drawer", "input_select.theater_announcer_preset",
    "sensor.theater_mode", "sensor.basement_palette", "sensor.basement_effect",
    "pyscript.curtain_call_active", "pyscript.mode_selector_expanded",

    # Host Infrastructure & System Monitor
    "sensor.system_monitor_processor_use", "sensor.system_monitor_memory_usage",
    "sensor.system_monitor_swap_usage", "sensor.system_monitor_disk_usage",
    "sensor.system_monitor_uptime", "binary_sensor.transit_microservice",
    "sensor.watchdog_system_health", "sensor.basement_automation_health",

    # Commute, Weather & House Entities
    "binary_sensor.septa_am_window", "binary_sensor.septa_pm_window", "binary_sensor.drive_display_window",
    "sensor.septa_commute", "sensor.commute_weather", "sensor.commute_drive_time",
    "weather.whole_house_national_weather_service_kphl", "weather.forecast_home",
    "calendar.matt", "calendar.partner", "calendar.family", "calendar.birthdays",
    "vacuum.vaculina", "camera.vaculina_map",
    "camera.back_deck_cam", "camera.back_yard_cam", "camera.front_porch_cam",
    "sensor.vaculina_battery_level", "sensor.vaculina_cleaned_area", "sensor.vaculina_charging_status",
    "sensor.office_creality_printer_print_progress", "sensor.office_creality_printer_print_status",

    # HDHomeRun & xTeVe Tuner Architecture
    "sensor.hdhomerun_tuner_allocation", "binary_sensor.hdhomerun_contention_risk",
    "input_boolean.xteve_tuner_reservation", "sensor.tuner0", "sensor.tuner1",
    "sensor.tuner0_target_ip", "sensor.tuner0_signal_quality", "sensor.tuner0_network_rate",
    "sensor.tuner1_target_ip", "sensor.tuner1_signal_quality", "sensor.tuner1_network_rate"
}

REGISTERED_SERVICES = {
    # PyScript Services
    "pyscript.play_movie", "pyscript.play_game", "pyscript.play_pc_game", "pyscript.play_music", "pyscript.play_sports",
    "pyscript.theater_play_spotify_playlist",
    "pyscript.session_end_house_lights", "pyscript.basement_all_off",
    "pyscript.toggle_all_basement_lights", "pyscript.mood_reset_normal",
    "pyscript.select_palette", "pyscript.select_effect_modifier",
    "pyscript.effect_bar_toast", "pyscript.effect_eagles_chant",
    "pyscript.toggle_ambient_drift", "pyscript.toggle_lighting_mode",
    "pyscript.toggle_mode_drawer", "pyscript.select_lighting_mode_ui",
    "pyscript.toggle_basement_drawer",
    "pyscript.theater_volume_up", "pyscript.theater_volume_down",
    "pyscript.theater_announcer_up", "pyscript.theater_announcer_down", "pyscript.theater_announcer_mute",
    "pyscript.theater_set_announcer_preset",
    "pyscript.theater_media_play_pause", "pyscript.theater_media_next", "pyscript.theater_media_previous",
    "pyscript.launch_app", "pyscript.search_and_play_movie",
    "pyscript.preempt_tuner_for_theater",

    # Standard HA Actions & Integrations
    "light.turn_on", "light.turn_off", "light.toggle",
    "switch.turn_on", "switch.turn_off", "switch.toggle",
    "vacuum.start", "vacuum.pause", "vacuum.stop", "vacuum.return_to_base",
    "spotcast.start",
    "remote.send_command",
    "media_player.media_play_pause", "media_player.volume_up", "media_player.volume_down",
    "media_player.select_source", "media_player.select_sound_mode",
    "media_player.play_media",
    "input_boolean.toggle", "input_boolean.turn_on", "input_boolean.turn_off",
    "input_select.select_option",
    "input_number.set_value", "button.press",
}

KNOWN_NAVIGATION_PREFIXES = {
    "/basement-yaml",
    "/dashboard-home",
    "/dashboard-home2",
    "/dashboard-diagnostics",
    "/dashboard-testing",
    "/kitchen-kiosk",
    "/onn-remote",
    "/activity-log",
    "/calendar"
}

def find_dashboard_files():
    base_dirs = [
        "dashboards",
        os.path.expanduser("~/ha_config/dashboards"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboards"))
    ]
    for d in base_dirs:
        if os.path.isdir(d):
            files = sorted(glob.glob(os.path.join(d, "*.yaml")))
            if files:
                return files
    return []

def load_yaml_with_includes(file_path, visited=None):
    if visited is None:
        visited = set()
    real_path = os.path.realpath(file_path)
    if real_path in visited:
        return ""
    visited.add(real_path)
    base_dir = os.path.dirname(file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    def replace_include(match):
        inc_file = match.group(1).strip()
        target_path = os.path.normpath(os.path.join(base_dir, inc_file))
        if os.path.isfile(target_path):
            return load_yaml_with_includes(target_path, visited)
        return match.group(0)

    return re.sub(r'!include\s+([^\s\n\r]+)', replace_include, content)

def audit_all_dashboards():
    print("\n==================================================")
    print("LOVELACE MULTI-DASHBOARD INTEGRITY & DEFECT AUDIT")
    print("==================================================")

    dashboard_files = find_dashboard_files()
    if not dashboard_files:
        print("  [!] No dashboard files found in dashboards/ directory!\n")
        sys.exit(1)

    total_defects = 0
    total_warnings = 0

    for file_path in dashboard_files:
        filename = os.path.basename(file_path)
        print(f"\n▶ Auditing: {filename} ({file_path})")
        raw_text = load_yaml_with_includes(file_path)

        file_defects = []
        file_warnings = []

        # 1. ENTITY LINKAGE AUDIT
        found_entities = set(re.findall(
            r"(?:entity:\s*|entity_id:\s*|states\(['\"]|is_state\(['\"]|state_attr\(['\"])([\w\.]+)",
            raw_text
        ))
        for ent in sorted(found_entities):
            if "." in ent and not ent.startswith("[[") and ent not in REGISTERED_ENTITIES:
                file_warnings.append(f"Unregistered entity: '{ent}'")

        # 2. ACTION / SERVICE CALL AUDIT
        # "- action: x.y" catches services passed to decluttering templates as a variable.
        found_actions = set(re.findall(r"(?:perform_action:\s*|service:\s*|-\s+action:\s*)([\w\.]+)", raw_text))
        for act in sorted(found_actions):
            if "." in act and act not in REGISTERED_SERVICES:
                file_defects.append(f"Unregistered action/service call: '{act}'")

        # 3. DEPRECATION AUDIT (call-service vs perform-action)
        call_services = re.findall(r"action:\s*call-service", raw_text)
        if call_services:
            file_warnings.append(f"Contains {len(call_services)} deprecated 'action: call-service' usages (prefer 'action: perform-action')")

        # 4. NAVIGATION PATH AUDIT
        nav_paths = re.findall(r"navigation_path:\s*([^\s\n]+)", raw_text)
        for path in nav_paths:
            clean_path = path.strip("'\"")
            if clean_path.startswith("#"):
                continue
            prefix = "/" + clean_path.strip("/").split("/")[0]
            if prefix not in KNOWN_NAVIGATION_PREFIXES:
                file_defects.append(f"Broken / Unregistered navigation path: '{path}'")

        # 5. CARD-SPECIFIC LOGIC (Marquee checks)
        if "UNIVERSAL NOW PLAYING MARQUEE" in raw_text:
            marquee_block = raw_text.split("UNIVERSAL NOW PLAYING MARQUEE")[1].split("CINEMA / THEATER EXPERIENCE EXPANDER")[0]
            if "Tap to Pause" in marquee_block and "action: none" in marquee_block:
                file_defects.append("UX Defect: Marquee secondary says 'Tap to Pause', but its tap_action is 'none'!")
            if 'state_not: "idle"' not in marquee_block and 'state: "playing"' in marquee_block:
                file_defects.append("Visibility Flaw: Marquee strictly requires state == 'playing'. Will vanish on pause!")

        # Print per-file report
        if file_defects:
            for d in file_defects:
                print(f"  ❌ DEFECT: {d}")
        if file_warnings:
            for w in file_warnings:
                print(f"  ⚠️  WARNING: {w}")
        if not file_defects and not file_warnings:
            print("  ✓ Pristine (0 defects, 0 warnings)")

        total_defects += len(file_defects)
        total_warnings += len(file_warnings)

    print("\n==================================================")
    print(f"AUDIT SUMMARY: {len(dashboard_files)} Dashboards Scanned")
    print(f"TOTAL DEFECTS:  {total_defects}")
    print(f"TOTAL WARNINGS: {total_warnings}")
    print("==================================================")

    if total_defects > 0:
        print("❌ FAILED: Defects detected in one or more dashboards.\n")
        sys.exit(1)
    else:
        print("✓ SUCCESS: All dashboards passed structural integrity checks.\n")
        sys.exit(0)

if __name__ == "__main__":
    audit_all_dashboards()
