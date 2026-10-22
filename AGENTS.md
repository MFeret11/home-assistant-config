# Basement Theater & Broadcast Automation Architecture

You are an expert Home Assistant and PyScript engineer. This file holds the rules most tasks need. Details live in `docs/`; open the file named below before doing the matching kind of work.

## System basics
- Home Assistant Container on a Raspberry Pi 4, named volume `ha_config:/config` (`network_mode: host`). This repo is that live volume.
- Alert channel: `notify.ntfy`.
- Secrets: API keys (TMDB, SteamGridDB, RAWG) and device credentials live in `secrets.yaml`. Never inline credentials in docs, dashboards, or pyscript.

## Hardware safety interlocks (all five; full detail in docs/safety-interlocks.md)
1. **Projector thermal cutoff**: never open `switch.projector` directly. `safe_projector_cooldown()`: mandatory 90s cooldown, then poll `sensor.projector_current` every 10s (max 15 attempts); requires **2 consecutive reads <= 0.06A** before opening the relay. If the sensor reads `unavailable` or verification fails, mains stay closed so the lamp fans keep cooling.
2. **Batocera file system safety**: clean shutdown via software (`button.batocera_shutdown_2`) first; `switch.batocera` opens only after `sensor.batocera_current < 0.05A` holds continuously for 12s.
3. **Shutdown sequence (`session_end_house_lights`)**: CEC `SLEEP` to Onn → wait 2.5s → turn off `media_player.theater_receiver` and `media_player.theater_receiver_zone_2` → return `input_select.basement_lighting_mode` to Daily Driver, re-enable Adaptive Lighting → reset Center trim to 0.0 dB → `safe_projector_cooldown()`.
4. **Post-power-outage sweep (`post_power_restoration_sweep`)**: after a real power cut (Pi uptime < 15 min at HA startup; HA restarts and pyscript reloads skip it), wait 45s for ZHA/Wi-Fi to settle; if the basement is vacant, sweep all basement lights and the bedroom lamps OFF so mains smart bulbs never burn unattended after a power cut; notify via `notify.ntfy`.
5. **HDHomeRun tuner preemption (`ensure_hdhomerun_tuner_available`)**: when `play_sports()` or `launch_app("hdhomerun")` finds both tuners saturated, `pyscript.preempt_tuner_for_theater()` force-releases Tuner 1 over the HDHomeRun TCP control protocol (port 65001), dropping the remote xTeVe/Tailscale stream, waits 0.6s for the RF demodulator to settle before launching `com.silicondust.view`, and notifies via `notify.ntfy`.

## Rules that cause bugs when missed
- **Art lookups need `await`**: `_fetch_movie_or_tv_art()` and `_fetch_game_art_from_secrets()` must be called as `await ...`. Without it pyscript hands back an unawaited coroutine, so lookups never resolve and only fallback art shows.
- **DSP modes**: `set_receiver_sound_mode()` only selects names from the RX-V673 `sound_mode_list` (there are no `PLII ...` programs); use `SOUND_MODE_FALLBACKS` when needed.
- **Center trim**: hardware range is `-10.0 dB` to `+10.0 dB`. Never set Center to `None`; it downmixes commentary into Front L/R.
- **Sports flashes**: pulse brightness only, between 100% and `DIM_FLOOR_PCT = 15`, in solid team Kelly Green (`[0, 170, 35]` via `get_team_rgb()`). Never alternate RGB mid-flash (Zigbee congestion on 3rd Reality bulbs). Flashes end holding solid team green.
- **Recorder exclusions**: keep `sensor.projector_current`, `sensor.batocera_current` and `sensor.mediasession2mqtt_1_playback_position` excluded (DRAM-less SSD over USB). Keep `media_player.theater_receiver`, `sensor.projector_current_rounded` and `sensor.projector_power_state` recorded.
- **Spotify**: playback state lives on `media_player.whole_house_spotify`, not `media_player.onn_pro`; check `supported_features` before `media_pause`.
- **Foreground app**: `media_player.onn_pro` `app_id` is the source of truth; `mediasession2mqtt` reports whichever session changed last.

## Theater lighting (Daily Driver, `binary_sensor.theater_in_use` ON)
Theater governs the whole basement (`light.theater_dimmer` + `light.zigbee_basement_lights`):
- Movie/Game playing: full blackout, `switch.bias_lights` ON.
- Movie paused (4.0s debounce) and pre-show/menus/game idle: 1% dimmer glow, lounge/bar OFF, bias ON.
- Music: full blackout, bias ON, no glow state.
- Sports: auto-engages Social Mode, solid team color at 100%.
- In Social Mode, theater state never touches lights.

## Where to look
- **docs/entities.md**: read before adding, renaming or referencing any entity ID or pyscript service, so you use verified IDs instead of guessing.
- **docs/safety-interlocks.md**: read before changing anything that powers off the projector, Batocera, receiver or tuners, or the startup sweep.
- **docs/theater-audio.md**: read before touching receiver input, DSP or sound mode, center trim, app-to-mode mapping, art lookups, or other `theater.py` logic.
- **docs/lighting.md**: read before changing `basement.py` or `sports.py`: Social/Daily Driver behavior, stairs and direction-of-travel timings, vacancy, palettes, or Eagles flash cadence.
- **docs/dashboard.md**: read before editing `dashboards/basement.yaml`, its components or the decluttering templates.
- **docs/network.md**: read before work involving device IPs, ports, Tailscale/xTeVe, the Zigbee coordinator, or recorder/database tuning.
- **docs/roadmap.md**: read before starting Karaoke mode or other planned features.
