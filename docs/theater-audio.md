# Theater Audio, Receiver DSP & Pyscript Engine

_Moved verbatim from AGENTS.md. "§N" references point to the old AGENTS.md sections (§4 lighting/sports now live in docs/lighting.md)._

### Audio Conduction & Yamaha RX-V673 DSP Routing (`theater.py`)
The RX-V673 exposes no `PLII ...` programs through HA. `media_player.theater_receiver` `sound_mode_list`: Hall in Munich, Hall in Vienna, Chamber, Cellar Club, The Roxy Theatre, The Bottom Line, Sports, Action Game, Roleplaying Game, Music Video, Standard, Spectacle, Sci-Fi, Adventure, Drama, Mono Movie, Surround Decoder, 2ch Stereo, 7ch Stereo, Straight. `set_receiver_sound_mode()` only selects names from this list and uses `SOUND_MODE_FALLBACKS` when needed (`Surround Decoder` falls back to `Action Game` then `Standard`).

| Application / Source | Receiver Input | DSP Mode | Audio Steer / Channel Behavior |
|---|---|---|---|
| `com.stremio.one` | HDMI1 | `Standard` | Bitstream passthrough (DD/DD+/TrueHD 5.1 when the file has it); Cinema DSP ambience on top |
| `com.netflix.ninja` / Prime | HDMI1 | `Standard` | Multichannel discrete surround |
| `com.google.android.youtube.tv` | HDMI1 | `Surround Decoder` | Stereo source matrixed to multichannel (Dolby Pro Logic II) |
| `com.spotify.tv.android` | HDMI1 | `7ch Stereo` | Same stereo from every speaker; room-filling for social use. Switch to `Surround Decoder` in the UI for dedicated listening |
| Music mode (`play_music()`) | HDMI1 | `7ch Stereo` | Projector off: stays off, phone streams to the AVR, Onn untouched. Projector on: opens Spotify on the Onn |
| Batocera (Retro 2CH Systems) | HDMI2 | `Straight` | Uncompressed stereo, no processing |
| Batocera (Modern 3D Systems) | HDMI2 | `Surround Decoder` | Stereo mix matrixed to multichannel (Dolby Pro Logic II) |
| Moonlight via Batocera (`play_pc_game()`, default) | HDMI2 | `Surround Decoder` | Batocera runs the Moonlight client; stereo is matrixed, true 5.1 plays natively. `configure_batocera_audio()` applies the same mode when Batocera reports `playing` |
| Moonlight on Onn (`play_pc_game(target="onn")`) | HDMI1 | `Surround Decoder` | Unused alternative: launches `com.limelight` on the Onn |
| HDHomeRun (`com.silicondust.view`) / Sports (`SPORTS_APPS`) | HDMI1 | `Sports` | Multi-surround crowd audio; Center speaker trimmed via dashboard slider (-10.0 dB hardware cap) |
| Native Net/AirPlay/Spotify Connect (no Onn app) | NET/AirPlay | not auto-routed | `route_app_audio_mode()` only acts when the source is HDMI1; `play_music()` sets `7ch Stereo` |

**Receiver prerequisites**
- The Pro Logic II flavor (Movie, Music or Game) used by `Surround Decoder` is set on the receiver, not through HA: Option menu → Sound Program → Surround Decoder (menu wording may vary by model). It is one global setting; the network API (`desc.xml`) offers no control for it. Chosen flavor: **undecided** — A/B DPL Music, Movie and Game on YouTube and 3D games, then record the choice here. (Music is the gentlest; Movie fits YouTube; Game fits 3D games.)
- Onn 4K Pro: Settings → Display & Sound → Advanced sound settings → Format should be Auto or passthrough, so 5.1 sources arrive as 5.1. The receiver's display should show Dolby Digital (or similar) for 5.1 content.
- Receiver scenes (`Main_Zone,Scene,Scene_Sel`) are exposed on the network and may allow per-mode decoder flavors later. Untested.

### Theater Pyscript Engine Notes (`theater.py`)
- **Art lookups need `await`**: `_fetch_movie_or_tv_art()` and `_fetch_game_art_from_secrets()` must be called as `await ...`. Without it pyscript handed back an unawaited coroutine, so lookups never resolved and only fallback art ever showed (and `update_game_poster()` crashed with `'coroutine' object has no attribute 'get'`).
- **Debounced triggers**: `update_theater_media_art()` and `update_game_poster()` are plain functions (called directly by the `play_*` services). The `@state_trigger` wrappers `on_theater_media_changed()` and `on_theater_game_changed()` debounce with `task.unique` plus a 0.5s sleep.
- **Mode resolver**: on HDMI1, `update_theater_mode()` maps the foreground app to a mode via `MUSIC_APPS`, `SPORTS_APPS`, `GAME_APPS` and `MOVIE_APPS`. Launcher or unknown apps keep the current mode.
- **Select feedback guard**: `sync_theater_select()` records its own changes in `_SELECT_SYNC_PENDING` (5s window) so `on_theater_select_changed()` ignores them and doesn't re-fire a `play_*` service.
- **Foreground app**: `get_active_app_id()` reads `media_player.onn_pro` `app_id` (then `app_name`, then `remote.onn_pro` `current_activity`); titles come from the Onn media players. This requires `media_player.onn_pro` to expose a live `app_id` attribute.
- **Art cache**: movie/TV lookup misses are not negatively cached while a service circuit breaker is open. Steam shortcut titles are cleaned before lookup (`1794680_Vampire_Survivors` becomes `Vampire Survivors`).
- **Music mode**: projector off (lamp current <= 0.06A) → cut its mains, receiver to HDMI1 / 7ch Stereo, and leave the Onn alone; music comes from the phone to the AVR. Projector on → leave it on and open Spotify on the Onn (skipped if already foreground). Never sleep the Onn here: the receiver follows its CEC standby and that ends the session (2026-10-23). The cooldown loop likewise never sleeps the Onn in music mode.
- **Spotify pause**: `pause_spotify_if_playing()` only fires when `media_player.whole_house_spotify` reports pause support.

