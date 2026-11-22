# /config/pyscript/city_trains.py
#
# On-demand Regional Rail lookups, both ways:
#
# - To the city: the kitchen "Trains to the city" button calls
#   pyscript.city_trains_lookup, which asks the transit service (:8000) for the
#   next trains from the home station to DESTINATION and writes
#   sensor.city_trains (card: dashboards/components/shared/city_trains.yaml).
# - Back home: while either of us is in Center City, binary_sensor.in_center_city
#   is on and the Home dashboard shows a "Trains home" button. It calls
#   pyscript.trains_home_lookup, which asks for the next trains from the
#   Center City station nearest that person, with the walk to it worked out
#   from their GPS, and writes sensor.trains_home
#   (card: dashboards/components/home/trains_home.yaml).
#
# Both cards share their markup (custom_templates/trains.jinja) and also list
# SEPTA's alerts for the home lines.
#
# Nothing asks SEPTA on a timer: only a button press does, and the service
# reuses any answer younger than a minute. The Center City check uses only the
# GPS sensors already in HA. The home station and its walk time stay in the
# service's own settings (its .env), so they aren't repeated here.
#
# Result sensor states: "idle" (card hidden), "loading", "ready" or "error".
# Each goes back to "idle" SHOW_MINUTES after a lookup. The sensors are made by
# state.set, so after an HA restart they don't exist until the next press and
# the cards stay hidden.

import math

DESTINATION = "Suburban Station"  # to the city; spelled as SEPTA's NextToArrive spells it
SHOW_MINUTES = 20                 # how long the results stay on the screen
ALERT_MAX_CHARS = 160             # longer alert text is cut to this length

# Where the trip home can start. Station positions are public (SEPTA's station
# list); someone within CITY_RADIUS_M of one of them counts as in Center City.
CITY_STATIONS = {
    "Suburban Station": (39.9539, -75.1678),
    "Jefferson Station": (39.9525, -75.1581),
    "30th Street Station": (39.9557, -75.1820),
}
CITY_RADIUS_M = 1500
WALK_M_PER_MIN = 80        # an easy city walking pace
STREET_FACTOR = 1.3        # streets are longer than the straight line
MAX_FIX_AGE_MIN = 30       # an older GPS position doesn't count

# Each person: (GPS sensor, home sensor). Someone at home is never "in the city",
# whatever an old position says.
PEOPLE = {
    "me": ("sensor.me_location", "binary_sensor.me_home"),
    "partner": ("sensor.partner_location", "binary_sensor.partner_home"),
}
IN_CITY_ENTITY = "binary_sensor.in_center_city"

SERVICE_URL = "http://127.0.0.1:8000"
TO_CITY = "sensor.city_trains"
TO_HOME = "sensor.trains_home"
NAMES = {
    TO_CITY: {"friendly_name": "Trains to the city", "icon": "mdi:train"},
    TO_HOME: {"friendly_name": "Trains home", "icon": "mdi:home-import-outline"},
}


@pyscript_compile
def _get_json(url, timeout=20):
    """Blocking GET. Returns the parsed JSON, or None on any failure."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


@pyscript_compile
def _clean_text(text, max_chars):
    """SEPTA alert text is HTML; make it one plain line, cut to max_chars."""
    import html
    import re
    clean = re.sub(r"<[^>]+>", " ", html.unescape(str(text or "")))
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > max_chars:
        clean = clean[:max_chars - 1].rstrip() + "…"
    return clean


@pyscript_compile
def _leave_by(departure, walk_minutes, now):
    """When to leave home for a train leaving at `departure` ("11:03AM"), as
    an ISO time the card counts down to. None if the time can't be read."""
    from datetime import datetime, timedelta
    try:
        clock = datetime.strptime(departure, "%I:%M%p")
    except (TypeError, ValueError):
        return None
    leave = now.replace(hour=clock.hour, minute=clock.minute, second=0, microsecond=0)
    if leave < now - timedelta(hours=12):
        leave += timedelta(days=1)  # a train just after midnight
    return (leave - timedelta(minutes=walk_minutes)).isoformat()


@pyscript_compile
def _trains(trip, now):
    """The next few trains, in the shape the card reads."""
    walk = trip.get("walk_time_minutes") or 0
    trains = []
    for option in trip.get("itineraries") or []:
        depart = option.get("origin_actual_departure")
        trains.append({
            "train": option.get("origin_train"),
            "line": option.get("origin_line"),
            "depart": depart,
            "leave_by": _leave_by(depart, walk, now),
            "arrive": option.get("actual_arrival_time"),
            "delay": option.get("total_delay_minutes") or 0,
            # ok, delayed, at_risk (tight change), cancelled or unclear
            "status": option.get("status"),
            # Only set when the trip needs a change of train.
            "change_train": option.get("connection_train"),
            "change_depart": option.get("connection_actual_departure"),
        })
    return trains


@pyscript_compile
def _alerts(alerts, max_chars):
    """Plain-text alerts for the home lines: urgent ones, then advisories
    (track work, bus substitutions)."""
    alerts = alerts or {}
    urgent = [f"{a.get('line')}: {_clean_text(a.get('alert_text'), max_chars)}"
              for a in alerts.get("critical_alerts") or []]
    advisories = [f"{a.get('line')}: {_clean_text(a.get('advisory_text'), max_chars)}"
                  for a in alerts.get("recent_advisories") or []]
    return urgent, advisories


def _current(entity):
    """(state, attributes) of an entity this file makes, or (None, {}) before
    it has been set (state.get raises for an entity that doesn't exist yet)."""
    if not state.exist(entity):
        return None, {}
    return state.get(entity), state.getattr(entity) or {}


def _hide_later(entity):
    """Hide the card again SHOW_MINUTES after the last lookup."""
    task.unique(f"trains_hide_{entity}")
    task.sleep(SHOW_MINUTES * 60)
    state.set(entity, "idle", NAMES[entity])


def _lookup(entity, url, destination, extra=None):
    """Ask the transit service for a trip and write it to `entity`, with any
    `extra` attributes the card needs."""
    from datetime import datetime
    state.set(entity, "loading", {**_current(entity)[1], **NAMES[entity]})

    trip = task.executor(_get_json, url)
    alerts = task.executor(_get_json, f"{SERVICE_URL}/api/alerts")
    now = datetime.now().astimezone()  # with the UTC offset, for the card's countdown
    urgent, advisories = _alerts(alerts, ALERT_MAX_CHARS)

    attrs = {
        **NAMES[entity],
        "looked_up_at": now.isoformat(),
        "destination": destination,
        **(extra or {}),
        "alerts": urgent,
        "advisories": advisories,
        "alerts_unavailable": alerts is None or bool(alerts.get("alerts_unavailable")),
    }
    if not trip or "error" in trip:
        attrs.update(trains=[], error=(trip or {}).get("error") or "Transit service didn't answer")
        state.set(entity, "error", attrs)
        log.warning(f"city_trains: {entity} lookup failed: {attrs['error']}")
    else:
        attrs.update(
            trains=_trains(trip, now),
            track=trip.get("origin_track"),  # for the first train only
            change_at=trip.get("connection_station"),
            walk_minutes=trip.get("walk_time_minutes"),
            data_stale=bool(trip.get("data_stale")),
            error=None,
        )
        state.set(entity, "ready", attrs)
    task.create(_hide_later, entity)


@service
def city_trains_lookup():
    """Look up the next trains from home to Center City (kitchen button)."""
    task.unique("city_trains_lookup")  # a second press replaces one still waiting
    _lookup(TO_CITY, f"{SERVICE_URL}/api/commute?destination={_quote(DESTINATION)}", DESTINATION)


@service
def trains_home_lookup():
    """Look up the next trains home from the Center City station nearest
    whoever is in the city (Home dashboard button). With nobody located
    there, it starts from DESTINATION with the service's usual walk time."""
    task.unique("trains_home_lookup")
    _update_in_city()
    where = _current(IN_CITY_ENTITY)[1]
    station = where.get("station") or DESTINATION
    url = f"{SERVICE_URL}/api/trip_home?origin={_quote(station)}"
    if where.get("walk_minutes") is not None:
        url += f"&walk={where['walk_minutes']}"
    _lookup(TO_HOME, url, "home", {"from_station": station})


# ---------------------------------------------------------------------------
# Is either of us in Center City?
# ---------------------------------------------------------------------------

@pyscript_compile
def _quote(text):
    import urllib.parse
    return urllib.parse.quote(text)


@pyscript_compile
def _distance_m(a, b):
    """Straight-line distance in metres between two (lat, lon) points."""
    import math
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2)
    return 6_371_000 * 2 * math.asin(math.sqrt(h))


@pyscript_compile
def _fix_age_min(last_seen, now):
    """Minutes since the phone reported this position, or None if unknown."""
    from datetime import datetime
    try:
        seen = datetime.fromisoformat(str(last_seen))
    except (TypeError, ValueError):
        return None
    if seen.tzinfo is None:
        seen = seen.astimezone()
    return (now - seen).total_seconds() / 60


@pyscript_compile
def _nearest_city_station(position, stations, radius_m):
    """(station, metres) for the nearest station within radius_m, else None."""
    best = min(stations, key=lambda name: _distance_m(position, stations[name]))
    metres = _distance_m(position, stations[best])
    return (best, metres) if metres <= radius_m else None


def _city_position(gps_entity, home_entity, now):
    """This person's (lat, lon) if it is fresh and they aren't home, else None."""
    if _current(home_entity)[0] == "on":
        return None
    attrs = _current(gps_entity)[1]
    try:
        position = (float(attrs.get("latitude")), float(attrs.get("longitude")))
    except (TypeError, ValueError):
        return None
    age = _fix_age_min(attrs.get("last_seen"), now)
    if age is not None and age > MAX_FIX_AGE_MIN:
        return None
    return position


def _update_in_city():
    """Set binary_sensor.in_center_city from both GPS positions. When both of
    us are in town, the station nearest either one is used."""
    from datetime import datetime
    now = datetime.now().astimezone()
    best = None
    for gps_entity, home_entity in PEOPLE.values():
        position = _city_position(gps_entity, home_entity, now)
        if position is None:
            continue
        found = _nearest_city_station(position, CITY_STATIONS, CITY_RADIUS_M)
        if found and (best is None or found[1] < best[1]):
            best = found
    attrs = {"friendly_name": "In Center City", "icon": "mdi:city-variant-outline"}
    if best:
        walk = math.ceil(best[1] * STREET_FACTOR / WALK_M_PER_MIN)
        attrs.update(station=best[0], walk_minutes=walk)
    new_state = "on" if best else "off"
    if _current(IN_CITY_ENTITY) != (new_state, attrs):
        state.set(IN_CITY_ENTITY, new_state, attrs)


@state_trigger(
    "sensor.me_location.latitude", "sensor.me_location.longitude",
    "sensor.partner_location.latitude", "sensor.partner_location.longitude",
    "binary_sensor.me_home", "binary_sensor.partner_home",
)
def in_center_city_changed():
    _update_in_city()


@time_trigger("startup", "cron(*/5 * * * *)")
def in_center_city_tick():
    """At startup, and every 5 minutes so a position that has gone stale stops counting."""
    _update_in_city()
