# Team Lights

`pyscript/apps/team_lights.py` paints your lights in your team's color while its game is live and celebrates when the team scores. It works with any team that the [Team Tracker](https://github.com/vasqued2/ha-teamtracker) integration follows (NFL, NBA, NHL, MLB, MLS, college and more), and you can follow as many teams as you like.

The code has nothing specific to this house in it. Your teams, lights and house rules go in YAML.

## What it does

- **Team color.** Each team uses its `color` from the config. If a team has no `color`, the app uses the brightest color in ESPN's colors for that team, skipping black, white and gray. Before a game, Team Tracker reports gray placeholder colors, so the app keeps the last real color it saw.

  Set `color` when ESPN's color isn't the one you want. The color might be too dark for a bulb, or your team might be known for a different color. The Eagles here use Kelly green `[0, 170, 35]` instead of ESPN's midnight green, which shows as teal on a bulb. If a particular bulb shows the color wrong, give it its own setting with `light_colors`, for example a hue/saturation value for a bulb whose green LED runs blue.
- **Featured team.** When two games are on at once, one team controls the lights. Playoff games go first, then the order of `teams`. If you set `featured_select`, picking a team there overrides that choice while the team's game is live. The featured team is published to `pyscript.team_lights_featured` (state = team name; attributes `sensor`, `rgb`, `light_colors`, `sport`, `live`) for dashboards and other scripts.
- **Kickoff.** The featured team's color goes on lights that are already on, if the `only_when` conditions are met. The app never turns lights on or changes modes.
- **Scores.** Only the featured team celebrates. Lights that are off stay off. Celebrations change brightness only, between 100% and `dim_floor_pct`, and never the color, so a Zigbee mesh can keep up. Each one ends at 100% in the team color.

| Sport | Celebrates on | Celebration |
|---|---|---|
| Football | touchdown (6+ points) | big |
| Football | field goal, extra point, safety | small |
| Basketball | three-pointers only | small |
| Hockey, soccer | every goal | big |
| Baseball | home run | big |
| Baseball | other runs | small |
| Anything else | any score | small |

The big celebration is six pulses, a short pause, then two more. The small one is three pulses. To change the rules, edit `_celebration()`.

Team Tracker checks for updates every 5 seconds during a game, so one update can include more than one score. In basketball, a 3-point increase counts as a three. A bigger increase counts only if ESPN's last play mentions a made three-pointer.

## Install

1. Install [pyscript](https://github.com/custom-components/pyscript) and Team Tracker, and add a Team Tracker sensor for each team.
2. Copy `team_lights.py` to `<config>/pyscript/apps/`.
3. Add the config below to `configuration.yaml` or a package, then run `pyscript.reload`.

Minimal config:

```yaml
pyscript:
  apps:
    team_lights:
      lights:
        - light.living_room
      teams:
        - name: Packers
          sensor: sensor.green_bay_packers
```

## Options

| Key | Required | Meaning |
|---|---|---|
| `lights` | yes | Lights to paint and pulse while they're on. |
| `lights_if_on` | no | Lights that are recolored only while they're already on. |
| `teams` | yes | Your teams, highest priority first (see below). |
| `enabled_entity` | no | Master switch: the app does nothing unless this entity is `on`. |
| `featured_select` | no | An `input_select` with `Auto` plus your team names, for choosing the featured team manually. |
| `only_when` | no | `entity_id: state` (or a list of states). Every entry must match before any team recolors or celebrates, e.g. `media_player.tv: playing`. |
| `dim_floor_pct` | no | Lowest brightness during a celebration (default 15; very low levels can flicker). |

Per team:

| Key | Required | Meaning |
|---|---|---|
| `sensor` | yes | The Team Tracker sensor. |
| `name` | no | Display name; must match the `featured_select` option. Defaults to the sensor ID. |
| `color` | no | `[r, g, b]` or `"#rrggbb"`. Without it, ESPN's team color is used. |
| `light_colors` | no | Settings for particular lights in place of the RGB, e.g. `light.hallway: {hs_color: [125, 100]}` for a bulb whose LEDs need a different hue to match. |
| `only_when` | no | Replaces the top-level `only_when` for this team (`{}` = always). |
| `celebrate` | no | `false` turns score celebrations off for this team. |

Dashboard button: `pyscript.team_lights_celebrate` (`kind: big` or `small`) plays a celebration in the featured team's color.

## This house

The config lives in `packages/sports.yaml`. All four teams share `only_when: {sensor.theater_mode: sports}`, so they recolor and celebrate only while the basement TV is on sports. Switching the TV to sports is what puts the basement in Social Mode and paints the featured team's color (`basement.py`). `input_select.featured_team` appears on the home dashboard when two teams have games the same day (`binary_sensor.team_games_overlap`). `basement.py`, the theater poster and the now-playing banner all follow `pyscript.team_lights_featured`.
