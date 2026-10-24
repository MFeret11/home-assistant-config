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

YouTube is left unmapped, so it opens YouTube as normal. **Power** and **Star** can't be remapped: Button Mapper never sees them because the system handles them first.

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

- **Power button gives a half-on theater.** The cooldown cuts `switch.projector` mains after every session, so a power-button press wakes the Onn and, over CEC, the receiver, but the projector stays dark. `binary_sensor.theater_in_use` still turns on and the theater lighting reacts. The Netflix button (`movie`) is the working "theater on" button. Possible fix: start a mode when the Onn and the receiver both wake within a few seconds while the theater is off. Don't trigger on the Onn waking alone, because scrcpy, casting and updates wake it too.
- **Game mode and the remote.** The picture is on HDMI2 while the remote still talks to the Onn. A press may wake the Onn, and CEC could pull the receiver back to HDMI1. Not yet confirmed.
