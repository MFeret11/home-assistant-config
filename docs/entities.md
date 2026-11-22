# Verified Entity Dictionary

_Moved verbatim from AGENTS.md. "§N" references point to the old AGENTS.md sections (§4 lighting/sports now live in docs/lighting.md)._

## Renaming an entity

**Change the display name, not the entity ID, whenever you can.** In HA: Settings → Devices & services → Entities → pick the entity → change *Name*. Nothing in this repo refers to display names, so nothing else needs editing.

If the entity ID itself has to change (for example, a replaced device came back with a new one):

1. Change it in HA (same dialog, *Entity ID*).
2. List every copy of the old ID, from `~/ha_config`: `git grep -nw <old_id>`
3. Edit each place it shows up:
   - `pyscript/modules/shared_entities.py`: IDs used by both `theater.py` and `basement.py`. Saving it reloads both files, so do it with the theater idle.
   - `pyscript/interlocks.py`: keeps its own copies on purpose (see the note at the top of `shared_entities.py`). `tests/test_shared_entities.py` fails until they match again. Edit with the theater idle.
   - Other pyscript files: their IDs are at the top of each file. `health_check.py` lists the entities it checks.
   - `packages/*.yaml`, `custom_templates/`, `configuration.yaml`.
   - `dashboards/`: dashboard YAML always types IDs out. After editing a file pulled in with `!include`, `touch` the main dashboard file so HA picks it up. Also update `REGISTERED_ENTITIES` in `tests/test_dashboard_integrity.py`.
   - `tests/` (the fake HA states) and `scripts/telemetry/`.
   - This file.
   - Don't hand-edit `tests/telemetry_48h.json`: it is recorded history under the old ID. If the replay suites fail after the rename, regenerate it with `scripts/telemetry/extract_48h.py` once the new ID has a couple of days of history.
4. Run `python3 tests/run_all_tests.py`, then `git grep -nw <old_id>` again; only `telemetry_48h.json` should still match. Check `home-assistant.log` for pyscript errors.

## 2. Verified Entity Dictionary

### Theater AV & Hardware
- `switch.projector`: Optoma HD146X mains relay (Endpoint on Third Reality Dual Plug 2).
- `sensor.projector_current`: Current draw in Amperes ($A$) for Optoma projector (raw hardware feed, excluded from recorder to suppress 7,000+ ADC jitter writes).
- `sensor.projector_current_rounded`: Clean 1-decimal current (`round(1)`) recorded in SQLite; settles at flat `0.0A` during standby and `2.5A` during playback with zero write noise.
- `sensor.projector_power_state`: Discrete state machine (`standby`, `cooling`, `active`) for lamp hours, cooling cycles, and session counting (3 writes per movie).
- `sensor.batocera_current_rounded`: Clean 1-decimal current for Batocera PC.
- `sensor.batocera_power_state`: Discrete console state (`standby`, `idle`, `gaming`).
- `sensor.theater_total_power`: Real-time aggregated theater power consumption in Watts ($W$) across Projector, AVR, and Batocera.
- `media_player.theater_receiver`: Yamaha RX-V673 Main Zone (`HDMI1`, `HDMI2`, `HDMI3`). (Un-excluded from recorder to maintain essential receiver power and input history).
- `media_player.theater_receiver_zone_2`: Yamaha RX-V673 Zone 2 (Must be confirmed `off` during shutdown).
- `media_player.onn_pro`: Onn 4K Pro primary Android TV integration.
- `media_player.onn_pro_2`: Onn 4K Pro Google Cast fallback.
- `remote.onn_pro`: Android TV Remote entity used for D-pad, `BACK`, and `HOME` commands on the dashboard remote.
- `media_player.theater_onn_pro_adb` / `remote.theater_onn_pro_adb`: Onn 4K Pro over ADB (Android Debug Bridge integration, added 2026-10-24). The target for `androidtv.adb_command` (`am start`, `monkey`); `media_player.onn_pro` belongs to Android TV Remote and rejects ADB commands. Its state (`playing`/`paused`/`idle`) is the playback source for theater lighting (`get_media_state()` in `basement.py`), stream status labels in `theater.py`, and the dashboard play/pause chip. `theater.py` sends app launches and the Stremio deep link through it only when `remote.onn_pro` is unavailable (`_onn_adb_command()`).
- `media_player.whole_house_spotify`: Spotify Connect target — Spotify audio/playback state lives here, not on `media_player.onn_pro`. Does not support `media_pause` on every state; `pause_spotify_if_playing()` checks `supported_features` first.
- `switch.batocera`: Smart plug hardware relay powering Batocera PC (Endpoint on Third Reality Dual Plug 2).
- `switch.batocera_console`: Template switch. Off = clean shutdown via `button.batocera_shutdown_2` (never opens the relay directly; the relay opens only via the 12s current-draw interlock). On = closes `switch.batocera` relay (PC boots via BIOS power-on-after-AC-restore). State reflects `sensor.batocera_state` in (`playing`, `idle`).
- `button.batocera_shutdown_2`: Clean Batocera shutdown button (dashboard power sub-button).
- `sensor.batocera_current`: Current draw in Amperes ($A$) for Batocera PC.
- `sensor.batocera_state`: EmulationStation state (`playing`, `idle`).
- `sensor.batocera_current_game` / `sensor.batocera_system`: Active ROM metadata. When Batocera is streaming the ROG PC through its Moonlight client, the system is `moonlight` and the game is `steam-big-picture`; Steam shortcuts report as `<appid>_<Title_With_Underscores>` and are cleaned before art lookup.
- `switch.gaming_pc`: ASUS ROG Gaming PC power switch (WOL boot, clean shutdown via `button.desktop_rspn8nu_shutdown`).
- `binary_sensor.gaming_pc_online`: High-speed ICMP connectivity ping for ROG Gaming PC.
- `sensor.desktop_rspn8nu_activewindow`: HASS.Agent's raw active-window title. Not recorded, and pyscript does not trigger on it.
- `sensor.gaming_pc_active_game`: template in `configuration.yaml` that filters the raw window to a game title, `Steam Big Picture` or `Idle / Desktop` (browsers, VS Code, Citrix and other apps collapse to idle, so ordinary PC use never changes theater mode or reaches the recorder). `theater.py` and `basement.py` read and trigger on this one; it drives box-art lookup and the Cinema Shield blackout. New non-game apps go in its suffix list.
- `sensor.desktop_rspn8nu_gputemperature`: HASS.Agent GPU temperature telemetry in °C; surfaced live on dashboard cards and Now Playing marquee subtitle.
- `button.desktop_rspn8nu_shutdown`: Clean Windows OS software shutdown button.
- `switch.bias_lights`: Screen backlight strip relay (Endpoint on Third Reality Dual Plug 1).
- `input_number.theater_announcer_volume`: Announcer voice level slider (Center channel speaker trim: -10.0 dB to +10.0 dB). Dynamically synced in real time to hardware via PyScript.
  - *Hardware Limit Constraint*: Yamaha RX-V673 internal DSP firmware hard-codes individual speaker pre-out level trims (`<Speaker_Preout><Pattern_1><Lvl><Center>`) between `-10.0 dB` and `+10.0 dB`. The AVR has no network command for true per-speaker channel muting. At `-10.0 dB`, voice loudness is reduced to ~1/4 to sit under stadium crowd noise. (Setting Center to `None` is strictly avoided as it automatically downmixes commentary into Front L/R).
- `input_select.theater_announcer_preset`: 3-way segmented audio toggle (`Stadium Crowd`, `Broadcast Ref`, `Dialogue Boost`). Only 1 preset active at a time; automatically drives Center channel trim (`-10.0 dB`, `0.0 dB`, `+3.0 dB`) and keeps `input_number.theater_announcer_volume` in sync while occupying minimal dashboard space.
- `pyscript.theater_set_announcer_preset`: Service setting the active 3-way announcer preset and dispatching YNC XML center trim.
- `rest_command.yamaha_set_center_trim`: Sends YNC XML speaker level payload to Yamaha RX-V673 over HTTP.
- `rest_command.yamaha_master_volume_step`: Sends YNC XML volume step (`Up 1 dB` / `Down 1 dB`) to Yamaha RX-V673 Main Zone. Not called by `theater.py` since 2026-10-25: `theater_volume_up`/`down` use `media_player.volume_set` alone (1 dB = 0.01 of `volume_level`), because sending both moved some taps 2 dB.
- `pyscript.theater_volume_up` / `pyscript.theater_volume_down`: AVR master volume steps (used by the dashboard slider sub-buttons).
- `pyscript.theater_media_play_pause` / `theater_media_next` / `theater_media_previous`: Unified transport controls. Route to `media_player.whole_house_spotify` when `sensor.theater_mode == 'music'`, else `media_player.onn_pro` — needed because Spotify audio plays through the Cast/Spotify-Connect entity, not `onn_pro`'s own media session, so `onn_pro`'s playback state never reflects Spotify accurately.
- `pyscript.play_movie` / `play_game` / `play_pc_game` / `play_music` / `play_sports`: Theater mode entry points (each also exposed on the dashboard). `play_pc_game(target=...)` defaults to `batocera`: it wakes the ROG PC (WOL), powers Batocera, selects HDMI2 and sets `Surround Decoder`. `target="onn"` is an unused alternative that launches the Moonlight app on the Onn (HDMI1); `target="auto"` picks Batocera only if `switch.batocera` is already on.
- `automation.onn_remote_buttons`: Webhook automation (`packages/onn_remote.yaml`) that maps the Onn remote's app and Guide buttons, sent by Button Mapper, to `play_*` and lighting services. The button map is in `docs/onn-remote.md`.
- `pyscript.launch_app`: Onn app launcher; accepts `app:` of `stremio`, `hdhomerun`, `youtube`, `spotify`, `batocera`, or `moonlight` (also `pc`, `steam`, `bpm`: wakes the PC and starts the Batocera route, since Moonlight runs on Batocera; the aliases `moonlight_batocera`, `batocera_moonlight`, `pc_batocera` force it explicitly). You still pick Moonlight in EmulationStation yourself.

### Zone Lighting & Environmental Sensors
- `light.theater_dimmer`: Overhead theater ceiling dimmer circuit.
- `light.theater_lights`: Group containing `light.theater_dimmer` and `switch.bias_lights`.
- `light.stairlights`: 3-bulb stairwell lights (stealth-red stairs behavior, sports team color, post-outage sweep).
- `light.zigbee_basement_lights`: Master ZHA group for all 9 downstairs bulbs (3rd Reality hardware — see §4 hardware note on strobe/pulse behavior).
- `light.zigbee_bar_lights`: Zone 1 (North / Bar).
- `light.zigbee_lounge_lights_1`: Zone 2 (Central Hub / Stair Landing).
- `light.zigbee_lounge_lights_2`: Zone 3 (South-West / Flanks Theater Seating).
- `light.zigbee_lounge_lights_3`: Zone 4 (Deep South / Lounge Rear).
- `light.zigbee_lounge_lights`: Lounge multi-light group.
- `binary_sensor.basement_stairs_door_sensor`: Top door contact sensor (`device_class: opening`).
- `binary_sensor.bottom_stairs`: Foot-of-stairs motion sensor (`device_class: motion`).
- `binary_sensor.theater_mmwave_sensor`: Sonoff SNZB-06P mmWave presence sensor (ZHA, area Theater). Sees people sitting still. Device settings: `select.theater_mmwave_sensor_detection_sensitivity`, `number.theater_mmwave_sensor_presence_detection_timeout` (clear delay, seconds).
- `binary_sensor.mmwave_sensor_bar`: Second Sonoff SNZB-06P mmWave presence sensor (ZHA), in the bar area. Counts as presence in `basement.py` (`_mmwave_occupied`, walk-out cancel and mmWave vacancy); unavailable counts as empty. Device settings: `select.mmwave_sensor_bar_detection_sensitivity`, `number.mmwave_sensor_bar_presence_detection_timeout`.
- `switch.basement_adaptive_lighting_adaptive_lighting_basement_adaptive_lighting`: Adaptive Lighting master switch.
- `input_select.basement_lighting_mode`: `Daily Driver` / `Social Mode`. The single source of truth for Social Mode (which is also the presence lock). The old `input_boolean.party_mode` / `input_boolean.presence_override` were removed.
- `pyscript.basement_social_source`: who engaged Social Mode: `manual`, `sports`, or `none`. Only `sports` Social drops back to Daily when the theater switches to a movie or game.
- `pyscript.toggle_lighting_mode`: Toggles Daily Driver / Social Mode (dashboard header chip, Room Ambience card).
- `pyscript.mood_reset_normal`: Resets room to normal Daily Driver lighting (header chip hold action, game over).
- `pyscript.select_palette`: Applies a palette (`speakeasy`, `lofi`, `synthwave`, `cyberpunk`, `nordic`, `blood_moon`).
- `pyscript.effect_bar_toast`: "Toast" celebration effect (amber bar & stairs).
- `pyscript.effect_eagles_chant`: Manual Eagles Kelly Green chant effect (see §4).
- `pyscript.team_lights_celebrate`: Plays a celebration (`kind: big|small`) in the featured team's color.
- `pyscript.basement_all_off`: Master basement lights blackout (header chip, visible when `binary_sensor.basement_lights_active` is on).
- `pyscript.bedroom_goodnight` (bedroom.py): Bedroom dashboard Goodnight chip. Fades the bedroom lamps off, then runs `basement_all_off` if basement lights are on and neither the theater nor Social Mode is in use.

### Sports, State Flags & Virtual Entities
- `sensor.philadelphia_eagles`: ESPN Team Tracker (`PRE`, `IN`, `POST`; Attributes: `team_score`, `team_colors`, `opponent_name`).
- `sensor.nba_philadelphia_76ers`, `sensor.mlb_philadelphia_phillies`, `sensor.nhl_philadelphia_flyers`: the other Team Tracker teams. Team Lights uses them for color and celebrations only while the TV is on sports (docs/team-lights.md). Excluded from the recorder.
- `pyscript.team_lights_featured`: Team Lights' featured team (state = name; attributes `sensor`, `rgb`, `light_colors`, `sport`, `live`). Read by `basement.py` (sports paint, stairs), the theater poster and the now-playing banner.
- `input_select.featured_team`: `Auto`, `Eagles`, `Flyers`, `76ers`, `Phillies`. Picks the featured team while its game is live; Auto = playoffs first, then that order.
- `binary_sensor.team_games_overlap`: On when two or more `*_game_soon` sensors are on; shows the Featured Team picker on the home dashboard.
- `binary_sensor.eagles_game_soon`, `binary_sensor.sixers_game_soon`, `binary_sensor.phillies_game_soon`, `binary_sensor.flyers_game_soon`: Template (`packages/sports.yaml`, macro in `custom_templates/sports.jinja`). On while that team's game is live, starts within 24 hours, or started less than 12 hours ago. Each one gates its team's card on the home dashboard.
- `binary_sensor.basement_automation_allowed`: Master safety gate; if `off`, suppresses automated sports flashes and macros.
- `binary_sensor.theater_in_use`: High when `media_player.theater_receiver == 'on'`.
- `pyscript.curtain_call_active`: on while curtain call (`session_end_house_lights` in `theater.py`) runs and through the house-lights window after it (10 minutes, then for as long as the mmWave sees someone). While it is on, `basement.py` keeps the room lit for people leaving (Adaptive Lighting off, stairs motion ignored), and the basement door closing turns everything off.
- `binary_sensor.theater_announcer_bar`: Set by `theater.py` `update_announcer_bar()`. On while the theater is in use and in sports mode, or in movie mode with a sports app or Prime Video in the foreground. Shows the booth announcer bar.
- `binary_sensor.basement_lights_active`: High when dimmer, lounge, or bias strip are ON.
- `binary_sensor.theater_media_playing`: Template (`packages/theater.yaml`). On while theater media is playing: `media_player.whole_house_spotify` in music mode, otherwise `media_player.theater_onn_pro_adb`. Drives the header play/pause chip.
- `input_select.basement_lighting_mode`: Active room mode (`Daily Driver`, `Social Mode`). ("Movie Mode" is a legacy input value, auto-converted to `Daily Driver` by `set_lighting_mode()` — theater lighting behavior is driven by `binary_sensor.theater_in_use` / `sensor.theater_mode`, not a distinct lighting-mode value.)
- `input_select.basement_theater_mode`: AV intent (`Movie`, `Game`, `Music`, `Sports`, `Off`).
- `sensor.theater_mode`: Hardware status resolver (`movie`, `game`, `music`, `sports`, `off`).
- `sensor.theater_current_poster`: Active movie/streaming poster URL and metadata attributes. The `source` attribute shows where the art came from (`tmdb`, `cinemeta`, `tvmaze`, `steamgriddb`, `libretro`, `*_title_match` or brand fallbacks), which is the quickest way to confirm lookups are resolving.
- `sensor.theater_current_boxart`: Dedicated retro gaming box art and hero backdrop sensor (SteamGridDB / RAWG / Libretro / curated `SYSTEM_ART_MAP` fallback per-system).
- `sensor.basement_palette`: Active palette (`speakeasy`, `lofi`, `synthwave`, `cyberpunk`, `nordic`, `blood_moon`).
- `sensor.basement_effect`: Active animation modifier (`static`, `drift`).
- `pyscript.toggle_ambient_drift`: Service toggling between static mood lock and 22s hardware spatial drift.
- `sensor.tuner0` / `sensor.tuner1`: Per-tuner HDHomeRun state, feeding `sensor.hdhomerun_tuner_allocation`.
- `sensor.hdhomerun_tuner_allocation`: Real-time ATSC tuner state (`0/2 active (idle)`, `1/2 active`, `2/2 saturated`).
- `binary_sensor.hdhomerun_contention_risk`: High when both physical ATSC tuners are saturated while theater is not currently in sports mode.
- `input_boolean.xteve_tuner_reservation`: Master policy switch enforcing 1-tuner reservation buffer for the basement theater.
- `pyscript.preempt_tuner_for_theater`: Force-releases a tuner (default Tuner 1) so the basement can lock it, dropping whatever remote Tailscale/xTeVe stream held it. Talks to the HDHomeRun FLEX DUO over its TCP control protocol (port 65001: `/tunerN/lockkey force`, then `/tunerN/channel none`); the device has no HTTP endpoint for this. Returns `False` and sends a failure ntfy if the device refuses.

### Dashboard Summary Sensors
Template sensors that hold logic the dashboards used to repeat inline. Cards read these instead of recomputing.
- `sensor.commute_am_severity` / `sensor.commute_pm_severity` (`packages/commute.yaml`): `ok`, `warn` or `alert`, from `sensor.septa_commute`. Sets the colour of the kitchen commute cards.
- `binary_sensor.partner_heading_home` (`packages/commute.yaml`): on 3 minutes after the commuter leaves work on a weekday; off at home, back at work, at midnight, or 3 hours after leaving.
- `sensor.city_trains` (`pyscript/city_trains.py`, made by `state.set`, so it doesn't exist after a restart until the first lookup): the kitchen "Trains to the city" answer. `idle`, `loading`, `ready` or `error`; attributes `trains` (next three from home: `leave_by`, `depart`, `arrive`, `delay`, `status`, `change_train`), `alerts`, `advisories`, `looked_up_at`. Filled only by `pyscript.city_trains_lookup` (the kitchen button) and back to `idle` 20 minutes later.
- `sensor.trains_home` (`pyscript/city_trains.py`, same shape as `sensor.city_trains`, plus `from_station`): the Home dashboard's "Trains home" answer, filled only by `pyscript.trains_home_lookup`.
- `binary_sensor.in_center_city` (`pyscript/city_trains.py`, `state.set`): on while either of us is within 1.5 km of a Center City station (Suburban, Jefferson, 30th Street), not home, with a GPS position under 30 minutes old. Attributes `station` (nearest) and `walk_minutes` (from the straight-line distance). Updated on position changes and every 5 minutes; shows the Home dashboard's Trains home button.
- `binary_sensor.transit_microservice` (REST sensor in `configuration.yaml`): whether the commute service on `127.0.0.1:8000` answers. `pyscript/watchdog.py` alerts after it has been off for 2 minutes.
- `sensor.maintenance_attention` (`packages/house_status.yaml`): number of things needing attention (worn parts, batteries at or below 20%, device problem flags, due or overdue chores, each chore counted once). The `items` attribute holds the display lines for the Maintenance page's "Needs Attention" card; the Home tile shows the count.
- `sensor.cameras_online` (`packages/house_status.yaml`): number of reachable cameras; attributes `total` and `offline` (list of cameras that are unavailable or unknown). Feeds the Home Security tile.
- `sensor.next_calendar_event` (`packages/house_status.yaml`): title of the soonest event across the household calendars; the `when` attribute is the formatted date and time.
- The maintenance and calendar logic lives in `custom_templates/house_status.jinja`. After editing it, run `homeassistant.reload_custom_templates`, then `template.reload`.

### Work schedule (`packages/private_work_schedule.yaml`)
- `schedule.partner_office_days` / `schedule.me_office_days`: on all day on each person's office days. The only place the days are set. The train windows (`binary_sensor.septa_display_window`, `septa_am_window`, `septa_pm_window`) and location sharing with the transit service follow the partner's; `binary_sensor.drive_display_window` follows mine. Reload with `schedule.reload`.
- `binary_sensor.kitchen_morning_wake` (`packages/kitchen_display.yaml`): kitchen tablet screen in the morning, 6-9 AM on weekdays whether or not anyone commutes, 8-11 AM on weekends.
- `binary_sensor.kitchen_evening_wake` (`packages/kitchen_display.yaml`): kitchen tablet screen on, 4-8 PM every day.
- `binary_sensor.kitchen_show_pm_commute` (`packages/kitchen_display.yaml`): shows the train-home card once the commuter has left work (`binary_sensor.partner_heading_home`) until they're home. Without a live location it falls back to fixed hours.
- `switch.kitchen_tablet_mains`: the kitchen tablet's charger plug. `pyscript/kitchen_tablet.py` switches it to hold the battery around 70-80%.
- `sensor.big_tablet_battery_level`: the kitchen tablet's battery level (Companion app).

### Presence (`packages/presence.yaml`)
- `binary_sensor.partner_home` / `binary_sensor.me_home`: on while the phone answers on the home WiFi, or Google Maps (`sensor.partner_location` / `sensor.me_location`) has said `home` for 5 minutes; off 3 minutes after both are gone. An unknown or unavailable Maps location counts as home. The 5-minute hold is there because Maps can read "home" briefly when someone just passes nearby. These keep the history of who was home; the `person.*` entities follow only the Companion apps and are not used for presence.
- `binary_sensor.partner_phone_on_wifi` / `binary_sensor.me_phone_on_wifi`: command_line ARP checks of each phone's reserved LAN address every 30 s (recorder-excluded; a sleeping iPhone flaps). A miss alone never means away.
- `binary_sensor.partner_maps_home` / `binary_sensor.me_maps_home`: Maps `home` held 5 minutes.
- `binary_sensor.partner_away` / `binary_sensor.me_away`: the home sensor is off (drives the kitchen away map). `binary_sensor.anyone_home`: off only when both are away (kitchen tablet screen).
