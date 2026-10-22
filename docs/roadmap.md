# Future Roadmap

_Moved verbatim from AGENTS.md. "§N" references point to the old AGENTS.md sections (§4 lighting/sports now live in docs/lighting.md)._

## 5. Future Planned Roadmap

### Karaoke Mode Architecture
- **Audio Routing**: Yamaha RX-V673 `HDMI1` or analog AUX mixed feed using `7ch Stereo` (uncompressed low-latency live vocals across all speakers, avoiding matrix phase echo). Center channel set to `Dialogue Boost` (`+3.0 dB`) to prioritize microphone vocals over backing tracks.
- **Video Source**: Onn 4K Pro deep-linking to YouTube (`com.google.android.youtube.tv`) for instrumental lyric tracks, or dedicated Android TV karaoke client.
- **Lighting & Ambiance**: Auto-engages `Social Mode` with overhead `light.theater_dimmer` at a safe 15% warm glow, screen bias strip ON, and the 9 basement Zigbee bulbs painted in `synthwave` or `cyberpunk` with ambient spatial drift.
- **Control**: Exposed as a 5th mode in `input_select.basement_theater_mode` (`Karaoke`) with `pyscript.play_karaoke()` and an inline `theater_mode_button` card.

## Backlog

### Dead-man's-switch heartbeat (healthchecks.io)
ntfy alerts come from HA itself, so nothing reports when the Pi, power or the `homeassistant` container dies. Plan:
- Create a free healthchecks.io check (period 5 min, grace 10 min) with a phone integration (healthchecks app, email or ntfy).
- Put the ping URL in `secrets.yaml` as `healthchecks_ping_url` (never inline it).
- Add a 5-minute `@time_trigger("cron(*/5 * * * *)")` ping in `pyscript/watchdog.py` that reads the URL from secrets and fails quietly on network errors; mock any new HA domains in the tests.
