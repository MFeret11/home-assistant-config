# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read first

@AGENTS.md

`AGENTS.md` (imported above) holds the safety interlocks and core rules; its "Where to look" list says which `docs/*.md` file to read before each kind of change. Keep both updated when behavior changes. `.clinerules` is a condensed version of the same rules.

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
python3 scripts/build_dashboard.py        # build + validate dashboard components
```

Each suite is a standalone script (no pytest); it exits non-zero on failure. `run_all_tests.py` runs the suites listed in its `TEST_SUITES` array in subprocesses with `pyscript/` on `PYTHONPATH` — add new suites there. The `audit_*`, `extract_*` and `profile_*` scripts in `tests/` are telemetry tools that read the recorder DB, not tests.

## Architecture

**Layers**
- `packages/*.yaml` (loaded via `!include_dir_named packages`): helpers, template sensors, `rest_command`s and integrations per subsystem — `theater.yaml` (AVR, input_selects, Yamaha YNC XML commands, HDHomeRun), `basement_lighting.yaml`, `commute.yaml` (transit FastAPI on :8000).
- `pyscript/*.py` (pyscript integration, `allow_all_imports`, `hass_is_global`): all automation logic. `theater.py` (mode resolver, `play_*` services, receiver DSP routing, poster/box-art scraping, safety interlocks), `basement.py` (lighting state machine, palettes, stairs direction-of-travel), `sports.py` (Eagles kickoff/score flash/game over, `get_team_rgb`), `watchdog.py`, `health_check.py`. `automations.yaml`/`scripts.yaml`/`scenes.yaml` are essentially empty — new automations go in pyscript.
- `dashboards/*.yaml`: Lovelace YAML-mode dashboards. Every file here is registered under `lovelace.dashboards` in `configuration.yaml`, and the repo is the source of truth: don't create or edit dashboards in the HA UI. Changes to the registration list need an HA restart; edits to the files show up on browser refresh. `basement.yaml` is assembled from `dashboards/components/*.yaml` via `!include`, with shared card shapes in `components/decluttering_templates.yaml` (keep repeated cards DRY through these templates).

**How the theater flows**: dashboard buttons / `input_select.basement_theater_mode` → `pyscript.play_*` services in `theater.py` → AVR input + DSP mode + app launch on the Onn → `sensor.theater_mode` resolver (driven by foreground `app_id` on HDMI1 and Batocera state on HDMI2) → `basement.py` `theater_lighting_sync()` reacts to `binary_sensor.theater_in_use` / `sensor.theater_mode`; `sports.py` reacts to `sensor.philadelphia_eagles`. Art sensors (`sensor.theater_current_poster`, `sensor.theater_current_boxart`) are written by `theater.py` with `state.set`.

**Pyscript gotchas**
- Async helpers (art lookups) must be `await`ed; `@state_trigger` wrappers debounce with `task.unique` + short sleep and call plain functions that the `play_*` services also call directly.
- Pyscript globals (`state`, `task`, `log`, service domains like `light`, `switch`, `media_player`) are not importable in plain Python. Tests inject mocks into `builtins` (see the top of `tests/test_theater_basement.py`) before importing the module — any new HA domain you call from pyscript must also be mocked there.
- Reload after editing: `pyscript.reload` service (or restart the container).

**Dashboard validation**: `tests/test_dashboard_integrity.py` holds `REGISTERED_ENTITIES` and `REGISTERED_SERVICES` and resolves `!include`s to check every binding. New entities or services referenced from a dashboard must be added to those sets, or the audit fails. `build_dashboard.py` reuses the same registry.

## Hard constraints

The five hardware safety interlocks and the rules that cause bugs when missed are in `AGENTS.md`, imported at the top of this file.
