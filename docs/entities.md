# Verified Entity Dictionary

_Moved verbatim from AGENTS.md. "§N" references point to the old AGENTS.md sections (§4 lighting/sports now live in docs/lighting.md)._

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
- `media_player.whole_house_spotify`: Spotify Connect target — Spotify audio/playback state lives here, not on `media_player.onn_pro`. Does not support `media_pause` on every state; `pause_spotify_if_playing()` checks `supported_features` first.
- `sensor.mediasession2mqtt_1_playback_state` / `sensor.mediasession2mqtt_1_application_id`: Onn media-session playback state and foreground app package ID (drives dashboard play/pause icon and sports-app detection). Reports whichever session changed last, not necessarily the foreground app; `media_player.onn_pro` `app_id` is the foreground source of truth.
- `switch.batocera`: Smart plug hardware relay powering Batocera PC (Endpoint on Third Reality Dual Plug 2).
- `switch.batocera_console`: Template switch. Off = clean shutdown via `button.batocera_shutdown_2` (never opens the relay directly; the relay opens only via the 12s current-draw interlock). On = closes `switch.batocera` relay (PC boots via BIOS power-on-after-AC-restore). State reflects `sensor.batocera_state` in (`playing`, `idle`).
- `button.batocera_shutdown_2`: Clean Batocera shutdown button (dashboard power sub-button).
- `sensor.batocera_current`: Current draw in Amperes ($A$) for Batocera PC.
- `sensor.batocera_state`: EmulationStation state (`playing`, `idle`).
- `sensor.batocera_current_game` / `sensor.batocera_system`: Active ROM metadata. When Batocera is streaming the ROG PC through its Moonlight client, the system is `moonlight` and the game is `steam-big-picture`; Steam shortcuts report as `<appid>_<Title_With_Underscores>` and are cleaned before art lookup.
- `switch.gaming_pc`: ASUS ROG Gaming PC power switch (WOL boot, clean shutdown via `button.desktop_rspn8nu_shutdown`).
- `binary_sensor.gaming_pc_online`: High-speed ICMP connectivity ping for ROG Gaming PC.
- `sensor.desktop_rspn8nu_activewindow`: HASS.Agent active window title sensor; sanitized to extract active PC game titles, Steam Big Picture Mode, and idle launcher states. Drives SteamGridDB / RAWG poster resolution and Cinema Shield blackout.
- `sensor.desktop_rspn8nu_gputemperature`: HASS.Agent GPU temperature telemetry in °C; surfaced live on dashboard cards and Now Playing marquee subtitle.
- `button.desktop_rspn8nu_shutdown`: Clean Windows OS software shutdown button.
- `switch.bias_lights`: Screen backlight strip relay (Endpoint on Third Reality Dual Plug 1).
- `input_number.theater_announcer_volume`: Announcer voice level slider (Center channel speaker trim: -10.0 dB to +10.0 dB). Dynamically synced in real time to hardware via PyScript.
  - *Hardware Limit Constraint*: Yamaha RX-V673 internal DSP firmware hard-codes individual speaker pre-out level trims (`<Speaker_Preout><Pattern_1><Lvl><Center>`) between `-10.0 dB` and `+10.0 dB`. The AVR has no network command for true per-speaker channel muting. At `-10.0 dB`, voice loudness is reduced to ~1/4 to sit under stadium crowd noise. (Setting Center to `None` is strictly avoided as it automatically downmixes commentary into Front L/R).
- `input_select.theater_announcer_preset`: 3-way segmented audio toggle (`Stadium Crowd`, `Broadcast Ref`, `Dialogue Boost`). Only 1 preset active at a time; automatically drives Center channel trim (`-10.0 dB`, `0.0 dB`, `+3.0 dB`) and keeps `input_number.theater_announcer_volume` in sync while occupying minimal dashboard space.
- `pyscript.theater_set_announcer_preset`: Service setting the active 3-way announcer preset and dispatching YNC XML center trim.
- `rest_command.yamaha_set_center_trim`: Sends YNC XML speaker level payload to Yamaha RX-V673 over HTTP.
- `rest_command.yamaha_master_volume_step`: Sends YNC XML volume step (`Up 1 dB` / `Down 1 dB`) to Yamaha RX-V673 Main Zone.
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
- `switch.basement_adaptive_lighting_adaptive_lighting_basement_adaptive_lighting`: Adaptive Lighting master switch.
- `input_select.basement_lighting_mode`: `Daily Driver` / `Social Mode`. The single source of truth for Social Mode (which is also the presence lock). The old `input_boolean.party_mode` / `input_boolean.presence_override` were removed.
- `pyscript.basement_social_source`: who engaged Social Mode: `manual`, `sports`, or `none`. Only `sports` Social drops back to Daily when the theater switches to a movie or game.
- `pyscript.toggle_lighting_mode`: Toggles Daily Driver / Social Mode (dashboard header chip, Room Ambience card).
- `pyscript.mood_reset_normal`: Resets room to normal Daily Driver lighting (header chip hold action, game over).
- `pyscript.select_palette`: Applies a palette (`speakeasy`, `lofi`, `synthwave`, `cyberpunk`, `nordic`, `blood_moon`).
- `pyscript.effect_bar_toast`: "Toast" celebration effect (amber bar & stairs).
- `pyscript.effect_eagles_chant`: Manual Eagles Kelly Green chant effect (see §4).
- `pyscript.basement_all_off`: Master basement lights blackout (header chip, visible when `binary_sensor.basement_lights_active` is on).

### Sports, State Flags & Virtual Entities
- `sensor.philadelphia_eagles`: ESPN Team Tracker (`PRE`, `IN`, `POST`; Attributes: `team_score`, `team_colors`, `opponent_name`).
- `binary_sensor.basement_automation_allowed`: Master safety gate; if `off`, suppresses automated sports flashes and macros.
- `binary_sensor.theater_in_use`: High when `media_player.theater_receiver == 'on'`.
- `binary_sensor.theater_announcer_bar`: Set by `theater.py` `update_announcer_bar()`. On while the theater is in use and in sports mode, or in movie mode with a sports app or Prime Video in the foreground. Shows the booth announcer bar.
- `binary_sensor.basement_lights_active`: High when dimmer, lounge, or bias strip are ON.
- `input_select.basement_lighting_mode`: Active room mode (`Daily Driver`, `Social Mode`). ("Movie Mode" is a legacy input value, auto-converted to `Daily Driver` by `set_lighting_mode()` — theater lighting behavior is driven by `binary_sensor.theater_in_use` / `sensor.theater_mode`, not a distinct lighting-mode value.)
- `input_select.basement_theater_mode`: AV intent (`Movie`, `Game`, `Music`, `Sports`, `Off`).
- `sensor.theater_mode`: Hardware status resolver (`movie`, `game`, `music`, `sports`, `off`).
- `sensor.theater_current_poster`: Active movie/streaming poster URL and metadata attributes. The `source` attribute shows where the art came from (`tmdb`, `cinemeta`, `tvmaze`, `steamgriddb`, `libretro`, `*_title_match` or brand fallbacks), which is the quickest way to confirm lookups are resolving.
- `sensor.theater_current_boxart`: Dedicated retro gaming box art and hero backdrop sensor (SteamGridDB / RAWG / Libretro / curated `SYSTEM_ART_MAP` fallback per-system).
- `sensor.basement_palette`: Active palette (`speakeasy`, `lofi`, `synthwave`, `cyberpunk`, `nordic`, `blood_moon`).
- `sensor.basement_effect`: Active animation modifier (`static`, `drift`).
- `pyscript.toggle_ambient_drift`: Service toggling between static mood lock and 22s hardware spatial drift.
- `pyscript.get_team_rgb()`: Exposed as a `@service` (sports module) so both `sports.py` and `basement.py`'s `effect_eagles_chant` pull the same live team color — no more hardcoded/divergent greens between the two.
- `sensor.tuner0` / `sensor.tuner1`: Per-tuner HDHomeRun state, feeding `sensor.hdhomerun_tuner_allocation`.
- `sensor.hdhomerun_tuner_allocation`: Real-time ATSC tuner state (`0/2 active (idle)`, `1/2 active`, `2/2 saturated`).
- `binary_sensor.hdhomerun_contention_risk`: High when both physical ATSC tuners are saturated while theater is not currently in sports mode.
- `input_boolean.xteve_tuner_reservation`: Master policy switch enforcing 1-tuner reservation buffer for the basement theater.
- `pyscript.preempt_tuner_for_theater`: Force-releases a tuner (default Tuner 1) so the basement can lock it, dropping whatever remote Tailscale/xTeVe stream held it. Talks to the HDHomeRun FLEX DUO over its TCP control protocol (port 65001: `/tunerN/lockkey force`, then `/tunerN/channel none`); the device has no HTTP endpoint for this. Returns `False` and sends a failure ntfy if the device refuses.

