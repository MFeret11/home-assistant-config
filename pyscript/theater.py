# ==============================================================================
# THEATER: modes, receiver and sound, posters, sessions, live TV tuners
# ==============================================================================
# Sections, in order (search for the capitalised heading):
#   ENTITY IDS, APP LISTS AND FALLBACK ART
#   SMALL HELPERS        safe state reads and service calls, Onn apps, projector state
#   POSTER AND BOX ART SENSORS, WHAT'S PLAYING
#   SPORTS SCOREBOARD AND THE MOVIE/MUSIC POSTER
#   GAMING PC WINDOW AND THE GAME POSTER
#   DASHBOARD MODE PICKER, AND POSTERS AT STARTUP
#   WORKING OUT THE THEATER MODE; RECEIVER AND ONN POWER BUTTONS
#   SOUND MODES, VOLUME AND THE ANNOUNCER LEVEL
#   HARDWARE INTERLOCK CALLS (the interlocks themselves live in interlocks.py)
#   STARTING SESSIONS: movie, game, PC game, music
#   HDHOMERUN TUNER CONTROL
#   SPORTS, CURTAIN CALL AND MANUAL SERVICES
#   MOVIE SEARCH (Stremio deep link)
#
# The online art lookups (movie and TV posters, game box art, their cache and the
# outage backoff) are in pyscript/modules/theater_art.py. This file decides which
# poster to show; that one fetches the pictures.
#
# Background and rules: AGENTS.md and docs/theater-audio.md.
# ==============================================================================
import re
import time
import urllib.parse

BOOT_TIMESTAMP = time.time()

from theater_art import (  # pyscript/modules/theater_art.py: online poster and box art lookups
    RE_ROM_EXT,
    RE_ROM_TAGS,
    _ART_CACHE,
    _CIRCUIT_STATE,
    _fetch_game_art_from_secrets,
    _fetch_json,
    _fetch_movie_or_tv_art,
    _is_circuit_open,
    get_search_candidates,
)

try:
    pyscript_compile
except NameError:
    def pyscript_compile(func):
        return func

# ------------------------------------------------------------------------------
# ENTITY IDS, APP LISTS AND FALLBACK ART
# ------------------------------------------------------------------------------
from shared_entities import (  # pyscript/modules/shared_entities.py
    ADAPTIVE_SWITCH,
    RECEIVER,
    RECEIVER_ZONE_2,
    ONN_PRO,
    ONN_ADB,
    ONN_REMOTE,
    PROJECTOR_SWITCH,
    PROJECTOR_CURRENT,
    BATOCERA_SWITCH,
    BATOCERA_CURRENT,
    BATOCERA_STATE,
    PC_ACTIVE_WINDOW,
    THEATER_MODE,
    THEATER_IN_USE,
    THEATER_BOXART,
    SOCIAL_SOURCE,
    MODE_SOCIAL,
    MODE_DAILY,
    LIGHTING_MODE_SELECT,
    CURTAIN_CALL,
    SPOTIFY_PLAYER,
    FEATURED_TEAM,
    MMWAVE_PRESENCE,
)

ONN_PRO_2 = "media_player.onn_pro_2"

BATOCERA_SYSTEM = "sensor.batocera_system"
BATOCERA_GAME = "sensor.batocera_current_game"

# ASUS ROG Gaming PC (HASS.Agent & Moonlight)
PC_SWITCH = "switch.gaming_pc"
PC_ONLINE = "binary_sensor.gaming_pc_online"
PC_GPU_TEMP = "sensor.desktop_rspn8nu_gputemperature"

THEATER_SELECT = "input_select.basement_theater_mode"
THEATER_POSTER = "sensor.theater_current_poster"

ANNOUNCER_VOLUME = "input_number.theater_announcer_volume"
ANNOUNCER_PRESET = "input_select.theater_announcer_preset"

# Onn apps, by Android package name
STREMIO_APP = "com.stremio.one"
NETFLIX_APP = "com.netflix.ninja"
YOUTUBE_TV_APP = "com.google.android.youtube.tv"
YOUTUBE_APPS = {YOUTUBE_TV_APP, "com.google.android.youtube"}
SPOTIFY_TV_APP = "com.spotify.tv.android"
HDHOMERUN_APP = "com.silicondust.view"
MOONLIGHT_APP = "com.limelight"
PRIME_VIDEO_PACKAGE = "com.amazon.amazonvideo.livingroom"

PRIME_VIDEO_APPS = {
    "com.amazon.amazonvideo.livingroom",
    "com.amazon.avod.thirdpartyclient",
    "com.amazon.aiv.eu",
    "com.amazon.primevideo.tv",
    "com.amazon.video",
}

# Which theater mode an app on the Onn means (see update_theater_mode)
MOVIE_APPS = {
    STREMIO_APP,
    *YOUTUBE_APPS,
    NETFLIX_APP,
    *PRIME_VIDEO_APPS,
}

MUSIC_APPS = {
    SPOTIFY_TV_APP,
    "com.spotify.music",
}

SPORTS_APPS = {
    HDHOMERUN_APP,              # HDHomeRun
    "com.armata.televizio",     # Televizio
    "ar.tvplayer.tv",           # TiviMate
    "com.espn.score_center",    # ESPN
    "com.foxsports.videogo",    # Fox Sports
    "com.cbs.app",              # Paramount+ / CBS Sports
}

# Apps that get the booth announcer bar (center-channel trim). Prime carries TNF.
ANNOUNCER_BAR_APPS = SPORTS_APPS | PRIME_VIDEO_APPS
ANNOUNCER_BAR = "binary_sensor.theater_announcer_bar"

GAME_APPS = {
    MOONLIGHT_APP,              # Moonlight Game Streaming
    "com.limelight.android",    # Moonlight Variant
    "com.valvesoftware.steamlink", # Steam Link
}

RETRO_2CH_SYSTEMS = {
    "nes", "snes", "gb", "gba", "gbc", "genesis", "megadrive",
    "mastersystem", "gamegear", "atari2600", "atari7800", "pce",
}

# Receiver sound program per app (route_app_audio_mode). Sports apps get the sports
# program instead, and an app missing here gets Standard.
APP_AUDIO_MODES = {
    "com.google.android.youtube.tv": "Surround Decoder",
    "com.google.android.youtube": "Surround Decoder",
    "com.stremio.one": "Standard",
    "com.netflix.ninja": "Standard",
    "com.amazon.amazonvideo.livingroom": "Standard",
    "com.amazon.avod.thirdpartyclient": "Standard",
    "com.amazon.aiv.eu": "Standard",
    "com.amazon.primevideo.tv": "Standard",
    "com.amazon.video": "Standard",
    "com.spotify.tv.android": "7ch Stereo",
    "com.spotify.music": "7ch Stereo",
    "com.limelight": "Surround Decoder",
    "com.limelight.android": "Surround Decoder",
    "com.valvesoftware.steamlink": "Surround Decoder",
}

# Fallback art used when no lookup succeeds
MOVIE_FALLBACK_POSTER = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=800&q=80"
MOVIE_FALLBACK_BACKDROP = "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1200&q=80"
MUSIC_FALLBACK_ART = "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=800&q=80"
SPORTS_BACKDROP = "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=1200&q=80"
EAGLES_LOGO_FALLBACK = "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png"

APP_BRAND_ART = {
    "prime_video": {
        "title": "Prime Video",
        "subtitle": "▶ Streaming on Prime Video",
        # Own card: it used to share the Netflix photo (a TV showing the Netflix logo)
        "poster": "https://placehold.co/800x1200/00a8e1/ffffff/png?text=PRIME+VIDEO",
        "backdrop": "https://placehold.co/1200x800/00a8e1/ffffff/png?text=PRIME+VIDEO",
        "badge_icon": "mdi:video",
        "badge_color": "teal",
    },
    "netflix": {
        "title": "Netflix",
        "subtitle": "▶ Streaming on Netflix",
        "poster": "https://images.unsplash.com/photo-1574375927938-d5a98e8ffe85?w=800&q=80",
        "backdrop": MOVIE_FALLBACK_BACKDROP,
        "badge_icon": "mdi:netflix",
        "badge_color": "red",
    },
    "stremio": {
        "title": "Stremio",
        "subtitle": "▶ Streaming on Stremio",
        "poster": MOVIE_FALLBACK_POSTER,
        "backdrop": MOVIE_FALLBACK_BACKDROP,
        "badge_icon": "mdi:movie-open",
        "badge_color": "blue",
    },
    "youtube": {
        "title": "YouTube",
        "subtitle": "▶ Streaming on YouTube",
        "poster": "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=1200&q=80",
        "badge_icon": "mdi:youtube",
        "badge_color": "red",
    },
}

# Poster label and badge for each video app: (label, badge icon, badge color).
# _stream_app() says which key an app id belongs to.
STREAM_APP_BADGES = {
    "prime_video": ("Prime Video", "mdi:video", "teal"),
    "netflix": ("Netflix", "mdi:netflix", "red"),
    "stremio": ("Stremio", "mdi:movie-open", "blue"),
    "theatrical_stream": ("Theatrical Stream", "mdi:movie-open", "blue"),
}

IDLE_BOXART = {
    "value": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=800&q=80",
    "backdrop": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=1200&q=80",
}

_GENESIS_ART = {
    "poster": "https://images.unsplash.com/photo-1551103782-8ab07afd45c1?w=800&q=80",
    "backdrop": "https://images.unsplash.com/photo-1551103782-8ab07afd45c1?w=1200&q=80",
}
_ARCADE_ART = {
    "poster": "https://images.unsplash.com/photo-1511512578047-dfb367046420?w=800&q=80",
    "backdrop": "https://images.unsplash.com/photo-1511512578047-dfb367046420?w=1200&q=80",
}

SYSTEM_ART_MAP = {
    "snes": {
        "poster": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=1200&q=80",
    },
    "nes": {
        "poster": "https://images.unsplash.com/photo-1563089145-599997674d42?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1563089145-599997674d42?w=1200&q=80",
    },
    "n64": {
        "poster": "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?w=1200&q=80",
    },
    "psx": {
        "poster": "https://images.unsplash.com/photo-1526509867162-5b0c0d1b4b33?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1526509867162-5b0c0d1b4b33?w=1200&q=80",
    },
    "ps2": {
        "poster": "https://images.unsplash.com/photo-1592478411213-6153e4ebc07d?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1592478411213-6153e4ebc07d?w=1200&q=80",
    },
    "dreamcast": {
        "poster": "https://placehold.co/800x1200/ff6600/ffffff/png?text=DREAMCAST",
        "backdrop": "https://placehold.co/1200x800/ff6600/ffffff/png?text=DREAMCAST",
    },
    "pc": {
        "poster": "https://images.unsplash.com/photo-1587202372775-e229f172b9d7?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=1200&q=80",
    },
    "windows": {
        "poster": "https://images.unsplash.com/photo-1587202372775-e229f172b9d7?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=1200&q=80",
    },
    "steam": {
        "poster": "https://images.unsplash.com/photo-1612287271448-c923296245f7?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=1200&q=80",
    },
    "moonlight": {
        "poster": "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1511512578047-dfb367046420?w=1200&q=80",
    },
    "genesis": _GENESIS_ART,
    "megadrive": _GENESIS_ART,
    "arcade": _ARCADE_ART,
    "mame": _ARCADE_ART,
    "neogeo": _ARCADE_ART,
    "gba": {
        "poster": "https://images.unsplash.com/photo-1531525645387-7f14be1bdbbd?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1531525645387-7f14be1bdbbd?w=1200&q=80",
    },
    "default": {
        "poster": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=1200&q=80",
    },
}

# ------------------------------------------------------------------------------
# SMALL HELPERS: safe state reads and service calls, Onn apps, projector state
# The safe_* helpers return a default or log a warning instead of raising,
# so one offline device can't stop a whole sequence.
# ------------------------------------------------------------------------------
def safe_state_get(entity_id, default=None):
    """An entity's state, or default if it's missing or the read fails."""
    try:
        val = state.get(entity_id)
        return val if val is not None else default
    except Exception:
        return default


def safe_state_getattr(entity_id, attr, default=None):
    """One attribute of an entity, or default if it's missing or the read fails."""
    try:
        attrs = state.getattr(entity_id) or {}
        return attrs.get(attr, default)
    except Exception:
        return default


def safe_service(service_func, **kwargs):
    """Call a service, logging a warning instead of raising if it fails (for example, an
    offline device)."""
    try:
        service_func(**kwargs)
    except Exception as e:
        name = getattr(service_func, "__name__", str(service_func))
        log.warning(f"[Theater] safe_service failed: {name} {kwargs}: {e}")


def safe_float(value, default=0.0):
    """value as a float, or default if it isn't a number."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


SOUND_MODE_FALLBACKS = {
    "Surround Decoder": ["Action Game", "Standard"],
    "Action Game": ["Roleplaying Game", "Surround Decoder", "Standard"],
    "7ch Stereo": ["Surround Decoder", "Standard"],
}


def set_receiver_sound_mode(mode):
    """Select a Yamaha DSP program that actually exists on the receiver.
    The Yamaha integration asserts the name is in sound_mode_list, so check it first."""
    available = safe_state_getattr(RECEIVER, "sound_mode_list") or []
    candidates = [mode] + SOUND_MODE_FALLBACKS.get(mode, [])
    for cand in candidates:
        if not available or cand in available:
            safe_service(media_player.select_sound_mode, entity_id=RECEIVER, sound_mode=cand)
            return cand
    log.warning(f"[Theater] No valid sound mode for {mode!r}. Receiver offers: {available}")
    return None


def pause_spotify_if_playing():
    """Only pause when Spotify is actually playing or active (the entity rejects pause when idle/paused)."""
    st = safe_state_get(SPOTIFY_PLAYER)
    feats = int(safe_float(safe_state_getattr(SPOTIFY_PLAYER, "supported_features"), 0))
    if st in ["playing", "on"] and (feats & 1):  # 1 = PAUSE
        safe_service(media_player.media_pause, entity_id=SPOTIFY_PLAYER)


def normalize_app_id(app_id):
    """Drop an activity suffix: 'com.app/.MainActivity' becomes 'com.app'."""
    if app_id and "/" in app_id:
        return app_id.split("/")[0]
    return app_id


LAUNCHER_APPS = {"com.google.android.apps.tv.launcherx", "com.google.android.tvlauncher"}


def _is_launcher(app_id):
    """True for the Google TV home screen, or when no app is reported."""
    return not app_id or app_id in LAUNCHER_APPS


def get_active_app_id():
    """Single source of truth for the foreground app (Android TV Remote entities)."""
    app_id = (
        safe_state_getattr(ONN_PRO, "app_id")
        or safe_state_getattr(ONN_PRO, "app_name")
        or safe_state_getattr(ONN_REMOTE, "current_activity")
    )
    if app_id:
        return normalize_app_id(app_id)
    return None


def launch_onn_app(package_name):
    """Open an app on the Onn by package name. Uses the Android TV Remote integration
    (deep link first where the app has one), or ADB if that integration is offline."""
    if not package_name:
        return
    # Map deep links / URI schemes (per Google TV Remote protocol recommendation)
    scheme = None
    if "stremio" in package_name:
        scheme = "stremio://"
    # No scheme for HDHomeRun: the app doesn't register hdhomerun://, and the
    # Onn's rejection drops the remote connection, losing the package launch.
    elif "limelight" in package_name or "moonlight" in package_name:
        scheme = "moonlight://"

    # The Android TV Remote integration is the normal path: deep link first, then package.
    if not _onn_remote_down():
        if scheme:
            safe_service(remote.turn_on, entity_id=ONN_REMOTE, activity=scheme)
        safe_service(remote.turn_on, entity_id=ONN_REMOTE, activity=package_name)
        return

    # Remote integration offline: launch through ADB instead.
    _onn_adb_command(f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1")


def _onn_remote_down() -> bool:
    """True when the Onn's Android TV Remote integration is offline."""
    return safe_state_get(ONN_REMOTE) == "unavailable"


def _onn_adb_command(command):
    """Send a shell command over the ADB integration, if it's online."""
    if safe_state_get(ONN_ADB) in [None, "unavailable"]:
        return
    try:
        service.call("androidtv", "adb_command", entity_id=ONN_ADB, command=command)
    except Exception as e:
        log.warning(f"[Theater] ADB command failed ({command!r}): {e}")


def is_booting(grace_seconds=30) -> bool:
    """True for the first grace_seconds after this file loaded (HA start or a pyscript
    reload), so triggers firing on restored states are ignored."""
    return (time.time() - BOOT_TIMESTAMP) < grace_seconds


def is_projector_cold() -> bool:
    """True when the projector lamp is off and cool (current at or under 0.06 A). If the
    current sensor has no reading, falls back to the mains switch being off."""
    current = safe_float(safe_state_get(PROJECTOR_CURRENT), default=None)
    if current is not None:
        return current <= 0.06
    return safe_state_get(PROJECTOR_SWITCH) == "off"


# ------------------------------------------------------------------------------
# POSTER AND BOX ART SENSORS, WHAT'S PLAYING
# sensor.theater_current_poster and sensor.theater_current_boxart are written
# here with state.set and read by the dashboard's Now Playing cards.
# ------------------------------------------------------------------------------
def set_theater_poster(value, title, subtitle, backdrop_url="", media_type="movie",
                       source="unknown", badge_icon="mdi:movie-open", badge_color="blue",
                       raw_title="", **extra_attrs):
    """Write sensor.theater_current_poster, which the Now Playing card shows. Extra
    keyword arguments become extra attributes (the sports scoreboard uses these)."""
    attrs = {
        "friendly_name": "Theater Poster",
        "title": title,
        "subtitle": subtitle,
        "raw_title": raw_title,
        "backdrop_url": backdrop_url,
        "media_type": media_type,
        "source": source,
        "badge_icon": badge_icon,
        "badge_color": badge_color,
    }
    attrs.update(extra_attrs)
    state.set(THEATER_POSTER, value=value, new_attributes=attrs)


def reset_boxart_idle(source="idle", boxart_state="idle"):
    """Put the game box art sensor back to the idle EmulationStation picture."""
    state.set(
        THEATER_BOXART,
        value=IDLE_BOXART["value"],
        new_attributes={
            "friendly_name": "Theater Box Art",
            "title": "EmulationStation",
            "raw_title": "",
            "system": "ARCADE",
            "backdrop_url": IDLE_BOXART["backdrop"],
            "media_type": "game",
            "source": source,
            "state": boxart_state,
        },
    )


def reset_poster_idle(source="idle"):
    """Clear the theater poster (nothing playing)."""
    state.set(
        THEATER_POSTER,
        value="none",
        new_attributes={
            "friendly_name": "Theater Poster",
            "title": "",
            "raw_title": "",
            "backdrop_url": "",
            "media_type": "none",
            "source": source,
        },
    )


def _stream_app(app_id):
    """Which video app is on screen, as a key of STREAM_APP_BADGES. No app id counts as Stremio."""
    if app_id in PRIME_VIDEO_APPS:
        return "prime_video"
    if app_id == NETFLIX_APP:
        return "netflix"
    if app_id == STREMIO_APP or not app_id:
        return "stremio"
    return "theatrical_stream"


def _stream_status_label(play_state, app_label):
    """Poster subtitle such as '▶ Streaming on Netflix', '⏸ Paused on Netflix' or
    'Netflix Idle'."""
    if play_state in ["playing", "on"]:
        return f"▶ Streaming on {app_label}"
    elif play_state == "paused":
        return f"⏸ Paused on {app_label}"
    return f"{app_label} Idle"


def _is_stale_music_session(mp):
    """True when a player's media info belongs to Spotify/music, not the video on screen."""
    app = str(safe_state_getattr(mp, "app_name") or "").lower()
    if "spotify" in app:
        return True
    if str(safe_state_getattr(mp, "media_content_type") or "").lower() == "music":
        return True
    title = safe_state_getattr(mp, "media_title")
    spotify_title = safe_state_getattr(SPOTIFY_PLAYER, "media_title")
    return bool(title and spotify_title and str(title).strip() == str(spotify_title).strip())


def get_active_media_info():
    """What the Onn is showing: {title, artist, app_id, play_state}. Generic titles such
    as 'Netflix' come back as None, and a Spotify session left open in the background
    is ignored while another app is on screen."""
    title = None
    artist = None
    play_state = None

    app_id = get_active_app_id()

    # A Spotify session left open on the Onn keeps reporting its last song after
    # another app takes the screen; skip those players so the song isn't looked
    # up as a movie.
    players = [ONN_PRO, ONN_PRO_2]
    if app_id not in MUSIC_APPS:
        players = [mp for mp in players if not _is_stale_music_session(mp)]

    if not title:
        for mp in players:
            for attr in ["media_title", "media_series_title", "title"]:
                val = safe_state_getattr(mp, attr)
                if val and str(val).strip() not in ["unknown", "unavailable", "None", ""]:
                    title = str(val).strip()
                    break
            if title:
                break

    if not artist:
        for mp in players:
            for a_attr in ["media_series_title", "media_artist", "artist"]:
                val = safe_state_getattr(mp, a_attr)
                if val and str(val).strip() not in ["unknown", "unavailable", "None", ""]:
                    artist = str(val).strip()
                    break
            if artist:
                break

    # The ADB player tracks the foreground app's playback, so it wins when it has a state.
    adb_state = safe_state_get(ONN_ADB)
    if adb_state in ["playing", "paused", "idle"]:
        play_state = adb_state
    if not play_state:
        play_state = safe_state_get(ONN_PRO)

    generic_titles = {
        "unknown", "unavailable", "none", "",
        "stremio", "stremio theatrical", "ready to stream",
        "prime video", "amazon prime video", "netflix", "youtube", "android tv"
    }
    if title and title.lower().strip() in generic_titles:
        title = None

    if artist and artist.lower().strip() in generic_titles:
        artist = None

    return {
        "title": title,
        "artist": artist,
        "app_id": app_id,
        "play_state": play_state or "idle",
    }


@service
def theater_resilience_status():
    """Debug: how many art lookups are cached, and which services are being skipped after failures."""
    open_circuits = [s for s, state_dict in _CIRCUIT_STATE.items() if time.time() < state_dict.get("tripped_until", 0)]
    return {
        "cache_entries": len(_ART_CACHE),
        "open_circuits": open_circuits,
        "circuit_states": _CIRCUIT_STATE,
    }


# ------------------------------------------------------------------------------
# SPORTS SCOREBOARD AND THE MOVIE/MUSIC POSTER
# ------------------------------------------------------------------------------
EAGLES_SENSOR = "sensor.philadelphia_eagles"
SPORT_BADGES = {
    "football": "mdi:football",
    "basketball": "mdi:basketball",
    "hockey": "mdi:hockey-puck",
    "baseball": "mdi:baseball",
    "soccer": "mdi:soccer",
}


def _period_label(sport, period, clock):
    """'Q3 4:12', 'P2 10:05', or the clock alone for baseball ('Top 5th')."""
    if sport == "baseball":
        return clock
    if period and clock:
        return f"{'P' if sport == 'hockey' else 'Q'}{period} {clock}"
    return None


def _set_sports_poster(source_label=None):
    """Writes the featured team's scoreboard to the theater poster. source_label
    (e.g. "HDHomeRun") is shown in the pre-game subtitle when given."""
    team_sensor = safe_state_getattr(FEATURED_TEAM, "sensor") or EAGLES_SENSOR
    try:
        team = state.getattr(team_sensor) or {}
    except Exception:
        team = {}
    attr = team.get
    sport = attr("sport") or "football"

    opp_name = attr("opponent_name")
    opp_abbr = attr("opponent_abbr") or opp_name or "OPP"
    team_abbr = attr("team_abbr") or "PHI"
    team_score = attr("team_score")
    opp_score = attr("opponent_score")
    quarter = attr("quarter")
    clock = attr("clock")
    down_dist = attr("down_distance_text")
    team_logo = attr("team_logo") or EAGLES_LOGO_FALLBACK
    team_name = attr("team_name") or "Eagles"
    game_state = safe_state_get(team_sensor)
    trim = safe_state_get(ANNOUNCER_VOLUME) or "0.0"

    if game_state == "IN" and team_score is not None and opp_score is not None:
        sports_title = f"{team_abbr} {team_score} - {opp_score} {opp_abbr}"
        sub_parts = []
        period = _period_label(sport, quarter, clock)
        if period:
            sub_parts.append(period)
        if down_dist:
            sub_parts.append(down_dist)
        sub_parts.append(f"Booth Trim: {trim} dB")
        sports_subtitle = " • ".join(sub_parts)
    elif game_state == "POST" and team_score is not None and opp_score is not None:
        sports_title = f"FINAL: {team_abbr} {team_score} - {opp_score} {opp_abbr}"
        sports_subtitle = f"Final Score • Stadium Surround • Booth Trim: {trim} dB"
    else:
        sports_title = f"{team_name} vs {opp_name}" if opp_name else "Live Sports Broadcast"
        sub_parts = ["Stadium Surround"] + ([source_label] if source_label else []) + [f"Booth Trim: {trim} dB"]
        sports_subtitle = " • ".join(sub_parts)

    set_theater_poster(
        team_logo, sports_title, sports_subtitle,
        backdrop_url=SPORTS_BACKDROP, media_type="sports",
        source="sports", badge_icon=SPORT_BADGES.get(sport, "mdi:scoreboard"), badge_color="green",
        team_logo=team_logo,
        opponent_logo=attr("opponent_logo"),
        team_score=team_score,
        opponent_score=opp_score,
        team_abbr=team_abbr,
        opponent_abbr=opp_abbr,
        quarter=quarter,
        clock=clock,
        down_distance_text=down_dist,
        last_play=attr("last_play"),
        possession=attr("possession"),
        game_state=game_state,
    )


# Plain function (no trigger): called directly by the play_* services and by the
# debounced trigger wrapper below.
def update_theater_media_art():
    """Set the theater poster in movie, music and sports modes. In order: the sports
    scoreboard; Spotify album art; YouTube; then for other video apps an art lookup
    by title, the Onn's own cover art, a generic poster with the title, and finally
    the app's brand card."""
    mode = safe_state_get(THEATER_MODE)
    if mode not in ["movie", "music", "sports"]:
        return

    media_info = get_active_media_info()
    raw_title = media_info["title"]
    artist = media_info["artist"]
    app_id = media_info["app_id"]
    play_state = media_info["play_state"]

    onn_art = (
        safe_state_getattr(ONN_PRO, "entity_picture")
        or safe_state_getattr(ONN_PRO_2, "entity_picture")
    )
    if onn_art and mode != "music" and app_id not in MUSIC_APPS:
        if "spotifycdn.com" in str(onn_art) or "spotify" in str(onn_art).lower():
            onn_art = None

    if mode == "sports" or app_id in SPORTS_APPS:
        _set_sports_poster()
        return

    # In movie mode, ignore any lingering background Spotify sessions
    if mode == "movie":
        if app_id in MUSIC_APPS:
            app_id = STREMIO_APP
            raw_title = None
            artist = None
            onn_art = None

    if mode == "music" or app_id in MUSIC_APPS:
        album_art = (
            onn_art
            or safe_state_getattr(SPOTIFY_PLAYER, "entity_picture")
            or MUSIC_FALLBACK_ART
        )
        music_title = (
            raw_title
            or safe_state_getattr(SPOTIFY_PLAYER, "media_title")
            or "Spotify Music"
        )
        artist_val = artist or safe_state_getattr(SPOTIFY_PLAYER, "media_artist") or "Spotify"
        album = safe_state_getattr(SPOTIFY_PLAYER, "media_album_name") or "Hi-Fi Audio"
        set_theater_poster(
            album_art, music_title, f"{artist_val} • {album}",
            backdrop_url=album_art, media_type="music",
            source="spotify", badge_icon="mdi:spotify", badge_color="green",
        )
        return

    if app_id in YOUTUBE_APPS:
        yt_art = onn_art or APP_BRAND_ART["youtube"]["poster"]
        set_theater_poster(
            yt_art, raw_title or "YouTube", _stream_status_label(play_state, "YouTube"),
            backdrop_url=yt_art, media_type="youtube",
            source="youtube", badge_icon="mdi:youtube", badge_color="red",
        )
        return

    stream_src = _stream_app(app_id)
    app_label, badge_icon, badge_color = STREAM_APP_BADGES[stream_src]

    subtitle_val = _stream_status_label(play_state, app_label)

    # 1. Art lookup by title (TMDB, then Cinemeta, then TVMaze)
    data = _fetch_movie_or_tv_art(raw_title, artist=artist) if (raw_title or artist) else None
    if data and isinstance(data, dict) and data.get("poster"):
        set_theater_poster(
            data["poster"], data.get("title") or raw_title or artist, subtitle_val,
            raw_title=raw_title or artist or "", backdrop_url=data.get("backdrop", ""),
            media_type=data.get("media_type", "movie"),
            source=data.get("source", stream_src), badge_icon=badge_icon, badge_color=badge_color,
        )
        return

    # 2. The Onn's own cover art
    if onn_art and onn_art not in ["unknown", "unavailable", "None", ""]:
        set_theater_poster(
            onn_art, raw_title or artist or "Now Playing", subtitle_val,
            raw_title=raw_title or artist or "", backdrop_url=onn_art,
            media_type="movie", source="androidtv_stream",
            badge_icon=badge_icon, badge_color=badge_color,
        )
        return

    # 3. No image found, but there is a title: generic poster with the title
    if raw_title or artist:
        candidates = get_search_candidates(raw_title, artist=artist)
        best_title = artist if (artist and artist not in ["Stremio", "Prime Video", "Netflix", "None"]) else (candidates[0] if candidates else raw_title)
        fallback_poster = MOVIE_FALLBACK_POSTER
        set_theater_poster(
            fallback_poster, best_title,
            subtitle_val,
            raw_title=raw_title or "",
            backdrop_url=MOVIE_FALLBACK_BACKDROP,
            media_type="movie", source=f"{stream_src}_title_match",
            badge_icon=badge_icon, badge_color=badge_color,
        )
        return

    # 4. Nothing at all: the app's brand card (APP_BRAND_ART)
    brand = APP_BRAND_ART.get(stream_src)
    if brand:
        fallback_poster = brand["poster"]
        fallback_backdrop = brand["backdrop"]
        fallback_title = brand["title"]
        badge_icon = brand.get("badge_icon", badge_icon)
        badge_color = brand.get("badge_color", badge_color)
        if play_state in ["playing", "on"]:
            fallback_sub = brand["subtitle"]
        else:
            fallback_sub = f"Ready to Stream • {fallback_title}"
    else:
        fallback_poster = MOVIE_FALLBACK_POSTER
        fallback_backdrop = MOVIE_FALLBACK_BACKDROP
        fallback_title = app_label
        fallback_sub = subtitle_val

    set_theater_poster(
        fallback_poster, fallback_title,
        fallback_sub,
        raw_title="",
        backdrop_url=fallback_backdrop,
        media_type="movie", source=f"{stream_src}_stream",
        badge_icon=badge_icon, badge_color=badge_color,
    )


@state_trigger(
    f"{ONN_PRO}, "
    f"{ONN_ADB}, "
    f"{ONN_PRO}.media_title, "
    f"{ONN_PRO}.media_series_title, "
    f"{ONN_PRO}.entity_picture, "
    f"{ONN_PRO}.app_id, "
    f"{ONN_PRO}.app_name, "
    f"{ONN_PRO_2}.media_title, "
    f"{ONN_PRO_2}.entity_picture, "
    f"{ONN_REMOTE}, "
    f"{ONN_REMOTE}.current_activity, "
    f"{ANNOUNCER_VOLUME}, "
    f"{FEATURED_TEAM}, "
    # Team Tracker sensors: a score change redraws the scoreboard
    f"{EAGLES_SENSOR}, "
    f"{EAGLES_SENSOR}.team_score, "
    f"{EAGLES_SENSOR}.opponent_score, "
    "sensor.nhl_philadelphia_flyers.team_score, "
    "sensor.nhl_philadelphia_flyers.opponent_score, "
    "sensor.nba_philadelphia_76ers.team_score, "
    "sensor.nba_philadelphia_76ers.opponent_score, "
    "sensor.mlb_philadelphia_phillies.team_score, "
    "sensor.mlb_philadelphia_phillies.opponent_score, "
    f"{THEATER_MODE}, "
    f"{THEATER_IN_USE}"
)
def on_theater_media_changed():
    """Redraw the poster when what's playing changes. Waits 0.5 s so a burst of changes
    draws once."""
    # Debounce: a newer trigger cancels this run, so only the last burst event renders.
    task.unique("theater_media_art")
    task.sleep(0.5)
    update_theater_media_art()


# ------------------------------------------------------------------------------
# GAMING PC WINDOW AND THE GAME POSTER
# HASS.Agent on the PC reports the foreground window; the "Gaming PC Active
# Game" template in configuration.yaml filters it into sensor.gaming_pc_active_game.
# ------------------------------------------------------------------------------
PC_SYSTEM_WINDOWS = {
    "desktop", "idle / desktop", "task switching", "taskbar", "explorer", "start",
    "windows shell experience host", "program manager", "none",
    "unknown", "unavailable", "null", "undefined", ""
}

PC_NON_GAME_APPS = {
    "hass.agent", "settings", "calculator", "task manager",
    "device manager", "command prompt", "powershell", "terminal",
    "notepad", "discord", "spotify", "spotify free", "spotify premium"
}

RE_PC_CLEANUP = re.compile(
    r"\s*(?:\(x(?:64|86)\)|\[DirectX\s*\d*\]|\(DX\d+\)|v\d+(?:\.\d+)+|build\s*\d+|™|®|\(C\).*?$)",
    re.IGNORECASE
)


def parse_pc_active_window(raw_window):
    """
    Parses sensor.gaming_pc_active_game into (game_title, state, is_steam).
    States: 'playing' (in-game), 'idle' (Steam BPM / launcher / ready), 'desktop' / 'off'
    """
    if not raw_window or str(raw_window).strip() in ["", "none", "None", "unknown", "unavailable"]:
        return ("", "off", False)

    w = str(raw_window).strip()
    w_lower = w.lower()

    if w_lower in PC_SYSTEM_WINDOWS:
        return ("", "desktop", False)

    # Check for browser windows
    if any([w_lower.endswith(b) for b in ["- google chrome", "- microsoft edge", "- mozilla firefox", "- brave"]]):
        return ("", "desktop", False)

    if w_lower in PC_NON_GAME_APPS:
        return ("", "desktop", False)

    # Steam Big Picture Mode / Steam client
    if "steam big picture" in w_lower or w_lower == "steam":
        return ("Steam Big Picture Mode", "idle", True)

    # Clean game window title
    clean = RE_ROM_EXT.sub("", w)
    clean = RE_ROM_TAGS.sub("", clean)
    clean = RE_PC_CLEANUP.sub("", clean).strip()

    if not clean or clean.lower() in PC_SYSTEM_WINDOWS:
        return ("", "desktop", False)

    return (clean, "playing", False)


RE_CAMEL_GAP = re.compile(r"(?<=[a-z])(?=[A-Z])")


def _spaced_title(title):
    """Process names like "ApeOut" -> "Ape Out" so art lookups match. Titles with spaces are left alone."""
    t = str(title or "").strip()
    return t if " " in t else RE_CAMEL_GAP.sub(" ", t)


def is_pc_game_playing():
    """Returns True if a PC game is actively running on the ROG Gaming PC."""
    win = safe_state_get(PC_ACTIVE_WINDOW)
    title, state_val, _ = parse_pc_active_window(win)
    return state_val == "playing"


# Plain function (no trigger): called directly by play_pc_game and by the
# debounced trigger wrapper below.
def _game_now_showing(gpu_temp_str):
    """Work out what game mode is showing. The first match wins:
      1. Batocera playing a game
      2. The PC playing a game
      3. Steam Big Picture menu on the PC
      4. Batocera in its game menu
      5. The PC on and a Moonlight app open on the Onn
      6. Nothing: the EmulationStation idle card
    Returns a dict:
      title        the game's name ("" for none); also sent as raw_title
      display      the title to show if the art lookup finds nothing better
      state        "playing" or "idle"
      system       the system label on the poster (SNES, PC, STEAM...)
      subtitle     the line under the title
      art_system   which system to look up box art for; None skips the lookup
      defaults     SYSTEM_ART_MAP entry to use when there is no box art
      badge_icon, badge_color
    """
    batocera_title = safe_state_get(BATOCERA_GAME)
    batocera_sys = (safe_state_get(BATOCERA_SYSTEM) or "").lower()
    batocera_st = safe_state_get(BATOCERA_STATE)
    batocera_has_title = batocera_title and batocera_title not in ["None", "unknown", "unavailable", ""]

    # sensor.gaming_pc_active_game, filtered from HASS.Agent's active window
    pc_title, pc_st, is_steam = parse_pc_active_window(safe_state_get(PC_ACTIVE_WINDOW))
    is_pc_playing = pc_st == "playing" and bool(pc_title)

    # 1. Batocera playing a game
    if batocera_st == "playing" and batocera_has_title:
        title = batocera_title
        art_system = batocera_sys
        if batocera_sys == "moonlight" and is_pc_playing:
            # Batocera only knows it launched Moonlight/Big Picture; the PC knows the game
            title = _spaced_title(pc_title)
            art_system = "pc"
        if batocera_sys == "moonlight":
            subtitle = "🎮 Streaming • PC via Moonlight"
        else:
            subtitle = f"🎮 Playing • {(batocera_sys.upper() or 'RETRO')} Gaming"
        return {
            "title": title, "display": title, "state": "playing",
            "system": batocera_sys.upper() or "RETRO", "subtitle": subtitle,
            "art_system": art_system if title else None,
            "defaults": SYSTEM_ART_MAP.get(batocera_sys, SYSTEM_ART_MAP["default"]),
            "badge_icon": "mdi:gamepad-variant", "badge_color": "green",
        }

    # 2. The PC playing a game
    if is_pc_playing:
        temp_suffix = f" (GPU: {gpu_temp_str})" if gpu_temp_str else ""
        return {
            "title": pc_title, "display": pc_title, "state": "playing",
            "system": "STEAM" if is_steam else "PC",
            "subtitle": f"🎮 Playing • ASUS ROG Gaming PC{temp_suffix}",
            "art_system": "pc", "defaults": SYSTEM_ART_MAP["pc"],
            "badge_icon": "mdi:steam" if is_steam else "mdi:desktop-tower", "badge_color": "purple",
        }

    temp_suffix = f" • GPU {gpu_temp_str}" if gpu_temp_str else ""

    # 3. Steam Big Picture menu on the PC
    if pc_st == "idle" and is_steam:
        return {
            "title": "Steam Big Picture Mode", "display": "Steam Big Picture Mode", "state": "idle",
            "system": "STEAM", "subtitle": f"🕹️ Ready • Steam Library & Carousel{temp_suffix}",
            "art_system": None, "defaults": SYSTEM_ART_MAP["steam"],
            "badge_icon": "mdi:steam", "badge_color": "blue",
        }

    # 4. Batocera in its game menu
    if batocera_has_title:
        return {
            "title": batocera_title, "display": batocera_title, "state": batocera_st or "idle",
            "system": batocera_sys.upper() or "ARCADE",
            "subtitle": "🕹️ Ready • EmulationStation System Menu",
            "art_system": batocera_sys,
            "defaults": SYSTEM_ART_MAP.get(batocera_sys, SYSTEM_ART_MAP["default"]),
            "badge_icon": "mdi:gamepad-variant", "badge_color": "green",
        }

    # 5. The PC on, and a Moonlight/Steam Link app open on the Onn. A PC that is
    #    just switched on (or Batocera between games) doesn't count.
    pc_on = safe_state_get(PC_SWITCH) == "on" or safe_state_get(PC_ONLINE) == "on"
    if pc_on and get_active_app_id() in GAME_APPS:
        return {
            "title": "ASUS ROG Gaming PC", "display": "ASUS ROG Gaming PC", "state": "idle",
            "system": "PC", "subtitle": f"🕹️ Ready • PC Gaming via Moonlight{temp_suffix}",
            "art_system": None, "defaults": SYSTEM_ART_MAP["pc"],
            "badge_icon": "mdi:desktop-tower", "badge_color": "purple",
        }

    # 6. Nothing: the EmulationStation idle card
    return {
        "title": "", "display": "EmulationStation Carousel", "state": "idle",
        "system": "ARCADE", "subtitle": "🕹️ Ready • EmulationStation System Menu",
        "art_system": None, "defaults": SYSTEM_ART_MAP["default"],
        "badge_icon": "mdi:gamepad-variant", "badge_color": "green",
    }


def update_game_poster():
    """Set the box art and theater poster in game mode, from Batocera or the gaming PC.
    _game_now_showing() decides what is showing; this looks up the box art and sets it."""
    if safe_state_get(THEATER_MODE) != "game":
        return

    gpu_temp = safe_state_get(PC_GPU_TEMP)
    gpu_temp_str = f"{round(float(gpu_temp))}°C" if (gpu_temp and str(gpu_temp).replace('.', '', 1).isdigit()) else ""

    show = _game_now_showing(gpu_temp_str)
    data = None
    if show["art_system"] is not None:
        data = _fetch_game_art_from_secrets(show["title"], show["art_system"])

    poster_val = data.get("poster") if (data and data.get("poster")) else show["defaults"]["poster"]
    backdrop_val = data.get("backdrop") if (data and data.get("backdrop")) else show["defaults"]["backdrop"]
    source_val = data.get("source", "system_art") if data else "system_art"
    final_title = data.get("title", show["display"]) if data else show["display"]

    state.set(
        THEATER_BOXART,
        value=poster_val,
        new_attributes={
            "friendly_name": "Theater Box Art",
            "title": final_title,
            "raw_title": show["title"],
            "system": show["system"],
            "backdrop_url": backdrop_val,
            "media_type": "game",
            "source": source_val,
            "state": show["state"],
            "gpu_temperature": gpu_temp_str,
        },
    )

    set_theater_poster(
        poster_val, final_title, show["subtitle"],
        raw_title=show["title"], backdrop_url=backdrop_val, media_type="game",
        source=source_val, badge_icon=show["badge_icon"], badge_color=show["badge_color"],
        system=show["system"], gpu_temperature=gpu_temp_str,
    )


@state_trigger(
    f"{BATOCERA_GAME}, "
    f"{BATOCERA_STATE}, "
    f"{BATOCERA_SYSTEM}, "
    f"{PC_ACTIVE_WINDOW}, "
    f"{PC_GPU_TEMP}, "
    f"{PC_SWITCH}, "
    f"{PC_ONLINE}, "
    f"{THEATER_MODE}"
)
def on_theater_game_changed():
    """Redraw the game poster when the game, system or PC window changes. Waits 0.5 s so
    a burst of changes draws once."""
    # Debounce: a newer trigger cancels this run, so only the last burst event renders.
    task.unique("theater_game_art")
    task.sleep(0.5)
    update_game_poster()


# ------------------------------------------------------------------------------
# DASHBOARD MODE PICKER, AND POSTERS AT STARTUP
# input_select.basement_theater_mode mirrors sensor.theater_mode, and picking a
# mode on it starts that mode.
# ------------------------------------------------------------------------------
THEATER_MODE_TO_SELECT = {
    "movie": "Movie",
    "game": "Game",
    "music": "Music",
    "sports": "Sports",
    "off": "Off",
}

_SELECT_SYNC_PENDING = {}  # option.lower() -> expiry timestamp (changes we made ourselves)


def sync_theater_select(mode_str: str):
    """Syncs sensor.theater_mode -> input_select.basement_theater_mode."""
    target_option = THEATER_MODE_TO_SELECT.get(str(mode_str).lower(), "Off")
    if safe_state_get(THEATER_SELECT) != target_option:
        _SELECT_SYNC_PENDING[target_option.lower()] = time.time() + 5
        safe_service(input_select.select_option, entity_id=THEATER_SELECT, option=target_option)


@state_trigger(THEATER_SELECT)
def on_theater_select_changed(value=None, old_value=None):
    """Someone picked a mode on the dashboard picker: start that mode (Off runs curtain call).
    Changes made by sync_theater_select itself are ignored."""
    if is_booting() or value == old_value or not value:
        return
    val_norm = str(value).strip().lower()
    # Ignore changes we made ourselves via sync_theater_select
    if _SELECT_SYNC_PENDING.pop(val_norm, 0) > time.time():
        return
    cur_mode = str(safe_state_get(THEATER_MODE, "off")).strip().lower()
    if val_norm == cur_mode:
        return

    if val_norm == "movie":
        play_movie()
    elif val_norm == "game":
        play_game()
    elif val_norm == "music":
        play_music()
    elif val_norm == "sports":
        play_sports()
    elif val_norm == "off":
        session_end_house_lights()


@time_trigger("startup")
def init_theater_poster_entity():
    """At startup: create the poster, box art and mode picker states if they're missing,
    then draw the current poster."""
    if not safe_state_get(THEATER_POSTER):
        reset_poster_idle(source="initialization")
    if not safe_state_get(THEATER_BOXART):
        reset_boxart_idle(source="initialization")
    if not safe_state_get(THEATER_SELECT):
        sync_theater_select(safe_state_get(THEATER_MODE, "off"))

    task.sleep(2.0)
    mode = safe_state_get(THEATER_MODE)
    if mode == "game":
        update_game_poster()
    elif mode in ["movie", "music", "sports"]:
        update_theater_media_art()


# ------------------------------------------------------------------------------
# WORKING OUT THE THEATER MODE; RECEIVER AND ONN POWER BUTTONS
# ------------------------------------------------------------------------------
@time_trigger("startup")
@state_trigger(
    f"{RECEIVER}, {ONN_PRO}, {ONN_REMOTE}, "
    f"{BATOCERA_STATE}, {BATOCERA_SWITCH}, "
    f"{PC_ACTIVE_WINDOW}, {PC_SWITCH}, {PC_ONLINE}"
)
def update_theater_mode():
    """Work out sensor.theater_mode (off, movie, music, sports or game) and mirror it to
    the dashboard picker. Receiver off means off. On HDMI1 the Onn's foreground app
    decides; HDMI2/HDMI3 or a game running means game."""
    receiver_state = state.get(RECEIVER)
    rx_attrs = state.getattr(RECEIVER) or {}
    source = rx_attrs.get("source")

    if receiver_state != "on":
        mode = "off"
    elif source == "HDMI1":
        onn_app = get_active_app_id()
        cur_mode = safe_state_get(THEATER_MODE, "movie")

        if onn_app in MUSIC_APPS:
            mode = "music"
        elif onn_app in SPORTS_APPS:
            mode = "sports"
        elif onn_app in GAME_APPS:
            mode = "game"
        elif onn_app in MOVIE_APPS:
            mode = "movie"
        else:
            # launcher / unknown: keep what we had
            mode = cur_mode if cur_mode in ["movie", "sports", "music"] else "movie"
    elif source in ["HDMI2", "HDMI3"] or safe_state_get(BATOCERA_STATE) == "playing" or is_pc_game_playing():
        mode = "game"
    elif source in ["Bluetooth", "SERVER", "NET", "TUNER", "AirPlay", "Spotify"]:
        mode = "music"
    else:
        mode = "movie"

    state.set(
        THEATER_MODE,
        value=mode,
        new_attributes={
            "device_class": "enum",
            "friendly_name": "Theater Mode",
            "icon": "mdi:theater",
            "active_source": source,
        },
    )
    sync_theater_select(mode)


@time_trigger("startup")
@state_trigger(RECEIVER)
def update_theater_in_use():
    """binary_sensor.theater_in_use follows the receiver: on straight away, off once the
    receiver has been off for 5 s."""
    task.unique("theater_in_use_debounce")
    receiver_on = state.get(RECEIVER) == "on"

    if receiver_on:
        state.set(THEATER_IN_USE, value="on")
    else:
        task.sleep(5)
        if state.get(RECEIVER) != "on":
            state.set(THEATER_IN_USE, value="off")


@time_trigger("startup")
@state_trigger(
    f"{ONN_PRO}.app_id, {ONN_REMOTE}.current_activity, "
    f"{THEATER_MODE}, {THEATER_IN_USE}"
)
def update_announcer_bar():
    """Shows the booth announcer bar for sports and for Prime Video (Thursday Night Football)."""
    show = safe_state_get(THEATER_IN_USE) == "on" and (
        safe_state_get(THEATER_MODE) == "sports"
        or (safe_state_get(THEATER_MODE) == "movie" and get_active_app_id() in ANNOUNCER_BAR_APPS)
    )
    value = "on" if show else "off"
    if safe_state_get(ANNOUNCER_BAR) != value:
        state.set(ANNOUNCER_BAR, value=value, new_attributes={
            "friendly_name": "Theater Announcer Bar",
            "icon": "mdi:account-voice",
        })


@state_trigger(f"{RECEIVER} == 'off'")
def handle_receiver_power_off():
    """The receiver was turned off outside HA (its own remote or front button) during a
    session: run curtain call so everything else shuts down too."""
    if is_booting():
        return
    if safe_state_get(CURTAIN_CALL) == "on":
        return

    was_active = (
        safe_state_get(THEATER_IN_USE) == "on"
        or safe_state_get(PROJECTOR_SWITCH) == "on"
        or safe_state_get(BATOCERA_SWITCH) == "on"
        or safe_state_get(THEATER_MODE) in ["movie", "game", "music", "sports"]
    )
    if was_active:
        log.info("[Theater] Unmanaged receiver shutdown detected! Initiating clean session teardown...")
        session_end_house_lights()


@state_trigger(f"{ONN_PRO} == 'off'", state_hold=4)
def onn_power_button_curtain_call(old_value=None):
    """The Onn remote's power button (sleeping the Onn mid-session) runs curtain call.
    CEC alone often leaves the receiver and projector on. Waking is handled by
    onn_power_button_wake."""
    if is_booting() or old_value != "on":
        return
    if safe_state_get(CURTAIN_CALL) == "on":
        return  # session end is already running (it sleeps the Onn itself)
    if safe_state_get(THEATER_IN_USE) != "on" or safe_state_get(RECEIVER) != "on":
        return  # nothing running; a receiver that went off is handled above
    if _gaming_on_hdmi2():
        return  # the Onn sleeps normally while Batocera is on HDMI2
    log.info("[Theater] Onn powered off mid-session. Running curtain call.")
    session_end_house_lights()


# ------------------------------------------------------------------------------
# SOUND MODES, VOLUME AND THE ANNOUNCER LEVEL
# "Announcer" is the receiver's center-channel trim: turned down it leaves
# mostly crowd noise, turned up it boosts commentary. Hardware range -10 to +10 dB.
# ------------------------------------------------------------------------------
@state_trigger(f"{BATOCERA_STATE} == 'playing'")
def configure_batocera_audio():
    """A Batocera game started: Straight for 2-channel retro systems, Surround Decoder
    for the rest, announcer back to 0 dB."""
    if is_booting():
        return
    system_id = (safe_state_get(BATOCERA_SYSTEM) or "").lower()
    snd = "Straight" if system_id in RETRO_2CH_SYSTEMS else "Surround Decoder"
    set_receiver_sound_mode(snd)
    safe_service(rest_command.yamaha_set_center_trim, level=0.0)


@service
def apply_sports_audio_mode():
    """Sports sound program, with the announcer at the slider's level. Only while the
    theater is in use."""
    if safe_state_get(THEATER_IN_USE) != "on":
        return
    set_receiver_sound_mode("Sports")
    level_float = safe_float(safe_state_get(ANNOUNCER_VOLUME), -10.0)
    safe_service(rest_command.yamaha_set_center_trim, level=level_float)


@service
def reset_standard_audio_mode(target_dsp="Standard"):
    """Set a sound program (Standard unless given) and put the announcer back to 0 dB."""
    set_receiver_sound_mode(target_dsp)
    safe_service(rest_command.yamaha_set_center_trim, level=0.0)


ANNOUNCER_PRESET_LEVELS = {
    "Stadium Crowd": -10.0,
    "Broadcast Ref": 0.0,
    "Dialogue Boost": 3.0,
}


def _announcer_zone(level):
    """Returns the preset whose range contains this level, or None between ranges."""
    if level is None:
        return None
    if level <= -8.0:
        return "Stadium Crowd"
    if -2.0 <= level <= 1.5:
        return "Broadcast Ref"
    if level >= 2.0:
        return "Dialogue Boost"
    return None


@state_trigger(ANNOUNCER_VOLUME)
def sync_announcer_volume_to_hardware(value=None):
    """The announcer slider moved: send the level to the receiver (sports and Prime
    Video only) and keep the preset picker in step."""
    if safe_state_get(THEATER_IN_USE) != "on":
        return
    if safe_state_get(THEATER_MODE) == "sports" or get_active_app_id() in ANNOUNCER_BAR_APPS:
        level_float = safe_float(value, default=None)
        if level_float is not None:
            safe_service(rest_command.yamaha_set_center_trim, level=level_float)
            # Sync 3-way toggle state
            zone = _announcer_zone(level_float)
            if zone and zone != safe_state_get(ANNOUNCER_PRESET):
                input_select.select_option(entity_id=ANNOUNCER_PRESET, option=zone)


@service
def theater_set_announcer_preset(preset=None):
    """Pick an announcer preset (Stadium Crowd, Broadcast Ref, Dialogue Boost): sets the
    picker and the slider, and the receiver if the theater is on."""
    if not preset:
        return
    if preset in ANNOUNCER_PRESET_LEVELS:
        input_select.select_option(entity_id=ANNOUNCER_PRESET, option=preset)
        new_val = ANNOUNCER_PRESET_LEVELS[preset]
        input_number.set_value(entity_id=ANNOUNCER_VOLUME, value=new_val)
        if safe_state_get(THEATER_IN_USE) == "on":
            safe_service(rest_command.yamaha_set_center_trim, level=new_val)


@state_trigger(ANNOUNCER_PRESET)
def sync_announcer_preset_to_hardware(value=None):
    """The preset picker changed: move the slider to that preset's level (unless it's
    already inside the preset's range) and send it to the receiver."""
    if not value:
        return
    if value in ANNOUNCER_PRESET_LEVELS:
        cur_vol = safe_float(safe_state_get(ANNOUNCER_VOLUME), None)
        # The level slider already lies in this preset's range (it selected the
        # preset itself), so keep the user's exact level instead of snapping.
        if _announcer_zone(cur_vol) == value:
            return
        new_val = ANNOUNCER_PRESET_LEVELS[value]
        if cur_vol != new_val:
            input_number.set_value(entity_id=ANNOUNCER_VOLUME, value=new_val)
        if safe_state_get(THEATER_IN_USE) == "on":
            safe_service(rest_command.yamaha_set_center_trim, level=new_val)


def _step_avr_volume(direction: str, step_db: float):
    """One volume write per tap. The Yamaha integration maps volume_level = dB / 100 + 1,
    so 1 dB is 0.01. (A second YNC "Up 1 dB" step used to follow, doubling some taps.)"""
    vol_float = safe_float(safe_state_getattr(RECEIVER, "volume_level"), 0.5)
    step_val = safe_float(step_db, 1.0)
    delta = step_val / 100.0
    new_vol = min(1.0, max(0.0, vol_float + delta if direction == "Up" else vol_float - delta))
    safe_service(media_player.volume_set, entity_id=RECEIVER, volume_level=round(new_vol, 3))


@service
def theater_volume_up(step_db=1.0):
    """Receiver volume up by step_db."""
    _step_avr_volume("Up", step_db)


@service
def theater_volume_down(step_db=1.0):
    """Receiver volume down by step_db."""
    _step_avr_volume("Down", step_db)


@service
def theater_announcer_up(step=1.0):
    """Announcer level up by step dB (at most +10)."""
    cur_val = safe_float(safe_state_get(ANNOUNCER_VOLUME), -10.0)
    step_val = safe_float(step, 1.0)
    new_val = min(10.0, round(cur_val + step_val, 1))
    input_number.set_value(entity_id=ANNOUNCER_VOLUME, value=new_val)


@service
def theater_announcer_down(step=1.0):
    """Announcer level down by step dB (at least -10)."""
    cur_val = safe_float(safe_state_get(ANNOUNCER_VOLUME), 0.0)
    step_val = safe_float(step, 1.0)
    new_val = max(-10.0, round(cur_val - step_val, 1))
    input_number.set_value(entity_id=ANNOUNCER_VOLUME, value=new_val)


@service
def theater_announcer_mute():
    """Toggle the announcer between -10 dB (crowd only) and 0 dB."""
    cur_val = safe_float(safe_state_get(ANNOUNCER_VOLUME), 0.0)
    new_val = 0.0 if cur_val <= -9.5 else -10.0
    input_number.set_value(entity_id=ANNOUNCER_VOLUME, value=new_val)


@state_trigger(
    f"{ONN_PRO}.app_id, "
    f"{ONN_REMOTE}.current_activity"
)
def route_app_audio_mode():
    """When the Onn's app changes on HDMI1, pick its sound program from APP_AUDIO_MODES.
    Sports apps get the sports program."""
    task.unique("theater_audio_routing")

    if is_booting() or safe_state_get(THEATER_IN_USE) != "on":
        return

    if safe_state_getattr(RECEIVER, "source") != "HDMI1":
        return

    app_id = get_active_app_id()
    if _is_launcher(app_id):
        return

    if app_id in SPORTS_APPS or safe_state_get(THEATER_MODE) == "sports":
        apply_sports_audio_mode()
        return

    target_mode = APP_AUDIO_MODES.get(app_id, "Standard")
    reset_standard_audio_mode(target_dsp=target_mode)


# ------------------------------------------------------------------------------
# HARDWARE INTERLOCK CALLS (logic lives in interlocks.py)
# ------------------------------------------------------------------------------
# The projector cooldown and the Batocera halt/relay logic run in interlocks.py
# so a reload of this file can't kill them. These wrappers call its services and
# never raise: if interlocks.py isn't loaded, nothing cuts mains (the safe side).
def is_batocera_on():
    """Determines if the Batocera x86 laptop client is powered on or active."""
    # batocera_state keeps its last value after power-off (seen 2026-10-31), so it only
    # counts when the relay isn't confirmed off (e.g. the plug dropped off Zigbee).
    relay = safe_state_get(BATOCERA_SWITCH)
    return (
        relay == "on"
        or (relay != "off" and safe_state_get(BATOCERA_STATE) in ["playing", "idle"])
        or safe_float(safe_state_get(BATOCERA_CURRENT), 0.0) >= 0.05
    )


def shutdown_batocera():
    """Ask interlocks.py for a clean Batocera shutdown. Logs instead of raising if that
    file isn't loaded."""
    try:
        pyscript.shutdown_batocera()
    except Exception as e:
        log.warning(f"[Theater] pyscript.shutdown_batocera failed (interlocks.py loaded?): {e}")


def cancel_projector_cooldown():
    """Ask interlocks.py to stop a running projector cooldown, because a new session is
    starting."""
    try:
        pyscript.cancel_projector_cooldown()
    except Exception as e:
        log.warning(f"[Theater] pyscript.cancel_projector_cooldown failed: {e}")


@state_trigger(f"float({BATOCERA_CURRENT}) < 0.05", state_hold=12)
def reset_boxart_on_batocera_halt():
    """Same trigger as interlocks.batocera_auto_power_off (which opens the relay); this only resets the art."""
    if is_booting():
        return
    reset_boxart_idle(source="idle", boxart_state="off")


def _gaming_on_hdmi2(mode=None):
    """Batocera is the source right now. Uses the receiver input and Batocera's relay,
    not sensor.batocera_state, which can stay 'idle' after Batocera powers off."""
    mode = mode if mode is not None else safe_state_get(THEATER_MODE)
    return (
        mode == "game"
        or safe_state_getattr(RECEIVER, "source") in ["HDMI2", "HDMI3"]
        or safe_state_get(BATOCERA_SWITCH) == "on"
    )


PROJECTOR_STANDBY_WAIT_S = 24
PROJECTOR_LIT_AMPS = 0.5


def _wait_projector_dark(timeout_s):
    """Poll the projector current until the lamp is out. True once dark.
    Returns True right away if the sensor is unavailable, so session end never hangs on it
    (the stray-wake guard still covers a lamp left lit)."""
    waited = 0
    while True:
        amps = safe_float(safe_state_get(PROJECTOR_CURRENT), -1.0)
        if amps < PROJECTOR_LIT_AMPS:
            return True
        if waited >= timeout_s:
            return False
        task.sleep(2)
        waited += 2


# Sleep the Onn with the SLEEP key only. media_player.turn_off sends POWER, a toggle,
# whenever HA still thinks the Onn is on, so right after SLEEP it woke the Onn back up
# (dark, receiver off) and the remote's power button then turned it off (2026-11-01).


def _cec_standby_burst(rounds=2, drop_receiver=True):
    """Up to `rounds` tries: SLEEP the Onn (it sends CEC standby to the projector) if it's on,
    then move the receiver to AUDIO1 and turn it off. Stops once the lamp draws under 0.5 A.
    Never wakes an Onn that is already off, since a wake could light the projector again."""
    for _ in range(rounds):
        if safe_state_get(ONN_PRO) == "on":
            safe_service(remote.send_command, entity_id=ONN_REMOTE, command="SLEEP")
            task.sleep(1.0)
        if drop_receiver and safe_state_get(RECEIVER) == "on":
            safe_service(media_player.select_source, entity_id=RECEIVER, source="AUDIO1")
            task.sleep(0.5)
            safe_service(media_player.turn_off, entity_id=RECEIVER)
            task.sleep(2.0)
        if safe_float(safe_state_get(PROJECTOR_CURRENT), 99.0) < 0.5:
            return True
    return False


# ------------------------------------------------------------------------------
# STARTING SESSIONS: movie, game, PC game, music
# Every play_* service starts with _begin_session(), which stops whatever the
# previous mode left running.
# ------------------------------------------------------------------------------
def _teardown_conflicting_sources(target_mode: str):
    """Stop what the previous mode left running: pause Spotify (unless going to music), shut
    Batocera down (unless going to game), and when leaving sports, send the Onn home to free
    the HDHomeRun tuner and drop the Social Mode that game day turned on."""
    # 1. If transitioning away from music, ensure Spotify Connect is paused
    if target_mode != "music":
        pause_spotify_if_playing()

    # 2. If transitioning away from game, initiate Batocera safe shutdown if active
    if target_mode != "game":
        if is_batocera_on():
            shutdown_batocera()

    # 3. If transitioning away from sports, return to home launcher to release HDHomeRun tuner lock
    if target_mode != "sports":
        cur_app = get_active_app_id()
        if cur_app in SPORTS_APPS or safe_state_get(THEATER_MODE) == "sports":
            safe_service(remote.send_command, entity_id=ONN_REMOTE, command="HOME")

    # 4. If target is not sports, drop the Social Mode that game day engaged
    if target_mode != "sports":
        release_sports_social_mode()


def release_sports_social_mode():
    """Returns to Daily Driver only if Social was engaged by sports; a manual Social survives."""
    if safe_state_get(LIGHTING_MODE_SELECT) == MODE_SOCIAL and safe_state_get(SOCIAL_SOURCE) == "sports":
        state.set(SOCIAL_SOURCE, value="none")
        safe_service(input_select.select_option, entity_id=LIGHTING_MODE_SELECT, option=MODE_DAILY)


def end_social_mode():
    """Session end always returns the basement to Daily Driver."""
    state.set(SOCIAL_SOURCE, value="none")
    if safe_state_get(LIGHTING_MODE_SELECT) == MODE_SOCIAL:
        safe_service(input_select.select_option, entity_id=LIGHTING_MODE_SELECT, option=MODE_DAILY)


_session_seq = 0


def _begin_session(target_mode, cancel_cooldown=True):
    """Common start of every play_* service: end curtain call, stop a running projector
    cooldown (play_music keeps it so a cold projector still gets its mains cut), and
    tear down whatever the previous mode left running."""
    global _session_seq
    _session_seq += 1  # cancels a running HDMI2 guard
    state.set(CURTAIN_CALL, value="off")
    if cancel_cooldown:
        cancel_projector_cooldown()
    _teardown_conflicting_sources(target_mode)


def _mark_session_active(mode):
    """Record that a session in this mode is running: theater mode, in-use flag and the
    dashboard picker."""
    state.set(THEATER_MODE, value=mode)
    state.set(THEATER_IN_USE, value="on")
    sync_theater_select(mode)


def _wake_hdmi1_chain():
    """Receiver on HDMI1, wake the Onn, then the projector (which owns its mains)."""
    media_player.turn_on(entity_id=RECEIVER)
    media_player.select_source(entity_id=RECEIVER, source="HDMI1")
    media_player.turn_on(entity_id=ONN_PRO)
    task.sleep(1.0)
    _wake_projector()


# The projector's CEC wake doesn't work from its Eco standby (2026-11-01: One Touch
# Play times out, the lamp stays dark). Direct Power On is enabled, though: it starts
# within ~2s of mains coming on (seen 2026-10-28 and 10-31). So a cold projector is
# woken by cycling its relay. A warm lamp's mains are never cut; the wake waits for
# it to finish cooling first. play_music never calls this.
PROJECTOR_COLD_AMPS = 0.06
PROJECTOR_MAINS_OFF_S = 3
PROJECTOR_WAKE_CHECK_S = 30
PROJECTOR_WAKE_CHECKS = 6  # up to 3 min for a projector that is still cooling


def _projector_lit():
    """True while the lamp draws at least PROJECTOR_LIT_AMPS."""
    return safe_float(safe_state_get(PROJECTOR_CURRENT), 0.0) >= PROJECTOR_LIT_AMPS


def _projector_confirmed_cold():
    """Two cold reads 1s apart, like the cooldown. An unavailable sensor is never cold."""
    for i in range(2):
        amps = safe_float(safe_state_get(PROJECTOR_CURRENT), default=None)
        if amps is None or amps > PROJECTOR_COLD_AMPS:
            return False
        if i == 0:
            task.sleep(1.0)
    return True


def _wake_session_ok(session):
    """True if this projector wake still belongs to the current session, and that
    session isn't music or off."""
    return (session == _session_seq and safe_state_get(THEATER_IN_USE) == "on"
            and safe_state_get(THEATER_MODE) not in ["music", "off"])


def _cycle_projector_mains(session):
    """Mains off, 3s, on. Leaves mains off if the session ended or went to music meanwhile."""
    log.info("[Theater] Projector cold in standby. Cycling its mains to start it.")
    switch.turn_off(entity_id=PROJECTOR_SWITCH)
    task.sleep(PROJECTOR_MAINS_OFF_S)
    if not _wake_session_ok(session):
        return False
    switch.turn_on(entity_id=PROJECTOR_SWITCH)
    return True


def _wake_projector():
    """Start the projector for every mode except music. Runs in the background."""
    task.create(_projector_wake_task, _session_seq)


def _projector_wake_task(session):
    """Background part of _wake_projector. Mains off: turn them on (Direct Power On
    starts the projector). Mains on and lamp cold: cycle the mains. Lamp still
    cooling: check every PROJECTOR_WAKE_CHECK_S, and cycle once it's cold. Gives up
    if the session changes."""
    if _projector_lit():
        return
    if safe_state_get(PROJECTOR_SWITCH) != "on":
        switch.turn_on(entity_id=PROJECTOR_SWITCH)  # Direct Power On
        cycled = True
    elif _projector_confirmed_cold():
        if not _wake_session_ok(session):
            return
        cycled = _cycle_projector_mains(session)
        if not cycled:
            return
    else:
        cycled = False  # still cooling from the last session; wait for it below

    for _ in range(PROJECTOR_WAKE_CHECKS):
        task.sleep(PROJECTOR_WAKE_CHECK_S)
        if not _wake_session_ok(session) or _projector_lit():
            return
        if not is_projector_cold():
            if cycled:
                return  # warming up
            continue  # still cooling
        if cycled:
            log.warning("[Theater] Projector didn't start after its mains came on.")
            return
        if _projector_confirmed_cold() and _wake_session_ok(session):
            cycled = _cycle_projector_mains(session)
            if not cycled:
                return
    if not cycled:
        log.warning("[Theater] Projector never cooled enough to restart.")


POWER_WAKE_SETTLE_S = 2
STREMIO_DEFER_S = 1.5


@state_trigger(f"{ONN_PRO} == 'on'")
def onn_power_button_wake(old_value=None):
    """The Onn remote's power button works like the movie button. CEC wakes the Onn
    and sometimes the projector, but never the receiver, so HA runs play_movie.
    App buttons also wake the Onn; their webhook starts its own mode within about
    0.5s, well inside the settle time, so this backs off. Needs someone in the theater, because
    scrcpy, casting and updates wake the Onn too."""
    if is_booting() or old_value not in ["off", "standby"]:
        return
    task.unique("onn_power_button_wake")
    task.sleep(POWER_WAKE_SETTLE_S)
    if safe_state_get(ONN_PRO) != "on" or _session_ending:
        return  # session end wakes the Onn itself to resend standby
    if safe_state_get(THEATER_IN_USE) == "on" or safe_state_get(RECEIVER) == "on":
        return  # a mode is already starting or running
    if safe_state_get(MMWAVE_PRESENCE) != "on":
        return
    # YouTube's single press isn't caught by Button Mapper: it wakes the Onn and opens
    # YouTube. Keep whatever app is up; open Stremio only from the home screen.
    showing_app = not _is_launcher(get_active_app_id())
    log.info("[Theater] Onn woke from its power button. Starting movie mode.")
    play_movie(open_stremio=False)
    if showing_app:
        return
    session = _session_seq
    task.sleep(STREMIO_DEFER_S)  # an app opened by the wake press shows up by now
    if session == _session_seq and _is_launcher(get_active_app_id()):
        launch_onn_app(STREMIO_APP)
        task.sleep(0.5)
        update_theater_media_art()


@service
def play_movie(open_stremio=True):
    """Movie mode: receiver on HDMI1, Onn and projector on, Stremio opened (unless
    open_stremio is false), Standard sound, announcer 0 dB."""
    _begin_session("movie")
    _mark_session_active("movie")
    release_sports_social_mode()

    # Immediately wipe any stale Spotify art from the marquee
    set_theater_poster(
        MOVIE_FALLBACK_POSTER,
        "Stremio",
        "Ready to Stream • Stremio",
        backdrop_url=MOVIE_FALLBACK_BACKDROP,
        media_type="movie", source="stremio", badge_icon="mdi:movie-open", badge_color="blue",
    )

    _wake_hdmi1_chain()

    if open_stremio:
        launch_onn_app(STREMIO_APP)
    task.sleep(0.5)
    update_theater_media_art()

    set_receiver_sound_mode("Standard")

    safe_service(rest_command.yamaha_set_center_trim, level=0.0)


@service
def play_game():
    """Batocera game mode: Batocera and the receiver on, projector on, receiver on HDMI2
    with Surround Decoder. Keeps the receiver on HDMI2 for 30 s in case CEC pulls it
    back."""
    _begin_session("game")

    switch.turn_on(entity_id=BATOCERA_SWITCH)
    media_player.turn_on(entity_id=RECEIVER)
    task.sleep(2.0)
    _wake_projector()
    media_player.select_source(entity_id=RECEIVER, source="HDMI2")
    set_receiver_sound_mode("Surround Decoder")

    safe_service(rest_command.yamaha_set_center_trim, level=0.0)

    _mark_session_active("game")
    release_sports_social_mode()
    task.create(_hold_receiver_on_hdmi2, _session_seq)


HDMI2_GUARD_SECONDS = 30
HDMI2_GUARD_STEP = 3


def _hold_receiver_on_hdmi2(session):
    """A remote press also wakes the Onn, and about 8s later CEC pulls the receiver
    back to HDMI1. Keep putting it back on HDMI2 for a while. Starting any other
    mode cancels this (_begin_session), and it stops if the session ends."""
    for _ in range(HDMI2_GUARD_SECONDS // HDMI2_GUARD_STEP):
        task.sleep(HDMI2_GUARD_STEP)
        if session != _session_seq or safe_state_get(RECEIVER) != "on" or safe_state_get(BATOCERA_SWITCH) != "on":
            return
        if safe_state_getattr(RECEIVER, "source") != "HDMI2":
            log.info("[Theater Game] Receiver left HDMI2, switching back")
            media_player.select_source(entity_id=RECEIVER, source="HDMI2")


@service
def play_pc_game(app="moonlight", target="batocera"):
    """PC game mode: turn the gaming PC on, then play it through Moonlight on Batocera
    (receiver HDMI2; target="batocera", the default, or "auto" when Batocera is already on),
    or on the Onn (HDMI1) for any other target. Surround Decoder sound."""
    _begin_session("game")

    switch.turn_on(entity_id=PC_SWITCH)
    media_player.turn_on(entity_id=RECEIVER)
    task.sleep(2.0)
    _wake_projector()

    target_clean = str(target).lower().strip()
    # Route to Batocera (HDMI2) if explicitly targeted or if Batocera is already on
    if target_clean == "batocera" or (target_clean == "auto" and safe_state_get(BATOCERA_SWITCH) == "on"):
        switch.turn_on(entity_id=BATOCERA_SWITCH)
        media_player.select_source(entity_id=RECEIVER, source="HDMI2")
        # Moonlight client on Batocera: Surround Decoder handles stereo (matrixed) or native 5.1
        set_receiver_sound_mode("Surround Decoder")
    else:
        # Moonlight streams from Onn 4K Pro over HDMI1 with Surround Decoder soundstage (native 5.1 or matrixed stereo)
        media_player.select_source(entity_id=RECEIVER, source="HDMI1")
        set_receiver_sound_mode("Surround Decoder")
        # Wake Onn and launch Moonlight app
        launch_onn_app(MOONLIGHT_APP)

    safe_service(rest_command.yamaha_set_center_trim, level=0.0)

    _mark_session_active("game")
    release_sports_social_mode()
    update_game_poster()


@service
def play_music():
    """Projector off: keep it off; music comes from the phone to the AVR.
    Projector on: open Spotify on the Onn and leave the projector alone."""
    _begin_session("music", cancel_cooldown=False)
    _mark_session_active("music")

    projector_cold = is_projector_cold()
    if projector_cold:
        # Cut mains before anything wakes over HDMI, so CEC can't strike the lamp
        switch.turn_off(entity_id=PROJECTOR_SWITCH)
        task.sleep(0.5)

    media_player.turn_on(entity_id=RECEIVER)
    media_player.select_source(entity_id=RECEIVER, source="HDMI1")
    set_receiver_sound_mode("7ch Stereo")
    safe_service(rest_command.yamaha_set_center_trim, level=0.0)

    if not projector_cold and get_active_app_id() not in MUSIC_APPS:
        media_player.turn_on(entity_id=ONN_PRO)
        task.sleep(1.0)
        launch_onn_app(SPOTIFY_TV_APP)

    update_theater_media_art()


@service
def theater_play_spotify_playlist(uri="spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"):
    """Music mode, then play a Spotify playlist (uri) on the whole-house Spotify player."""
    play_music()
    task.sleep(1.0)
    try:
        media_player.play_media(
            entity_id=SPOTIFY_PLAYER,
            media_content_id=uri,
            media_content_type="playlist",
        )
    except Exception as e:
        log.warning(f"Spotify playlist start failed: {e}")


# ------------------------------------------------------------------------------
# HDHOMERUN TUNER CONTROL
# The FLEX DUO has no HTTP endpoint for releasing a tuner; it only takes
# control commands over its TCP protocol on port 65001 (what hdhomerun_config uses).
# ------------------------------------------------------------------------------
HDHOMERUN_HOST = "192.168.1.221"
TUNER_IDLE_STATES = ["idle", "off", "unavailable", "unknown", "none", ""]


@pyscript_compile
def _hdhr_control(host, name, value=None, timeout=3.0):
    """Blocking get/set over the HDHomeRun control protocol. Returns the reply value, or None on error."""
    import socket
    import struct
    import zlib

    def tag(t, data):
        n = len(data)
        ln = bytes([n]) if n < 128 else bytes([(n & 0x7F) | 0x80, n >> 7])
        return bytes([t]) + ln + data

    payload = tag(0x03, name.encode() + b"\0")
    if value is not None:
        payload += tag(0x04, value.encode() + b"\0")
    pkt = struct.pack(">HH", 0x0004, len(payload)) + payload
    pkt += struct.pack("<I", zlib.crc32(pkt) & 0xFFFFFFFF)
    try:
        with socket.create_connection((host, 65001), timeout=timeout) as sock:
            sock.sendall(pkt)
            resp = sock.recv(4096)
        plen = struct.unpack(">H", resp[2:4])[0]
        body, i, out = resp[4:4 + plen], 0, {}
        while i < len(body):
            t, n = body[i], body[i + 1]
            i += 2
            if n & 0x80:
                n = (n & 0x7F) | (body[i] << 7)
                i += 1
            out[t] = body[i:i + n].rstrip(b"\0").decode(errors="replace")
            i += n
        if 0x05 in out:  # error message tag
            return None
        return out.get(0x04)
    except Exception:
        return None


def _release_hdhomerun_tuner(tuner):
    """Force-releases a tuner (drops whatever stream holds it). Returns True if the device accepted it."""
    t = str(tuner)
    task.executor(_hdhr_control, HDHOMERUN_HOST, f"/tuner{t}/lockkey", "force")
    return task.executor(_hdhr_control, HDHOMERUN_HOST, f"/tuner{t}/channel", "none") is not None


@service
def preempt_tuner_for_theater(target_tuner="1"):
    """Evicts the remote Tailscale/xTeVe stream on a tuner so the basement Onn can lock it."""
    ok = _release_hdhomerun_tuner(target_tuner)
    if ok:
        msg = f"🏈 Theater Priority Preemption: Evicted remote stream on Tuner {target_tuner} for the basement broadcast."
        log.info(msg)
    else:
        msg = f"⚠️ Theater Preemption failed: HDHomeRun did not release Tuner {target_tuner}. Basement live TV may not get a tuner."
        log.error(msg)
    try:
        notify.ntfy(
            title="HDHomeRun Stream Preemption",
            message=msg,
            data={"priority": "high", "tags": ["football", "tv", "warning"]}
        )
    except Exception:
        pass

    task.sleep(0.6)
    return ok


def ensure_hdhomerun_tuner_available():
    """Interlock 5: if both HDHomeRun tuners are busy, free tuner 1 for the theater by
    dropping the remote (xTeVe) stream on it. Returns True when a tuner is free."""
    t0 = (safe_state_get("sensor.tuner0") or "idle").lower().strip()
    t1 = (safe_state_get("sensor.tuner1") or "idle").lower().strip()
    if t0 not in TUNER_IDLE_STATES and t1 not in TUNER_IDLE_STATES:
        log.warning("HDHomeRun Contention: Both tuners busy. Preempting remote stream on Tuner 1 for basement theater.")
        return preempt_tuner_for_theater(target_tuner="1")
    return True


# ------------------------------------------------------------------------------
# SPORTS, CURTAIN CALL AND MANUAL SERVICES
# ------------------------------------------------------------------------------
@service
def play_sports(app=None):
    """Sports mode. Default source is HDHomeRun; pass app="prime" to watch sports on Prime Video instead."""
    _begin_session("sports")

    use_prime = str(app or "").lower().strip() in ("prime", "prime_video", "amazon")
    source_label = "Prime Video" if use_prime else "HDHomeRun"

    _mark_session_active("sports")

    # Set the scoreboard right away so stale Spotify art is wiped
    _set_sports_poster(source_label)

    _wake_hdmi1_chain()

    if not use_prime:
        # Guarantee an ATSC tuner is unblocked before launching broadcast app
        ensure_hdhomerun_tuner_available()

    apply_sports_audio_mode()
    launch_onn_app(PRIME_VIDEO_PACKAGE if use_prime else HDHOMERUN_APP)
    task.sleep(0.5)
    update_theater_media_art()

    if safe_state_get(LIGHTING_MODE_SELECT) != MODE_SOCIAL:
        state.set(SOCIAL_SOURCE, value="sports")
        input_select.select_option(entity_id=LIGHTING_MODE_SELECT, option=MODE_SOCIAL)


_session_ending = False


@service
def session_end_house_lights():
    """Curtain call. _session_ending is true only while this runs; CURTAIN_CALL
    stays on afterwards for the house-lights window."""
    global _session_ending
    _session_ending = True
    try:
        _session_end_sequence()
    finally:
        _session_ending = False


def _session_end_sequence():
    """The steps of curtain call, in order. AGENTS.md (interlock 3) lists them too; keep
    both in step."""
    global _session_seq
    _session_seq += 1  # stop the HDMI2 guard so it can't undo the AUDIO1 switch
    state.set(CURTAIN_CALL, value="on")

    # 1. Restore house lights first so the room isn't dark while the CEC burst runs
    safe_service(switch.turn_on, entity_id=ADAPTIVE_SWITCH)

    # 2. Clean up conflicting sources / background media
    _teardown_conflicting_sources("off")

    # 3. Pause Spotify Connect
    pause_spotify_if_playing()

    # 4. Clean Batocera shutdown if active
    if is_batocera_on():
        shutdown_batocera()

    prior_mode = safe_state_get(THEATER_MODE)
    rx_source = safe_state_getattr(RECEIVER, "source")
    is_gaming = (prior_mode == "game") or (rx_source in ["HDMI2", "HDMI3"]) or is_batocera_on()

    # 5. Isolate video and manage Onn without triggering HDMI passthrough wake
    if is_gaming:
        # Never switch to HDMI1 and never send HOME when exiting gaming.
        if safe_state_get(ONN_PRO) == "on":
            safe_service(remote.send_command, entity_id=ONN_REMOTE, command="SLEEP")
    else:
        # Non-gaming: release foreground apps/tuner only if Onn is currently on
        if safe_state_get(ONN_PRO) == "on":
            safe_service(remote.send_command, entity_id=ONN_REMOTE, command="HOME")
            task.sleep(0.5)
            safe_service(remote.send_command, entity_id=ONN_REMOTE, command="SLEEP")

    # 5b. Keep the receiver up until the projector acts on the Onn's CEC standby.
    # The projector takes ~15s; dropping the receiver sooner breaks the CEC path
    # (2026-10-31: receiver off 2s after SLEEP left the lamp lit).
    if not _wait_projector_dark(PROJECTOR_STANDBY_WAIT_S) and not _gaming_on_hdmi2(prior_mode):
        # One retry: wake the Onn (the receiver is still on HDMI1) and sleep it again.
        # Skipped when gaming so the Onn never grabs HDMI1 there.
        if safe_state_get(RECEIVER) == "on":
            log.warning("[Theater] Projector still lit after CEC standby. Waking the Onn to resend it.")
            safe_service(media_player.turn_on, entity_id=ONN_PRO)
            task.sleep(10)
            safe_service(remote.send_command, entity_id=ONN_REMOTE, command="SLEEP")
            _wait_projector_dark(PROJECTOR_STANDBY_WAIT_S)

    # 6. Switch AVR to AUDIO1 to completely cut HDMI pass-through signal before turning off AVR
    if safe_state_get(RECEIVER) == "on":
        safe_service(media_player.select_source, entity_id=RECEIVER, source="AUDIO1")
        task.sleep(0.5)

    _cec_standby_burst(rounds=2, drop_receiver=True)

    safe_service(media_player.turn_off, entity_id=RECEIVER)
    safe_service(media_player.turn_off, entity_id=RECEIVER_ZONE_2)
    safe_service(rest_command.yamaha_set_center_trim, level=0.0)

    state.set(THEATER_MODE, value="off")
    state.set(THEATER_IN_USE, value="off")
    sync_theater_select("off")
    end_social_mode()

    reset_boxart_idle(source="idle", boxart_state="off")
    reset_poster_idle(source="session_end")
    # The projector stays in standby with mains on (2026-10-29). Mains are cut only
    # when the lamp is cold: by play_music(), and briefly by _wake_projector() to start it.
    # interlocks.projector_stray_wake_guard covers a standby that didn't take.


@service
def force_projector_off():
    """Manual: put the projector into standby over CEC (wake the Onn, send SLEEP), then
    turn the receiver off. Never cuts the projector's mains."""
    media_player.turn_on(entity_id=RECEIVER)
    media_player.turn_on(entity_id=ONN_PRO)
    task.sleep(2.0)
    remote.send_command(entity_id=ONN_REMOTE, command="SLEEP")
    task.sleep(2.5)
    media_player.turn_off(entity_id=RECEIVER)
    safe_service(media_player.turn_off, entity_id=RECEIVER_ZONE_2)


@service
def theater_force_reconcile():
    """Manual fix-up: recompute the theater mode, in-use flag, dashboard picker and poster from
    the receiver's current state. Doesn't change any hardware."""
    rx_state = safe_state_get(RECEIVER)
    if rx_state == "on":
        state.set(THEATER_IN_USE, value="on")
        update_theater_mode()
        cur_mode = safe_state_get(THEATER_MODE, "movie")
        sync_theater_select(cur_mode)
        if cur_mode == "game":
            update_game_poster()
        elif cur_mode in ["movie", "music", "sports"]:
            update_theater_media_art()
    else:
        state.set(THEATER_IN_USE, value="off")
        state.set(THEATER_MODE, value="off")
        sync_theater_select("off")
        reset_poster_idle(source="reconcile")
        reset_boxart_idle(source="reconcile", boxart_state="off")


@service
def launch_app(app=None):
    """Start a mode or open an app by short name: stremio/movie, hdhomerun/sports/tv,
    prime_sports, spotify/music, batocera/game, moonlight/pc/steam, youtube, netflix, prime.
    Anything else is treated as an Android package name and opened on the Onn."""
    if not app:
        return
    app_lower = str(app).lower().strip()
    if app_lower in ["stremio", "movie", "cinema"]:
        play_movie()
    elif app_lower in ["prime_sports", "sports_prime"]:
        play_sports(app="prime")
    elif app_lower in ["hdhomerun", "sports", "tv", "live_tv"]:
        play_sports()
    elif app_lower in ["spotify", "music"]:
        play_music()
    elif app_lower in ["batocera", "game", "arcade"]:
        play_game()
    elif app_lower in ["moonlight", "pc", "steam", "bpm"]:
        play_pc_game()
    elif app_lower in ["moonlight_batocera", "batocera_moonlight", "pc_batocera"]:
        play_pc_game(target="batocera")
    elif app_lower in ["youtube"]:
        launch_onn_app(YOUTUBE_TV_APP)
    elif app_lower in ["netflix"]:
        launch_onn_app(NETFLIX_APP)
    elif app_lower in ["prime", "prime_video", "amazon"]:
        launch_onn_app(PRIME_VIDEO_PACKAGE)
    else:
        launch_onn_app(app)


# ------------------------------------------------------------------------------
# MOVIE SEARCH (Stremio deep link)
# ------------------------------------------------------------------------------
def fetch_cinemeta_movie(query):
    """Queries Stremio's Cinemeta catalog to resolve IMDb ID, Title, Year, and artwork."""
    if not query:
        return None
    clean_q = str(query).strip()
    if _is_circuit_open("cinemeta"):
        return None
    # Runs off the event loop via _fetch_json, which also feeds the cinemeta circuit breaker.
    try:
        data = _fetch_json(
            "cinemeta",
            f"https://v3-cinemeta.strem.io/catalog/movie/top/search={urllib.parse.quote(clean_q)}.json",
            timeout=3.5,
        )
    except Exception:
        data = None
    metas = (data or {}).get("metas") or []
    if not metas:
        if data is None:
            log.warning(f"[Theater] Cinemeta query for '{query}' failed or timed out")
        return None
    m = metas[0]
    return {
        "id": m.get("id"),
        "name": m.get("name") or clean_q.title(),
        "year": m.get("year"),
        "poster": m.get("poster"),
        "background": m.get("background") or m.get("poster"),
    }


@service
def search_and_play_movie(query=None):
    """Find a movie and start it in Stremio. Looks the title up in Cinemeta for its IMDb ID
    and poster, starts movie mode (receiver on HDMI1, Onn and projector on, Standard sound),
    then deep-links Stremio straight to the movie with autoplay, or to a search if there was
    no match. With no query it reads input_text.theater_movie_search; with neither, it runs
    plain play_movie."""
    search_term = query
    if not search_term or not str(search_term).strip():
        search_term = safe_state_get("input_text.theater_movie_search")

    if not search_term or not str(search_term).strip():
        play_movie()
        return

    clean_term = str(search_term).strip()
    log.info(f"[Theater] Instant Stremio Launch initiated for query: '{clean_term}'")

    # 1. Resolve Cinemeta metadata (IMDb ID, poster, backdrop)
    meta = fetch_cinemeta_movie(clean_term)
    imdb_id = meta.get("id") if meta else None
    movie_title = meta.get("name") if meta else clean_term.title()
    year = meta.get("year") if meta else None
    poster_url = (
        meta.get("poster")
        if meta and meta.get("poster")
        else MOVIE_FALLBACK_POSTER
    )
    backdrop_url = (
        meta.get("background")
        if meta and meta.get("background")
        else MOVIE_FALLBACK_BACKDROP
    )

    # 2. Start movie mode and show the poster right away
    _begin_session("movie")
    _mark_session_active("movie")
    release_sports_social_mode()

    subtitle_str = f"{year} • Stremio AutoPlay" if year else "Stremio AutoPlay"
    set_theater_poster(
        poster_url,
        movie_title,
        subtitle_str,
        backdrop_url=backdrop_url,
        media_type="movie",
        source="stremio",
        badge_icon="mdi:movie-open",
        badge_color="blue",
    )

    # 3. Projector, receiver on HDMI1, Onn awake; then audio
    _wake_hdmi1_chain()
    set_receiver_sound_mode("Standard")
    safe_service(rest_command.yamaha_set_center_trim, level=0.0)

    # 4. Build the Stremio deep link (the movie itself, or a search)
    if imdb_id and str(imdb_id).startswith("tt"):
        deep_link = f"stremio:///detail/movie/{imdb_id}/{imdb_id}?autoPlay=true"
    else:
        encoded_query = urllib.parse.quote(clean_term)
        deep_link = f"stremio:///search?search={encoded_query}"

    log.info(f"[Theater] Sending Stremio deep link: {deep_link}")

    # Send the deep link through the Android TV Remote; ADB only if that integration is down.
    if not _onn_remote_down():
        safe_service(remote.turn_on, entity_id=ONN_REMOTE, activity=deep_link)
    else:
        _onn_adb_command(f'am start -a android.intent.action.VIEW -d "{deep_link}" com.stremio.one')