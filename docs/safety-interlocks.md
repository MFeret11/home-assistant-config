# Hardware Safety Interlocks (full detail)

_Moved verbatim from AGENTS.md. "§N" references point to the old AGENTS.md sections (§4 lighting/sports now live in docs/lighting.md)._

### Hardware Safety Interlocks
1. **Optoma Projector Thermal Cutoff**:
   - `safe_projector_cooldown()`: Mandatory 90s cooldown delay -> poll `sensor.projector_current` every 10s (max 15 attempts).
   - Requires **2 consecutive reads <= 0.06A** before opening `switch.projector`.
   - Protects against power cuts during `movie`, `game`, and `sports` modes.
   - If sensor reads `unavailable` or verification fails, mains remain closed to preserve lamp cooling fans.
2. **Batocera File System Safety**:
   - Clean shutdown initiated via software command.
   - `switch.batocera` opens only after `sensor.batocera_current < 0.05A` holds continuously for 12s.
3. **Shutdown Sequence (`session_end_house_lights`)**:
   - Send CEC `SLEEP` to Onn Pro -> wait 2.5s -> turn off `media_player.theater_receiver` and `media_player.theater_receiver_zone_2`.
   - Return `input_select.basement_lighting_mode` to Daily Driver (`end_social_mode()`) and re-enable Adaptive Lighting.
   - Reset Center channel trim to flat 0.0 dB -> initiate `safe_projector_cooldown()`.
4. **Post-Power-Outage Restoration Sweep (`post_power_restoration_sweep`)**:
   - Triggers only after a real power cut: `power_restoration_on_boot()` (`@time_trigger("startup")`) runs the sweep only if the Pi's own uptime (`/proc/uptime`) is under 15 minutes (`POWER_RESTORE_BOOT_WINDOW_S`). HA restarts and pyscript reloads also fire "startup" but leave host uptime high, so they skip it. `post_power_restoration_sweep` stays a `@service` for on-demand use.
   - 45s settling delay for ZHA Zigbee mesh & Wi-Fi integrations to register initial state.
   - Evaluates occupancy: if basement is vacant (no motion, door closed, theater off, presence not locked), sweeps all basement lights (`light.theater_dimmer`, `light.zigbee_basement_lights`, `light.stairlights`, `switch.bias_lights`, and Zone 2) OFF.
   - Also sweeps bedroom lamps (`light.zigbee_bedroom_lights`, `light.bedroom_lamp_1`, `light.bedroom_light_2`) OFF to prevent mains smart bulbs from burning unattended after a power cut.
   - Dispatches a push notification via `notify.ntfy` confirming the swept areas.
5. **HDHomeRun Dual-Tuner Preemption Guard (`ensure_hdhomerun_tuner_available`)**:
   - Protects against broadcast lockout when family members stream live TV remotely over Tailscale / xTeVe (`100.82.195.2`).
   - Real-time monitoring across `sensor.tuner0` and `sensor.tuner1`.
   - When `play_sports()` or `launch_app("hdhomerun")` is invoked in the basement, if both physical ATSC tuners are saturated, `pyscript.preempt_tuner_for_theater()` force-releases Tuner 1 over the HDHomeRun TCP control protocol (port 65001: `lockkey force`, then `channel none`), dropping the remote session. If the device refuses, the ntfy says preemption failed instead of claiming success.
   - Enforces a 0.6s RF demodulator settling window before Onn 4K Pro launches `com.silicondust.view` to guarantee 100% first-time stream acquisition.
   - Dispatches a high-priority push notification via `notify.ntfy` with the outcome.

