# Onn Remote Buttons

The Onn 4K Pro remote's app shortcut buttons and its Guide button trigger theater modes and lighting through Home Assistant. Set up 2026-10-24.

## How it works

1. **Button Mapper (Pro)** runs on the Onn. It catches the button press through an Accessibility service (battery optimization is off for it, so Android doesn't stop it) and blocks the button's normal action.
2. It sends an **HTTP POST** over the LAN to `http://<pi-lan-ip>:8123/api/webhook/<id>?button=<action>`. The request needs no body.
3. The `onn_remote_buttons` automation in `packages/onn_remote.yaml` reads the `button` value and calls the matching pyscript service.

The webhook ID lives in `secrets.yaml` as `onn_remote_webhook_id`. It is the only thing protecting the endpoint on the LAN (`local_only: true`), so keep it out of the repo. The automation is YAML rather than pyscript so it can use `!secret`. After editing the package, reload automations (Developer Tools → YAML → Automations).

## Button map

Action names describe what happens, not which button sends them. To move an action to another button, change only that button's URL in Button Mapper.

| Remote button | Button Mapper code | Press | `?button=` | Service |
|---|---|---|---|---|
| Netflix | `BUTTON_4` | single | `movie` | `pyscript.play_movie` (Stremio, blackout) |
| Paramount+ | `BUTTON_10` | single | `music` | `pyscript.play_music` (Spotify, 7ch Stereo) |
| Disney+ | `BUTTON_9` | single | `game` | `pyscript.play_game` (Batocera, HDMI2) |
| Free TV | `FEATURED_APP_1` | single | `sports` | `pyscript.play_sports` (HDHomeRun, team colors) |
| Guide (TV icon) | `GUIDE` | single | `social` | `pyscript.toggle_lighting_mode` (Daily Driver ↔ Social) |
| Guide (TV icon) | `GUIDE` | double | `lights` | `pyscript.toggle_all_basement_lights` |
| Guide (TV icon) | `GUIDE` | long | `eagles` | `pyscript.effect_eagles_chant` |
| YouTube | (mapped 2026-11-01) | long | `curtain` | `pyscript.session_end_house_lights` (curtain call, any mode; the way to end a game session) |

A single YouTube press still opens YouTube. **Power** and **Star** can't be remapped: Button Mapper never sees them because the system handles them first.

**Power button = curtain call (2026-10-31).** When the Onn goes from on to off and stays off for 4s while the theater is in use and the receiver is on, `onn_power_button_curtain_call` (theater.py) runs `session_end_house_lights`. It skips game mode (theater mode `game`, receiver on HDMI2/HDMI3, or Batocera's relay on), an `unavailable` flicker, and a session end that is already running.

**Power button = movie button (2026-11-01).** CEC from the Onn waking never turns on the Yamaha and only sometimes wakes the projector, so HA finishes the job. `onn_power_button_wake` (theater.py) waits 2s after the Onn goes from off to on, then, if the theater isn't in use, the receiver is still off, session end isn't running (`_session_ending`; curtain call's 10-min house-lights flag doesn't block it) and `binary_sensor.theater_mmwave_sensor` sees someone, it runs `play_movie`: projector, receiver on HDMI1 with Standard audio, movie lighting. Stremio opens only if the Onn is on its home screen 1.5s later; a YouTube single press (not caught by Button Mapper) wakes the Onn into YouTube, and the theater starts around it. An app button also wakes the Onn, but its webhook starts its own mode within about 0.5s, so the handler backs off. The presence check keeps scrcpy, casting and overnight updates from starting the theater.

Because Guide has a double press mapped, its single press waits about 300 ms. The app buttons fire immediately.

## Testing

- `?button=test` (or any unknown name) runs nothing and logs `Onn remote webhook: unknown button '<name>'` as a warning. Use it to check the connection without starting a mode.
- Every real action runs the full mode: `movie`, `game` and `sports` power the projector.
- Check presses with `docker logs homeassistant 2>&1 | grep "Onn remote"`.

## Controlling the Onn from a computer

Use scrcpy over ADB to see and control the Onn's screen without the remote, for example to edit Button Mapper URLs (Ctrl+V pastes the computer's clipboard).

- On the Onn: Developer options → **USB debugging** on. This opens ADB on port 5555. Wireless debugging won't stay on because the Onn is on Ethernet, and it isn't needed.
- On the computer: `scrcpy --tcpip=<onn-ip>:5555`, and approve the computer once on the TV ("Always allow").
- scrcpy wakes the Onn but not the receiver or projector.
- While scrcpy is connected, `media_player.onn_pro` flickers between `on` and `unavailable` because HA's ADB connection and scrcpy compete. Close scrcpy when done.

## Known gaps

- **Onn ignoring SLEEP (open, 2026-11-01).** From about 15:41 UTC the Onn stopped acting on `remote.send_command SLEEP` (curtain call and the stray-wake guard both sent it; the Onn stayed on, even after a restart). It worked at 15:02. It began while Button Mapper was being edited for the YouTube long press; check whether Button Mapper is catching the key. While the Onn stays awake, the projector keeps a signal and Auto Power Off can't run.

- **Waking the projector (fixed 2026-11-01).** The projector's CEC wake doesn't work from its Eco standby (One Touch Play over ADB times out; Power On Link is already Mutual), so the power button never started it on its own. Before 2026-10-29 it seemed to, because every mode switched its mains on and Direct Power On started it. `_wake_projector()` now does that on purpose: with the lamp cold it cycles the relay (off, 3s, on); with mains already off it switches them on. Movie, sports, game, PC game and the power button use it; `play_music` never does. See docs/safety-interlocks.md for the cold-lamp rules.
- **Onn left awake after curtain call (fixed 2026-11-01).** `media_player.turn_off` on the Onn sends POWER, a toggle, whenever HA still thinks it is on. Sent right after `SLEEP`, it woke the Onn back up with a dark screen, and the next power-button press turned it off. Everything now sleeps the Onn with `SLEEP` only.
- **Game mode and the remote (fixed 2026-10-28).** The Disney+ press also wakes the Onn, and about 8s later CEC pulls the receiver back to HDMI1. `play_game()` now starts `_hold_receiver_on_hdmi2()`, which checks every 3s for 30s and switches back to HDMI2. Starting another mode or ending the session stops it.
