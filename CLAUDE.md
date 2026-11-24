# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read first

@AGENTS.md

`AGENTS.md` (imported above) holds the safety interlocks and core rules; its "Where to look" list says which `docs/*.md` file to read before each kind of change. Keep both updated when behavior changes. Each rule should live in one place: `AGENTS.md` for the rules, `docs/` for the detail. `.clinerules` only points other tools at `AGENTS.md`; don't copy rules into it.

## This directory is the live Home Assistant config

This repo is the Docker named volume mounted at `/config` in the `homeassistant` container (`~/docker/docker-compose.yml`, `network_mode: host`). `~/ha_config` is a symlink to it. Edits here hit production immediately — there is no staging copy.

- Don't read or search the paths listed in `.clineignore`: secrets and certs, databases, `.storage/`, logs, caches, `backups/`, `ssh/`, `tts/`, `www/community/`. They hold sensitive or bulky runtime state and waste context. `custom_components/` is also git-ignored (installed by HACS). The only exception is read-only queries against `home-assistant_v2.db` / `zigbee.db` when a task needs telemetry; never write to them while HA is running.
- Validate config: `docker exec homeassistant python -m homeassistant --script check_config -c /config`
- Logs: `home-assistant.log` in the repo root, or `docker logs homeassistant`.
- `scripts/sync_to_ha.sh` is for pushing from a separate dev checkout (rsync over Tailscale or `--local-docker`); it is not needed when editing in place.

## Commands

```bash
python3 tests/run_all_tests.py            # full suite (same as ./run_tests.sh)
python3 tests/test_theater_basement.py    # run one suite directly
python3 tests/test_dashboard_integrity.py # dashboard entity/service binding audit
python3 scripts/build_dashboard.py        # read-only check of basement.yaml includes (never writes)
```

Each suite is a standalone script (no pytest); it exits non-zero on failure. `run_all_tests.py` runs the suites listed in its `TEST_SUITES` array in subprocesses with `pyscript/` on `PYTHONPATH` — add new suites there. Telemetry tools that read the recorder DB (read-only) live in `scripts/telemetry/`, not `tests/`. `extract_48h.py` rewrites `tests/telemetry_48h.json`, which the replay suites read; `check_live_artwork.py` calls TMDB with the key from `secrets.yaml`, so it is not part of the suite.

## Architecture

**Layers**
- `packages/*.yaml` (loaded via `!include_dir_named packages`): helpers, template sensors, `rest_command`s and integrations per subsystem — `theater.yaml` (AVR, input_selects, Yamaha YNC XML commands, HDHomeRun), `basement_lighting.yaml`, `commute.yaml` (transit FastAPI on :8000), `kitchen_display.yaml` (kitchen tablet data: display mode, trimmed NWS forecasts, today's events, work-from-home flag, NWS alerts; card markup in `custom_templates/kitchen.jinja`, cards in `dashboards/components/shared/` (also used by `home.yaml`)).
- `pyscript/*.py` (pyscript integration, `allow_all_imports`, `hass_is_global`): all automation logic. `theater.py` (mode resolver, `play_*` services, receiver DSP routing, which poster to show, session end), `interlocks.py` (projector cooldown, stray-wake guard, Batocera halt/relay; kept apart so a theater.py reload can't kill a running cooldown, and theater.py reaches it only through `pyscript.*` services), `basement.py` (lighting state machine, palettes, stairs direction-of-travel), `apps/team_lights.py` (shareable Team Tracker app: team colors, featured team, per-sport score celebrations for all four Philly teams; config under `pyscript: apps: team_lights:` in `packages/sports.yaml`, docs in docs/team-lights.md), `kitchen_tablet.py` (kitchen tablet charging on `switch.kitchen_tablet_mains`, 70–80% and only inside the screen's wake windows, because Android wakes the screen whenever the charger switches; at any hour only at 25% or below; with the plug's own 4 h off-timer armed on every turn-on as a backstop; holds the screen on via Companion app commands in the morning windows and 4–8 PM, and lets it go dark in between), `modules/theater_art.py` (the online poster and box-art lookups theater.py calls: TMDB, Cinemeta, TVMaze, SteamGridDB, RAWG, libretro, with their cache and outage backoff; saving it reloads theater.py and basement.py), `modules/pc_window.py` (whether the gaming PC is in a game, read from `sensor.gaming_pc_active_game`, for the game poster and the basement lights; its "not a game" lists match the Gaming PC Active Game template in configuration.yaml, and `tests/test_pc_window.py` fails if they differ), `modules/shared_entities.py` (entity IDs and mode names used by both theater.py and basement.py; saving it reloads both, so edit it with the theater idle. interlocks.py keeps its own copies so it never reloads with them, and `tests/test_shared_entities.py` fails if those drift or if theater.py/basement.py redefine a shared name), `commute_location.py` (posts `sensor.partner_location` to the transit service's `/api/location` during commute hours on the commuter's office days, so the commute cards follow the train the commuter is actually on; the sensor is a neutral copy of the location tracker made in the gitignored `packages/private_location.yaml`), `city_trains.py` (on-demand trains both ways, asked only when a button is pressed: the kitchen "Trains to the city" button (`pyscript.city_trains_lookup`, the transit service's `/api/commute`, `sensor.city_trains`) and the Home dashboard's "Trains home" button, shown while `binary_sensor.in_center_city` says one of us is in Center City (`pyscript.trains_home_lookup`, `/api/trip_home` from the nearest station with the walk from GPS, `sensor.trains_home`); both cards share `custom_templates/trains.jinja`), `weather_alert.py` (`pyscript.weather_alert_dismiss`: tapping the weather alert banner hides it until the alert changes; the banner follows `binary_sensor.weather_alert_showing` in `packages/kitchen_display.yaml`), `watchdog.py`, `health_check.py`. `automations.yaml`/`scripts.yaml`/`scenes.yaml` are essentially empty — new automations go in pyscript.
- `dashboards/*.yaml`: Lovelace YAML-mode dashboards. Every file here is registered under `lovelace.dashboards` in `configuration.yaml`, and the repo is the source of truth: don't create or edit dashboards in the HA UI. Changes to the registration list need an HA restart; edits to the files show up on browser refresh. `basement.yaml` is assembled from `dashboards/components/*.yaml` via `!include`, with shared card shapes in `components/decluttering_templates.yaml` (keep repeated cards DRY through these templates). `home.yaml` pulls its vacuum pop-up from `components/home/vacuum_popup.yaml`. Home, Bedroom and Diagnostics (with its Activity Log tab) use the `House Glass` theme (per view, `theme: House Glass`), built by `scripts/build_house_theme.py` from the HACS-installed Frosted Glass Dark Lite into the gitignored `themes/house_glass.yaml`; rerun it after a Frosted Glass update, then reload themes. Its `glass-tile` (`tall` / `row`) and `glass-chip` classes hold the shared card look: a card sets `card_mod: class:` and only `--tile-rgb` / `--tile-on` in its own style.

**How the theater flows**: dashboard buttons / `input_select.basement_theater_mode` → `pyscript.play_*` services in `theater.py` → AVR input + DSP mode + app launch on the Onn → `sensor.theater_mode` resolver (driven by foreground `app_id` on HDMI1 and Batocera state on HDMI2) → `basement.py` `theater_lighting_sync()` reacts to `binary_sensor.theater_in_use` / `sensor.theater_mode`; Team Lights reacts to the Team Tracker sensors and publishes `pyscript.team_lights_featured`, which basement.py and the theater poster read for team color. Art sensors (`sensor.theater_current_poster`, `sensor.theater_current_boxart`) are written by `theater.py` with `state.set`.

**Pyscript gotchas**
- `@state_trigger` wrappers debounce with `task.unique` + short sleep and call plain functions that the `play_*` services also call directly.
- Pyscript globals (`state`, `task`, `log`, service domains like `light`, `switch`, `media_player`) are not importable in plain Python. Tests inject mocks into `builtins` (see the top of `tests/test_theater_basement.py`) before importing the module — any new HA domain you call from pyscript must also be mocked there.
- Reload after editing: `pyscript.reload` service (or restart the container). A reload, or a save (auto-reload), reloads the changed file and kills that file's running tasks. Saving a file in `pyscript/modules/` also reloads every file that imports it (`shared_entities.py`, `pc_window.py` and `theater_art.py`, which pc_window.py imports, all reload theater.py and basement.py). `task.unique` names are per file too, so one file can't cancel another's task; call a service instead.

**Trigger check**: `tests/test_pyscript_triggers.py` loads every pyscript file and fails if a `@state_trigger` is invalid or watches an entity not listed in `docs/entities.md`. When a new trigger watches a new entity, confirm the ID in HA (`ha-api state <id>`) and add it to `docs/entities.md`.

**Dashboard validation**: `tests/test_dashboard_integrity.py` holds `REGISTERED_ENTITIES` and `REGISTERED_SERVICES` and resolves `!include`s to check every binding. New entities or services referenced from a dashboard must be added to those sets, or the audit fails. `build_dashboard.py` reuses the same registry.

## Hard constraints

The five hardware safety interlocks and the rules that cause bugs when missed are in `AGENTS.md`, imported at the top of this file.
