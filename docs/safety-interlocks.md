# Hardware Safety Interlocks (full detail)

_Moved verbatim from AGENTS.md. "§N" references point to the old AGENTS.md sections (§4 lighting/sports now live in docs/lighting.md)._

### Hardware Safety Interlocks

Interlocks 1 and 2 run in `pyscript/interlocks.py` (split out of `theater.py` 2026-10-28). Pyscript reloads a file when it is saved and kills that file's running tasks, so a cooldown started from theater.py died whenever theater.py was edited. Now theater.py reaches it only through services (`pyscript.cancel_projector_cooldown`, `pyscript.shutdown_batocera`), whose wrappers never raise: if interlocks.py is not loaded, nothing cuts mains. `task.unique` names are per file, so theater.py can't cancel the cooldown with `task.unique`; it must use the cancel service. interlocks.py must not import or call theater.py (`test_interlocks_file_stands_alone` checks this). Interlocks 3–5 stay in theater.py / basement.py: they are short sequences, not long-running tasks.

1. **Optoma Projector Thermal Cutoff**:
   - **Model: Optoma HD146X** (system FW C03, MCU C01). No RS-232 or network port; control is CEC (unreliable), IR, or mains. Menu settings (2026-11-01): Direct Power On On, Signal Power On On, Auto Power Off 5 min (backstop when CEC standby fails; 0 would disable it), HDMI Link On, Power On Link Mutual, Power Off Link On. Eco standby (~0.1 W) has no Active option in the menu.
   - **Standby by default (2026-10-29)**: session end no longer cuts mains. The projector cools itself in standby and CEC can wake it again. Standby draws about 0.01A (Eco standby; its CEC wake doesn't work, see below).
   - Automatic mains cuts happen only with the lamp cold (<= 0.06A):
     - `play_music()` (theater.py) cuts mains before the receiver wakes, so CEC can't strike the lamp, and leaves them off.
     - `_wake_projector()` (theater.py, 2026-11-01) starts the projector for every other mode and the power button. CEC One Touch Play times out from Eco standby, but Direct Power On is enabled, so it cycles the relay: two cold reads 1s apart, off, 3s, on. If mains are already off it only switches them on. A projector that is still cooling (0.06–0.5A) is never cut: it rechecks every 30s for up to 3 min and cycles once cold. An unavailable current sensor never counts as cold. If the session ends or switches to music during the 3s, mains stay off. It is the only code that switches mains on for a mode.
   - **Stray wake guard** (`projector_stray_wake_guard`, interlocks.py): lamp > 0.5A held 120s while `binary_sensor.theater_in_use` is off (scrcpy, updates and casting wake the Onn but not the receiver; any real session turns the receiver on). If the Onn is on: CEC `SLEEP` (never `media_player.turn_off`, which sends a POWER toggle and re-woke the Onn), wait 60s, retry once. If the Onn is off, HA can't send standby, so it only warns (someone may be using the projector's own remote). Either way it posts a persistent notification and ntfy, and never cuts mains. It also catches a session end whose CEC standby didn't take (what the cooldown's CEC re-sends used to do).
   - The cooldown below is kept for manual use (`pyscript.safe_projector_cooldown`); nothing calls it automatically.
   - `safe_projector_cooldown()`: Mandatory 90s cooldown delay -> poll `sensor.projector_current` every 10s (max 25 attempts, about 4 minutes after the 90s wait).
   - Requires **2 consecutive reads <= 0.06A** before opening `switch.projector`.
   - Every `play_*` service except `play_music` cancels a running (manually started) cooldown (`pyscript.cancel_projector_cooldown`). The call is not instant, so the loop's own checks also abort it: any `movie`/`game`/`sports` mode stops it, and the final cut needs mode `music` or `off`.
   - Protects against power cuts during `movie`, `game`, and `sports` modes.
   - If sensor reads `unavailable` or verification fails, mains remain closed to preserve lamp cooling fans.
2. **Batocera File System Safety**:
   - Clean shutdown initiated via software command.
   - `shutdown_batocera` (button press) and `batocera_auto_power_off` (relay) are in interlocks.py; theater.py's `reset_boxart_on_batocera_halt` uses the same trigger only to reset the box art.
   - `switch.batocera` opens only after `sensor.batocera_current < 0.05A` holds continuously for 12s.
3. **Shutdown Sequence (`session_end_house_lights`)**:
   - Raise house lights first (`pyscript.curtain_call_active` on, Adaptive Lighting on) so the room isn't dark during the CEC steps.
   - Pause Spotify and start the clean Batocera shutdown (`_teardown_conflicting_sources("off")`, then again explicitly; the repeat is harmless).
   - Onn: when gaming (mode `game`, HDMI2/HDMI3, or Batocera on) send only CEC `SLEEP`, never HOME or HDMI1; otherwise `HOME`, 0.5s, then `SLEEP`. Either way `media_player.onn_pro` is turned off.
   - Wait for the projector (`_wait_projector_dark`, 2026-10-31): poll `sensor.projector_current` every 2s for up to 24s with the receiver still on, since the projector needs ~15s to act on CEC standby and an early receiver off breaks the CEC path. If the lamp is still lit and the session wasn't gaming (`_gaming_on_hdmi2`: mode `game`, receiver on HDMI2/HDMI3, or Batocera relay on), wake the Onn once, wait 10s, resend `SLEEP` and wait again. An unavailable sensor skips the wait. Never cuts mains.
   - Receiver to `AUDIO1` (cuts HDMI pass-through), 0.5s.
   - `_cec_standby_burst(rounds=2)`: each round re-sends `SLEEP` if the Onn still reads on (1s), then receiver `AUDIO1` (0.5s) and off (2s); stops early once `sensor.projector_current` < 0.5A. By this point the projector has normally gone dark already.
   - Turn off `media_player.theater_receiver` and `media_player.theater_receiver_zone_2`.
   - Return `input_select.basement_lighting_mode` to Daily Driver (`end_social_mode()`) and re-enable Adaptive Lighting.
   - Reset Center channel trim to flat 0.0 dB. Projector mains stay on (standby); the stray wake guard covers a lamp that stays lit.
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

