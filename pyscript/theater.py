# ==============================================================================
# PYSCRIPT MODULE: THEATER AV CONDUCTION, ART & HARDWARE ENGINE
# ==============================================================================
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BOOT_TIMESTAMP = time.time()

try:
    pyscript_compile
except NameError:
    def pyscript_compile(func):
        return func

# Pre-compiled Regex Patterns
RE_ROM_EXT = re.compile(r"\.[a-zA-Z0-9]{2,4}$")
RE_ROM_TAGS = re.compile(r"\(.*?\)|\{.*?\}|\[.*?\]")
RESOLUTION_TAGS = {"4k", "1080p", "720p", "hdr", "uhd", "1080hd", "4kuhd", "60fps", "hd"}

# In-Memory Secrets Cache
_SECRETS_CACHE = {}

# ------------------------------------------------------------------------------
# CORE ENTITIES & CONSTANTS
# ------------------------------------------------------------------------------
RECEIVER = "media_player.theater_receiver"
RECEIVER_ZONE_2 = "media_player.theater_receiver_zone_2"
ONN_PRO = "media_player.onn_pro"
ONN_PRO_2 = "media_player.onn_pro_2"
ONN_REMOTE = "remote.onn_pro"

PROJECTOR_SWITCH = "switch.projector"
PROJECTOR_CURRENT = "sensor.projector_current"
BATOCERA_SWITCH = "switch.batocera"
BATOCERA_CURRENT = "sensor.batocera_current"
BATOCERA_STATE = "sensor.batocera_state"
BATOCERA_SYSTEM = "sensor.batocera_system"
BATOCERA_GAME = "sensor.batocera_current_game"

# ASUS ROG Gaming PC (HASS.Agent & Moonlight)
PC_SWITCH = "switch.gaming_pc"
PC_ONLINE = "binary_sensor.gaming_pc_online"
PC_ACTIVE_WINDOW = "sensor.desktop_rspn8nu_activewindow"
PC_GPU_TEMP = "sensor.desktop_rspn8nu_gputemperature"
PC_SHUTDOWN_BUTTON = "button.desktop_rspn8nu_shutdown"

THEATER_MODE = "sensor.theater_mode"
THEATER_SELECT = "input_select.basement_theater_mode"
THEATER_IN_USE = "binary_sensor.theater_in_use"
THEATER_POSTER = "sensor.theater_current_poster"
THEATER_BOXART = "sensor.theater_current_boxart"

ANNOUNCER_VOLUME = "input_number.theater_announcer_volume"
ANNOUNCER_PRESET = "input_select.theater_announcer_preset"
SOCIAL_SOURCE = "pyscript.basement_social_source"
MODE_SOCIAL = "Social Mode"
MODE_DAILY = "Daily Driver"
LIGHTING_MODE_SELECT = "input_select.basement_lighting_mode"
CURTAIN_CALL = "pyscript.curtain_call_active"
SPOTIFY_PLAYER = "media_player.whole_house_spotify"

MEDIA_APP_ID = "sensor.mediasession2mqtt_1_application_id"
MEDIA_STATE = "sensor.mediasession2mqtt_1_playback_state"
MEDIA_TITLE = "sensor.mediasession2mqtt_1_media_title"

PRIME_VIDEO_PACKAGE = "com.amazon.amazonvideo.livingroom"

PRIME_VIDEO_APPS = {
    "com.amazon.amazonvideo.livingroom",
    "com.amazon.avod.thirdpartyclient",
    "com.amazon.aiv.eu",
    "com.amazon.primevideo.tv",
    "com.amazon.video",
}

MOVIE_APPS = {
    "com.stremio.one",
    "com.google.android.youtube.tv",
    "com.google.android.youtube",
    "com.netflix.ninja",
    *PRIME_VIDEO_APPS,
}

MUSIC_APPS = {
    "com.spotify.tv.android",
    "com.spotify.music",
}

SPORTS_APPS = {
    "com.silicondust.view",     # HDHomeRun
    "com.armata.televizio",     # Televizio
    "ar.tvplayer.tv",           # TiviMate
    "com.espn.score_center",    # ESPN
    "com.foxsports.videogo",    # Fox Sports
    "com.cbs.app",              # Paramount+ / CBS Sports
}

GAME_APPS = {
    "com.limelight",            # Moonlight Game Streaming
    "com.limelight.android",    # Moonlight Variant
    "com.valvesoftware.steamlink", # Steam Link
}

RETRO_2CH_SYSTEMS = {
    "nes", "snes", "gb", "gba", "gbc", "genesis", "megadrive",
    "mastersystem", "gamegear", "atari2600", "atari7800", "pce",
}

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

APP_BRAND_ART = {
    "prime_video": {
        "title": "Prime Video",
        "subtitle": "▶ Streaming on Prime Video",
        "poster": "https://images.unsplash.com/photo-1574375927938-d5a98e8ffe85?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1200&q=80",
        "badge_icon": "mdi:video",
        "badge_color": "teal",
    },
    "netflix": {
        "title": "Netflix",
        "subtitle": "▶ Streaming on Netflix",
        "poster": "https://images.unsplash.com/photo-1574375927938-d5a98e8ffe85?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1200&q=80",
        "badge_icon": "mdi:netflix",
        "badge_color": "red",
    },
    "stremio": {
        "title": "Stremio",
        "subtitle": "▶ Streaming on Stremio",
        "poster": "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=800&q=80",
        "backdrop": "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1200&q=80",
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
# SAFE STATE / SERVICE / NUMERIC HELPERS
# ------------------------------------------------------------------------------
def safe_state_get(entity_id, default=None):
    try:
        val = state.get(entity_id)
        return val if val is not None else default
    except Exception:
        return default


def safe_state_getattr(entity_id, attr, default=None):
    try:
        attrs = state.getattr(entity_id) or {}
        return attrs.get(attr, default)
    except Exception:
        return default


def safe_service(service_func, **kwargs):
    try:
        service_func(**kwargs)
    except Exception as e:
        name = getattr(service_func, "__name__", str(service_func))
        log.warning(f"[Theater] safe_service failed: {name} {kwargs}: {e}")


def safe_float(value, default=0.0):
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
    if app_id and "/" in app_id:
        return app_id.split("/")[0]
    return app_id


def get_active_app_id():
    """Single source of truth for the foreground app.
    Prefers the Android TV Remote entity (always live); falls back to mediasession2mqtt."""
    app_id = (
        safe_state_getattr(ONN_PRO, "app_id")
        or safe_state_getattr(ONN_PRO, "app_name")
        or safe_state_getattr(ONN_REMOTE, "current_activity")
    )
    if app_id:
        return normalize_app_id(app_id)
    for eid in MEDIA_APP_ENTITIES:
        val = safe_state_get(eid)
        if val and str(val).strip() not in ["unknown", "unavailable", "None", ""]:
            return normalize_app_id(str(val).strip())
    return None


def launch_onn_app(package_name, activity_name=None):
    if not package_name:
        return
    # Map deep links / URI schemes (per Google TV Remote protocol recommendation)
    scheme = None
    if "stremio" in package_name:
        scheme = "stremio://"
    elif "silicondust" in package_name:
        scheme = "hdhomerun://"
    elif "limelight" in package_name or "moonlight" in package_name:
        scheme = "moonlight://"

    # 1. Try deep link / URI scheme
    if scheme:
        safe_service(remote.turn_on, entity_id=ONN_REMOTE, activity=scheme)

    # 2. Standard Home Assistant Android TV Remote integration launch by package
    safe_service(remote.turn_on, entity_id=ONN_REMOTE, activity=package_name)

    # 3. Explicit MainActivity component
    act = activity_name or f"{package_name}/.MainActivity"
    safe_service(remote.turn_on, entity_id=ONN_REMOTE, activity=act)

    # 4. In case ADB integration (androidtv.adb_command) is present
    try:
        service.call(
            "androidtv",
            "adb_command",
            entity_id=ONN_PRO,
            command=f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1",
        )
    except Exception:
        pass
    try:
        service.call(
            "androidtv",
            "adb_command",
            entity_id=ONN_PRO,
            command=f"am start -n {act}",
        )
    except Exception:
        pass



def is_booting(grace_seconds=30) -> bool:
    return (time.time() - BOOT_TIMESTAMP) < grace_seconds


def is_projector_cold() -> bool:
    current = safe_float(safe_state_get(PROJECTOR_CURRENT), default=None)
    if current is not None:
        return current <= 0.06
    return safe_state_get(PROJECTOR_SWITCH) == "off"


# ------------------------------------------------------------------------------
# THEATER POSTER & BOX ART ENGINE
# ------------------------------------------------------------------------------
def set_theater_poster(value, title, subtitle, backdrop_url="", media_type="movie",
                       source="unknown", badge_icon="mdi:movie-open", badge_color="blue",
                       raw_title="", **extra_attrs):
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


def _stream_status_label(play_state, app_label):
    if play_state in ["playing", "on"]:
        return f"▶ Streaming on {app_label}"
    elif play_state == "paused":
        return f"⏸ Paused on {app_label}"
    return f"{app_label} Idle"


SECRET_PATHS = [
    "/config/secrets.yaml",
    "/ha_config/secrets.yaml",
    "secrets.yaml",
]


@pyscript_compile
def _scan_secrets_file(paths, key_name):
    """Blocking file read; runs in an executor thread via task.executor."""
    import os
    for sp in paths:
        if os.path.exists(sp):
            try:
                with open(sp, "r", encoding="utf-8") as f:
                    for line in f:
                        l = line.strip()
                        if l.startswith(key_name + ":"):
                            return l.split(":", 1)[1].strip().strip("\"'")
            except Exception:
                pass
    return None


def _read_secret(key_name):
    if key_name in _SECRETS_CACHE:
        return _SECRETS_CACHE[key_name] or None
    val = task.executor(_scan_secrets_file, SECRET_PATHS, key_name)
    _SECRETS_CACHE[key_name] = val or ""
    return val or None


MEDIA_TITLE_ENTITIES = [
    "sensor.mediasession2mqtt_1_media_title",
    "sensor.mediasession2mqtt_media_title",
    "sensor.mediasession2mqtt_1_title",
    "sensor.mediasession2mqtt_title",
    "sensor.mediasession2mqtt_1_track",
    "sensor.mediasession2mqtt_track",
    "sensor.mediasession2mqtt_2_media_title",
]

MEDIA_ARTIST_ENTITIES = [
    "sensor.mediasession2mqtt_1_media_artist",
    "sensor.mediasession2mqtt_media_artist",
    "sensor.mediasession2mqtt_1_artist",
    "sensor.mediasession2mqtt_artist",
    "sensor.mediasession2mqtt_2_media_artist",
]

MEDIA_STATE_ENTITIES = [
    "sensor.mediasession2mqtt_1_playback_state",
    "sensor.mediasession2mqtt_playback_state",
    "sensor.mediasession2mqtt_2_playback_state",
]

MEDIA_APP_ENTITIES = [
    "sensor.mediasession2mqtt_1_application_id",
    "sensor.mediasession2mqtt_application_id",
    "sensor.mediasession2mqtt_2_application_id",
]


def get_active_media_info():
    title = None
    artist = None
    play_state = None

    for eid in MEDIA_TITLE_ENTITIES:
        val = safe_state_get(eid)
        if val and str(val).strip() not in ["unknown", "unavailable", "None", ""]:
            title = str(val).strip()
            break

    for eid in MEDIA_ARTIST_ENTITIES:
        val = safe_state_get(eid)
        if val and str(val).strip() not in ["unknown", "unavailable", "None", ""]:
            artist = str(val).strip()
            break

    for eid in MEDIA_STATE_ENTITIES:
        st = safe_state_get(eid)
        if st and str(st).strip() not in ["unknown", "unavailable", "None", ""]:
            play_state = str(st).strip()
        if not title:
            val = safe_state_getattr(eid, "media_title") or safe_state_getattr(eid, "title") or safe_state_getattr(eid, "track")
            if val and str(val).strip() not in ["unknown", "unavailable", "None", ""]:
                title = str(val).strip()
        if not artist:
            val = safe_state_getattr(eid, "media_artist") or safe_state_getattr(eid, "artist")
            if val and str(val).strip() not in ["unknown", "unavailable", "None", ""]:
                artist = str(val).strip()
        if title:
            break

    # Foreground app: Android TV Remote entity first, mediasession as fallback
    app_id = get_active_app_id()

    # mediasession2mqtt reports whichever session changed last, not the foreground one.
    # If it disagrees with the live foreground app, ignore its metadata.
    session_app = None
    for eid in MEDIA_APP_ENTITIES:
        val = safe_state_get(eid)
        if val and str(val).strip() not in ["unknown", "unavailable", "None", ""]:
            session_app = normalize_app_id(str(val).strip())
            break
    if app_id and session_app and session_app != app_id:
        title = None
        artist = None
        play_state = None

    if not title:
        for mp in [ONN_PRO, ONN_PRO_2]:
            for attr in ["media_title", "media_series_title", "title"]:
                val = safe_state_getattr(mp, attr)
                if val and str(val).strip() not in ["unknown", "unavailable", "None", ""]:
                    title = str(val).strip()
                    break
            if title:
                break

    if not artist:
        for mp in [ONN_PRO, ONN_PRO_2]:
            for a_attr in ["media_series_title", "media_artist", "artist"]:
                val = safe_state_getattr(mp, a_attr)
                if val and str(val).strip() not in ["unknown", "unavailable", "None", ""]:
                    artist = str(val).strip()
                    break
            if artist:
                break

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


RE_GENERIC_SEASON = re.compile(r"^(?:season|series|episode|ep|s)\s*\d+$", re.IGNORECASE)


def get_search_candidates(raw_title, artist=None):
    candidates = []
    if artist and len(artist) > 1 and artist.lower() not in ["unknown", "none", "stremio", "prime video", "netflix", "youtube"]:
        candidates.append(artist.strip())

    if not raw_title:
        return candidates

    clean = re.sub(r"\.(mkv|mp4|avi|mov|wmv|iso|ts)$", "", raw_title, flags=re.IGNORECASE)
    if "." in clean and " " not in clean:
        clean = clean.replace(".", " ")
    clean = clean.replace("_", " ")
    clean = re.sub(
        r"\b(2160p|1080p|720p|480p|uhd|hdr|hdr10|bluray|bdrip|webrip|web-dl|web|x264|x265|hevc|aac|dts|ac3|remux|h264|h265|proper|repack)\b.*$",
        "",
        clean,
        flags=re.IGNORECASE,
    ).strip()

    # Season/Episode split e.g. "Futurama S01E01 Space Pilot 3000"
    m = re.split(r"\b(?:s\d{1,2}e\d{1,2}|\d{1,2}x\d{1,2})\b", clean, flags=re.IGNORECASE)
    if len(m) > 1:
        show_part = m[0].strip().strip("-–— ")
        ep_part = m[1].strip().strip("-–— ")
        if show_part and show_part not in candidates and not RE_GENERIC_SEASON.match(show_part):
            candidates.append(show_part)
        if ep_part and ep_part not in candidates and not RE_GENERIC_SEASON.match(ep_part):
            candidates.append(ep_part)

    # Hyphen split e.g. Stremio "Episode - Show" or standard "Show - Episode"
    if " - " in clean:
        parts = [p.strip() for p in clean.split(" - ") if p.strip()]
        for p in reversed(parts):
            if p not in candidates and p.lower() not in RESOLUTION_TAGS and not RE_GENERIC_SEASON.match(p):
                candidates.append(p)
        for p in parts:
            if p not in candidates and p.lower() not in RESOLUTION_TAGS and not RE_GENERIC_SEASON.match(p):
                candidates.append(p)

    # Strip year e.g. "Inception 2010" -> "Inception"
    year_clean = re.sub(r"[\(\[]?\b(19\d\d|20\d\d)\b[\)\]]?", "", clean).strip()
    if year_clean and year_clean not in candidates and len(year_clean) > 1:
        candidates.append(year_clean)

    if clean and clean not in candidates:
        candidates.append(clean)
    if raw_title not in candidates:
        candidates.append(raw_title)

    return [c for c in candidates if len(c) > 1 and c.lower() not in ["stremio", "stremio theatrical", "ready to stream", "prime video", "netflix"]]


# ------------------------------------------------------------------------------
# RESILIENT NETWORK LAYER: IN-MEMORY CACHE & CIRCUIT BREAKER
# ------------------------------------------------------------------------------
_ART_CACHE = {}          # key -> (timestamp, data)
_CIRCUIT_STATE = {}      # service_name -> {"failures": int, "tripped_until": float}

CACHE_TTL_HIT = 3600     # 1 hour for successful art lookup
CACHE_TTL_MISS = 300     # 5 minutes negative cache for non-matches
CIRCUIT_MAX_FAILURES = 3 # Trip after 3 consecutive network failures
CIRCUIT_COOLDOWN = 300   # 5-minute recovery backoff


def _is_circuit_open(service_name: str) -> bool:
    cs = _CIRCUIT_STATE.get(service_name)
    if not cs:
        return False
    if time.time() < cs.get("tripped_until", 0):
        return True
    if cs.get("tripped_until", 0) > 0:
        cs["failures"] = 0
        cs["tripped_until"] = 0
    return False


def _record_service_failure(service_name: str):
    cs = _CIRCUIT_STATE.setdefault(service_name, {"failures": 0, "tripped_until": 0})
    cs["failures"] += 1
    if cs["failures"] >= CIRCUIT_MAX_FAILURES:
        cs["tripped_until"] = time.time() + CIRCUIT_COOLDOWN
        try:
            log.warning(f"[Theater Resilience] Circuit breaker tripped for {service_name}! Backing off for {CIRCUIT_COOLDOWN}s.")
        except Exception:
            pass


def _record_service_success(service_name: str):
    cs = _CIRCUIT_STATE.get(service_name)
    if cs:
        cs["failures"] = 0
        cs["tripped_until"] = 0


@service
def theater_resilience_status():
    """Returns current status of network cache and circuit breakers."""
    open_circuits = [s for s, state_dict in _CIRCUIT_STATE.items() if time.time() < state_dict.get("tripped_until", 0)]
    return {
        "cache_entries": len(_ART_CACHE),
        "open_circuits": open_circuits,
        "circuit_states": _CIRCUIT_STATE,
    }


# ------------------------------------------------------------------------------
# ART LOOKUPS
# Normal pyscript functions. Only the blocking HTTP call runs in an executor thread
# (task.executor + a native @pyscript_compile helper that receives everything as arguments).
# ------------------------------------------------------------------------------
@pyscript_compile
def _http_get(url, headers=None, timeout=5, parse_json=True):
    """Blocking GET. Returns (status, data): status is the HTTP code, or -1 on a network error."""
    import json
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if not parse_json:
                return resp.status, None
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return -1, None


def _fetch_json(service_name, url, headers=None, timeout=5):
    """GET JSON with circuit-breaker bookkeeping. A 404 is a miss, not a service failure."""
    hdrs = {"User-Agent": "HomeAssistant-Pyscript/1.0"}
    if headers:
        hdrs.update(headers)
    status, data = task.executor(_http_get, url, hdrs, timeout, True)
    if status == 200:
        _record_service_success(service_name)
        return data
    if status == -1 or status >= 500 or status in (401, 403, 429):
        _record_service_failure(service_name)
    return None


def _movie_or_tv_art_lookup(raw_title, artist=None):
    if not raw_title and not artist:
        return None

    cache_key = f"movie_tv:{raw_title}:{artist}"
    if cache_key in _ART_CACHE:
        cached_ts, cached_data = _ART_CACHE[cache_key]
        ttl = CACHE_TTL_HIT if cached_data else CACHE_TTL_MISS
        if time.time() - cached_ts < ttl:
            return cached_data

    candidates = get_search_candidates(raw_title, artist=artist)
    if not candidates and raw_title:
        candidates = [raw_title]

    # 1. TMDB (needs tmdb_api_key in secrets.yaml)
    api_key = _read_secret("tmdb_api_key")
    if api_key:
        for candidate in candidates:
            if _is_circuit_open("tmdb"):
                break
            encoded = urllib.parse.quote(candidate)
            data = _fetch_json(
                "tmdb",
                f"https://api.themoviedb.org/3/search/multi?api_key={api_key}&query={encoded}",
                timeout=4,
            )
            results = (data or {}).get("results", [])
            if not results:
                continue
            best = None
            for item in results[:5]:
                if item.get("media_type") in ["movie", "tv"] and item.get("poster_path"):
                    best = item
                    break
            if not best:
                best = results[0]
            poster_path = best.get("poster_path")
            backdrop_path = best.get("backdrop_path")
            if poster_path:
                res = {
                    "poster": f"https://image.tmdb.org/t/p/w500{poster_path}",
                    "backdrop": f"https://image.tmdb.org/t/p/w780{backdrop_path}" if backdrop_path else "",
                    "title": best.get("title") or best.get("name") or candidate,
                    "media_type": best.get("media_type", "movie"),
                    "source": "tmdb",
                }
                _ART_CACHE[cache_key] = (time.time(), res)
                return res

    # 2. Cinemeta (Stremio's catalog backend; no API key)
    for pass_mode in ("exact", "fuzzy"):
        for candidate in candidates:
            if _is_circuit_open("cinemeta"):
                break
            encoded = urllib.parse.quote(candidate)
            match_found = None
            for cat in ["series", "movie"]:
                data = _fetch_json(
                    "cinemeta",
                    f"https://v3-cinemeta.strem.io/catalog/{cat}/top/search={encoded}.json",
                    timeout=3,
                )
                for m in (data or {}).get("metas", [])[:4]:
                    m_name = m.get("name", "").strip()
                    if pass_mode == "exact" and m_name.lower() == candidate.lower():
                        match_found = (m, cat)
                        break
                    elif pass_mode == "fuzzy" and (candidate.lower() in m_name.lower() or m_name.lower() in candidate.lower()):
                        match_found = (m, cat)
                        break
                if match_found:
                    break

            if match_found:
                meta, cat = match_found
                poster_url = meta.get("poster")
                bg_url = meta.get("background") or poster_url
                if poster_url:
                    if "_V1_SX250.jpg" in poster_url:
                        poster_url = poster_url.replace("_V1_SX250.jpg", "_V1_SX700.jpg")
                    elif "/small/" in poster_url:
                        poster_url = poster_url.replace("/small/", "/medium/")
                    res = {
                        "poster": poster_url,
                        "backdrop": bg_url,
                        "title": meta.get("name") or candidate,
                        "media_type": meta.get("type", cat),
                        "source": "cinemeta",
                    }
                    _ART_CACHE[cache_key] = (time.time(), res)
                    return res

    # 3. TVMaze (no API key)
    for candidate in candidates:
        if _is_circuit_open("tvmaze"):
            break
        encoded = urllib.parse.quote(candidate)
        data = _fetch_json("tvmaze", f"https://api.tvmaze.com/singlesearch/shows?q={encoded}", timeout=3)
        if data and data.get("image"):
            img = data["image"].get("original") or data["image"].get("medium")
            if img:
                res = {
                    "poster": img,
                    "backdrop": img,
                    "title": data.get("name") or candidate,
                    "media_type": "tv",
                    "source": "tvmaze",
                }
                _ART_CACHE[cache_key] = (time.time(), res)
                return res

    # Don't negative-cache when a service was down: a brief outage would pin the fallback poster.
    had_outage = any([_is_circuit_open(s) for s in ("tmdb", "cinemeta", "tvmaze")])
    if not had_outage:
        _ART_CACHE[cache_key] = (time.time(), None)
    return None


def _fetch_movie_or_tv_art(raw_title, artist=None):
    try:
        return _movie_or_tv_art_lookup(raw_title, artist)
    except Exception as e:
        log.warning(f"[Theater] Movie/TV art lookup failed for {raw_title!r}: {e}")
        return None


def _fetch_tmdb_from_secrets(raw_title, artist=None):
    """Compatibility alias for tests and direct callers."""
    return _fetch_movie_or_tv_art(raw_title, artist=artist)


def _fetch_sgdb_asset(url, api_key):
    data = _fetch_json("steamgriddb", url, {"Authorization": f"Bearer {api_key}"}, 5)
    items = (data or {}).get("data") or []
    return items[0].get("url") if items else None


LIBRETRO_SYSTEM_REPOS = {
    "n64": "Nintendo_-_Nintendo_64",
    "psx": "Sony_-_PlayStation",
    "ps1": "Sony_-_PlayStation",
    "playstation": "Sony_-_PlayStation",
    "ps2": "Sony_-_PlayStation_2",
    "dreamcast": "Sega_-_Dreamcast",
    "genesis": "Sega_-_Mega_Drive_-_Genesis",
    "megadrive": "Sega_-_Mega_Drive_-_Genesis",
    "snes": "Nintendo_-_Super_Nintendo_Entertainment_System",
    "nes": "Nintendo_-_Nintendo_Entertainment_System",
    "gba": "Nintendo_-_Game_Boy_Advance",
    "gbc": "Nintendo_-_Game_Boy_Color",
    "gb": "Nintendo_-_Game_Boy",
    "gamecube": "Nintendo_-_GameCube",
    "gc": "Nintendo_-_GameCube",
    "wii": "Nintendo_-_Wii",
    "saturn": "Sega_-_Saturn",
    "psp": "Sony_-_PlayStation_Portable",
    "arcade": "FBNeo_-_Arcade_Games",
    "mame": "MAME",
}


def _fetch_libretro_game_art(clean_title, system_id=None):
    if not clean_title or not system_id:
        return None
    repo = LIBRETRO_SYSTEM_REPOS.get(str(system_id).lower())
    if not repo:
        return None

    variations = [
        clean_title,
        f"{clean_title} (USA)",
        f"{clean_title} (USA, Europe)",
        f"{clean_title} (Europe)",
        f"{clean_title} (World)",
    ]
    for v in variations:
        if _is_circuit_open("libretro"):
            return None
        encoded = urllib.parse.quote(v)
        box_url = f"https://raw.githubusercontent.com/libretro-thumbnails/{repo}/master/Named_Boxarts/{encoded}.png"
        snap_url = f"https://raw.githubusercontent.com/libretro-thumbnails/{repo}/master/Named_Snaps/{encoded}.png"
        status, _ = task.executor(_http_get, box_url, {"User-Agent": "HomeAssistant-Pyscript/1.0"}, 3, False)
        if status == 200:
            _record_service_success("libretro")
            return {
                "poster": box_url,
                "backdrop": snap_url,
                "title": clean_title,
                "source": "libretro",
            }
        # 404 = this naming variant doesn't exist (a miss); only real network/server errors count as failures
        if status == -1 or status >= 500:
            _record_service_failure("libretro")
    return None


def _game_art_lookup(game_title, system_id=None):
    clean_title = RE_ROM_EXT.sub("", game_title)
    clean_title = RE_ROM_TAGS.sub("", clean_title).strip()
    # Steam shortcuts arrive as "1794680_Vampire_Survivors": drop the app id, underscores -> spaces
    clean_title = re.sub(r"^\d+_", "", clean_title).replace("_", " ").strip()
    if not clean_title:
        return None

    cache_key = f"game:{clean_title}:{system_id}"
    if cache_key in _ART_CACHE:
        cached_ts, cached_data = _ART_CACHE[cache_key]
        ttl = CACHE_TTL_HIT if cached_data else CACHE_TTL_MISS
        if time.time() - cached_ts < ttl:
            return cached_data

    steamgriddb_key = _read_secret("steamgriddb_api_key")
    rawg_key = _read_secret("rawg_api_key")

    if steamgriddb_key and not _is_circuit_open("steamgriddb"):
        encoded = urllib.parse.quote(clean_title)
        data = _fetch_json(
            "steamgriddb",
            f"https://www.steamgriddb.com/api/v2/search/autocomplete/{encoded}",
            {"Authorization": f"Bearer {steamgriddb_key}"},
            5,
        )
        results = (data or {}).get("data") or []
        if results:
            game_id = results[0].get("id")
            game_name = results[0].get("name") or clean_title
            grid_url = _fetch_sgdb_asset(
                f"https://www.steamgriddb.com/api/v2/grids/game/{game_id}?dimensions=600x900",
                steamgriddb_key,
            )
            hero_url = _fetch_sgdb_asset(
                f"https://www.steamgriddb.com/api/v2/heroes/game/{game_id}",
                steamgriddb_key,
            )
            if grid_url or hero_url:
                res = {
                    "poster": grid_url or hero_url,
                    "backdrop": hero_url or grid_url,
                    "title": game_name,
                    "source": "steamgriddb",
                }
                _ART_CACHE[cache_key] = (time.time(), res)
                return res

    if rawg_key and not _is_circuit_open("rawg"):
        encoded = urllib.parse.quote(clean_title)
        data = _fetch_json(
            "rawg",
            f"https://api.rawg.io/api/games?key={rawg_key}&search={encoded}&page_size=1",
            timeout=5,
        )
        results = (data or {}).get("results") or []
        if results and results[0].get("background_image"):
            img = results[0].get("background_image")
            res = {
                "poster": img,
                "backdrop": img,
                "title": results[0].get("name") or clean_title,
                "source": "rawg",
            }
            _ART_CACHE[cache_key] = (time.time(), res)
            return res

    # Libretro boxart fallback (no API key)
    libretro_match = _fetch_libretro_game_art(clean_title, system_id)
    if libretro_match:
        _ART_CACHE[cache_key] = (time.time(), libretro_match)
        return libretro_match

    _ART_CACHE[cache_key] = (time.time(), None)
    return None


def _fetch_game_art_from_secrets(game_title, system_id=None):
    try:
        return _game_art_lookup(game_title, system_id)
    except Exception as e:
        log.warning(f"[Theater] Game art lookup failed for {game_title!r} ({system_id}): {e}")
        return None


# Plain function (no trigger): called directly by the play_* services and by the
# debounced trigger wrapper below.
def update_theater_media_art():
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
        opp_name = safe_state_getattr("sensor.philadelphia_eagles", "opponent_name")
        opp_abbr = safe_state_getattr("sensor.philadelphia_eagles", "opponent_abbr") or opp_name or "OPP"
        team_abbr = safe_state_getattr("sensor.philadelphia_eagles", "team_abbr") or "PHI"
        team_score = safe_state_getattr("sensor.philadelphia_eagles", "team_score")
        opp_score = safe_state_getattr("sensor.philadelphia_eagles", "opponent_score")
        quarter = safe_state_getattr("sensor.philadelphia_eagles", "quarter")
        clock = safe_state_getattr("sensor.philadelphia_eagles", "clock")
        down_dist = safe_state_getattr("sensor.philadelphia_eagles", "down_distance_text")
        last_play = safe_state_getattr("sensor.philadelphia_eagles", "last_play")
        possession = safe_state_getattr("sensor.philadelphia_eagles", "possession")
        team_logo = safe_state_getattr("sensor.philadelphia_eagles", "team_logo") or "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png"
        opp_logo = safe_state_getattr("sensor.philadelphia_eagles", "opponent_logo")
        game_state = safe_state_get("sensor.philadelphia_eagles")
        trim = safe_state_get(ANNOUNCER_VOLUME) or "0.0"
        sports_backdrop = "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=1200&q=80"

        # Construct live stats & scoreboard title
        if game_state == "IN" and team_score is not None and opp_score is not None:
            sports_title = f"{team_abbr} {team_score} - {opp_score} {opp_abbr}"
            sub_parts = []
            if quarter and clock:
                sub_parts.append(f"Q{quarter} {clock}")
            if down_dist:
                sub_parts.append(down_dist)
            sub_parts.append(f"Booth Trim: {trim} dB")
            sports_subtitle = " • ".join(sub_parts)
        elif game_state == "POST" and team_score is not None and opp_score is not None:
            sports_title = f"FINAL: {team_abbr} {team_score} - {opp_score} {opp_abbr}"
            sports_subtitle = f"Final Score • Stadium Surround • Booth Trim: {trim} dB"
        else:
            sports_title = f"Eagles vs {opp_name}" if opp_name else "Live Sports Broadcast"
            sports_subtitle = f"Stadium Surround • Booth Trim: {trim} dB"

        set_theater_poster(
            team_logo, sports_title, sports_subtitle,
            backdrop_url=sports_backdrop, media_type="sports",
            source="sports", badge_icon="mdi:football", badge_color="green",
            team_logo=team_logo,
            opponent_logo=opp_logo,
            team_score=team_score,
            opponent_score=opp_score,
            team_abbr=team_abbr,
            opponent_abbr=opp_abbr,
            quarter=quarter,
            clock=clock,
            down_distance_text=down_dist,
            last_play=last_play,
            possession=possession,
            game_state=game_state,
        )
        return

    # In movie mode, ignore any lingering background Spotify sessions
    if mode == "movie":
        if app_id in ["com.spotify.tv.android", "com.spotify.music"]:
            app_id = "com.stremio.one"
            raw_title = None
            artist = None
            onn_art = None

    if mode == "music" or app_id in ["com.spotify.tv.android", "com.spotify.music"]:
        album_art = (
            onn_art
            or safe_state_getattr("media_player.whole_house_spotify", "entity_picture")
            or "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=800&q=80"
        )
        music_title = (
            raw_title
            or safe_state_getattr("media_player.whole_house_spotify", "media_title")
            or "Spotify Music"
        )
        artist_val = artist or safe_state_getattr("media_player.whole_house_spotify", "media_artist") or "Spotify"
        album = safe_state_getattr("media_player.whole_house_spotify", "media_album_name") or "Hi-Fi Audio"
        set_theater_poster(
            album_art, music_title, f"{artist_val} • {album}",
            backdrop_url=album_art, media_type="music",
            source="spotify", badge_icon="mdi:spotify", badge_color="green",
        )
        return

    if app_id in ["com.google.android.youtube.tv", "com.google.android.youtube"]:
        yt_art = onn_art or "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=800&q=80"
        set_theater_poster(
            yt_art, raw_title or "YouTube", _stream_status_label(play_state, "YouTube"),
            backdrop_url=yt_art, media_type="youtube",
            source="youtube", badge_icon="mdi:youtube", badge_color="red",
        )
        return

    if app_id in PRIME_VIDEO_APPS:
        app_label = "Prime Video"
        badge_icon = "mdi:video"
        badge_color = "teal"
        stream_src = "prime_video"
    elif app_id == "com.netflix.ninja":
        app_label = "Netflix"
        badge_icon = "mdi:netflix"
        badge_color = "red"
        stream_src = "netflix"
    elif app_id == "com.stremio.one" or not app_id:
        app_label = "Stremio"
        badge_icon = "mdi:movie-open"
        badge_color = "blue"
        stream_src = "stremio"
    else:
        app_label = "Theatrical Stream"
        badge_icon = "mdi:movie-open"
        badge_color = "blue"
        stream_src = "theatrical_stream"

    subtitle_val = _stream_status_label(play_state, app_label)

    # 1. Multi-source art resolution (Cinemeta, TMDB, TVMaze)
    data = _fetch_movie_or_tv_art(raw_title, artist=artist) if (raw_title or artist) else None
    if data and isinstance(data, dict) and data.get("poster"):
        set_theater_poster(
            data["poster"], data.get("title") or raw_title or artist, subtitle_val,
            raw_title=raw_title or artist or "", backdrop_url=data.get("backdrop", ""),
            media_type=data.get("media_type", "movie"),
            source=data.get("source", stream_src), badge_icon=badge_icon, badge_color=badge_color,
        )
        return

    # 2. Direct Android TV / Onn MediaSession Cover Art Passthrough
    if onn_art and onn_art not in ["unknown", "unavailable", "None", ""]:
        set_theater_poster(
            onn_art, raw_title or artist or "Now Playing", subtitle_val,
            raw_title=raw_title or artist or "", backdrop_url=onn_art,
            media_type="movie", source="androidtv_stream",
            badge_icon=badge_icon, badge_color=badge_color,
        )
        return

    # 3. If art search didn't yield an image, but we detected a title/artist:
    if raw_title or artist:
        candidates = get_search_candidates(raw_title, artist=artist)
        best_title = artist if (artist and artist not in ["Stremio", "Prime Video", "Netflix", "None"]) else (candidates[0] if candidates else raw_title)
        fallback_poster = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=800&q=80"
        set_theater_poster(
            fallback_poster, best_title,
            subtitle_val,
            raw_title=raw_title or "",
            backdrop_url="https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1200&q=80",
            media_type="movie", source=f"{stream_src}_title_match",
            badge_icon=badge_icon, badge_color=badge_color,
        )
        return

    # 4. Brand & Streaming App fallback (Prime Video, Stremio, Netflix, YouTube)
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
        fallback_poster = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=800&q=80"
        fallback_backdrop = "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1200&q=80"
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
    "sensor.mediasession2mqtt_1_media_title, "
    "sensor.mediasession2mqtt_media_title, "
    "sensor.mediasession2mqtt_1_title, "
    "sensor.mediasession2mqtt_title, "
    "sensor.mediasession2mqtt_1_media_artist, "
    "sensor.mediasession2mqtt_media_artist, "
    "sensor.mediasession2mqtt_1_playback_state, "
    "sensor.mediasession2mqtt_playback_state, "
    "sensor.mediasession2mqtt_1_application_id, "
    "sensor.mediasession2mqtt_application_id, "
    "media_player.onn_pro, "
    "media_player.onn_pro.media_title, "
    "media_player.onn_pro.media_series_title, "
    "media_player.onn_pro.entity_picture, "
    "media_player.onn_pro.app_id, "
    "media_player.onn_pro.app_name, "
    "media_player.onn_pro_2.media_title, "
    "media_player.onn_pro_2.entity_picture, "
    "remote.onn_pro, "
    "remote.onn_pro.current_activity, "
    "input_number.theater_announcer_volume, "
    "sensor.philadelphia_eagles, "
    "sensor.philadelphia_eagles.team_score, "
    "sensor.philadelphia_eagles.opponent_score, "
    "sensor.theater_mode, "
    "binary_sensor.theater_in_use"
)
def on_theater_media_changed():
    # Debounce: a newer trigger cancels this run, so only the last burst event renders.
    task.unique("theater_media_art")
    task.sleep(0.5)
    update_theater_media_art()


# ------------------------------------------------------------------------------
# PC GAMING & ACTIVE WINDOW CONDUCTION (HASS.AGENT & MOONLIGHT)
# ------------------------------------------------------------------------------
PC_SYSTEM_WINDOWS = {
    "desktop", "task switching", "taskbar", "explorer", "start",
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
    Parses sensor.desktop_rspn8nu_activewindow into (game_title, state, is_steam).
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


def is_pc_game_playing():
    """Returns True if a PC game is actively running on the ROG Gaming PC."""
    win = safe_state_get(PC_ACTIVE_WINDOW)
    title, state_val, _ = parse_pc_active_window(win)
    return state_val == "playing"


def is_pc_gaming_active():
    """Returns True if PC is online and running either a game or Steam BPM."""
    win = safe_state_get(PC_ACTIVE_WINDOW)
    title, state_val, is_steam = parse_pc_active_window(win)
    return state_val in ["playing", "idle"]


# Plain function (no trigger): called directly by play_pc_game and by the
# debounced trigger wrapper below.
def update_game_poster():
    if safe_state_get(THEATER_MODE) != "game":
        return

    # Check Batocera
    batocera_title = safe_state_get(BATOCERA_GAME)
    batocera_sys = (safe_state_get(BATOCERA_SYSTEM) or "").lower()
    batocera_st = safe_state_get(BATOCERA_STATE)

    # Check PC Gaming (HASS.Agent sensor.desktop_rspn8nu_activewindow)
    pc_win = safe_state_get(PC_ACTIVE_WINDOW)
    pc_title, pc_st, is_steam = parse_pc_active_window(pc_win)
    gpu_temp = safe_state_get(PC_GPU_TEMP)
    gpu_temp_str = f"{round(float(gpu_temp))}°C" if (gpu_temp and str(gpu_temp).replace('.', '', 1).isdigit()) else ""

    # Conduction Priority:
    # 1. Batocera actively playing a ROM
    # 2. PC actively playing a game
    # 3. Steam Big Picture Mode active
    # 4. Batocera loaded in carousel/menu
    # 5. ASUS ROG PC Online / Ready
    # 6. Default idle arcade
    is_batocera_playing = batocera_st == "playing" and batocera_title and batocera_title not in ["None", "unknown", "unavailable", ""]
    is_pc_playing = pc_st == "playing" and bool(pc_title)

    if is_batocera_playing:
        clean_title = batocera_title
        system_id = batocera_sys
        game_state = "playing"
        sys_name = system_id.upper() if system_id else "RETRO"
        display_title = clean_title
        game_sub = f"🎮 Playing • {sys_name} Gaming"
        data = _fetch_game_art_from_secrets(clean_title, system_id) if clean_title else None
        sys_defaults = SYSTEM_ART_MAP.get(system_id, SYSTEM_ART_MAP["default"])
        badge_icon = "mdi:gamepad-variant"
        badge_color = "green"
    elif is_pc_playing:
        clean_title = pc_title
        system_id = "steam" if is_steam else "pc"
        game_state = "playing"
        sys_name = "STEAM" if is_steam else "PC"
        display_title = clean_title
        temp_suffix = f" (GPU: {gpu_temp_str})" if gpu_temp_str else ""
        game_sub = f"🎮 Playing • ASUS ROG Gaming PC{temp_suffix}"
        data = _fetch_game_art_from_secrets(clean_title, "pc")
        sys_defaults = SYSTEM_ART_MAP.get("pc", SYSTEM_ART_MAP["default"])
        badge_icon = "mdi:steam" if is_steam else "mdi:desktop-tower"
        badge_color = "purple"
    elif pc_st == "idle" and is_steam:
        clean_title = "Steam Big Picture Mode"
        system_id = "steam"
        game_state = "idle"
        sys_name = "STEAM"
        display_title = "Steam Big Picture Mode"
        temp_suffix = f" • GPU {gpu_temp_str}" if gpu_temp_str else ""
        game_sub = f"🕹️ Ready • Steam Library & Carousel{temp_suffix}"
        data = None
        sys_defaults = SYSTEM_ART_MAP["steam"]
        badge_icon = "mdi:steam"
        badge_color = "blue"
    elif batocera_title and batocera_title not in ["None", "unknown", "unavailable", ""]:
        clean_title = batocera_title
        system_id = batocera_sys
        game_state = batocera_st or "idle"
        sys_name = system_id.upper() if system_id else "ARCADE"
        display_title = clean_title
        game_sub = "🕹️ Ready • EmulationStation System Menu"
        data = _fetch_game_art_from_secrets(clean_title, system_id)
        sys_defaults = SYSTEM_ART_MAP.get(system_id, SYSTEM_ART_MAP["default"])
        badge_icon = "mdi:gamepad-variant"
        badge_color = "green"
    elif safe_state_get(PC_SWITCH) == "on" or safe_state_get(PC_ONLINE) == "on":
        clean_title = "ASUS ROG Gaming PC"
        system_id = "pc"
        game_state = "idle"
        sys_name = "PC"
        display_title = "ASUS ROG Gaming PC"
        temp_suffix = f" • GPU {gpu_temp_str}" if gpu_temp_str else ""
        game_sub = f"🕹️ Ready • PC Gaming via Moonlight{temp_suffix}"
        data = None
        sys_defaults = SYSTEM_ART_MAP["pc"]
        badge_icon = "mdi:desktop-tower"
        badge_color = "purple"
    else:
        clean_title = ""
        system_id = "arcade"
        game_state = "idle"
        sys_name = "ARCADE"
        display_title = "EmulationStation Carousel"
        game_sub = "🕹️ Ready • EmulationStation System Menu"
        data = None
        sys_defaults = SYSTEM_ART_MAP["default"]
        badge_icon = "mdi:gamepad-variant"
        badge_color = "green"

    poster_val = data.get("poster") if (data and data.get("poster")) else sys_defaults["poster"]
    backdrop_val = data.get("backdrop") if (data and data.get("backdrop")) else sys_defaults["backdrop"]
    source_val = data.get("source", "system_art") if data else "system_art"
    final_title = data.get("title", display_title) if data else display_title

    state.set(
        THEATER_BOXART,
        value=poster_val,
        new_attributes={
            "friendly_name": "Theater Box Art",
            "title": final_title,
            "raw_title": clean_title,
            "system": sys_name,
            "backdrop_url": backdrop_val,
            "media_type": "game",
            "source": source_val,
            "state": game_state,
            "gpu_temperature": gpu_temp_str,
        },
    )

    set_theater_poster(
        poster_val, final_title, game_sub,
        raw_title=clean_title, backdrop_url=backdrop_val, media_type="game",
        source=source_val, badge_icon=badge_icon, badge_color=badge_color,
        system=sys_name, gpu_temperature=gpu_temp_str,
    )


@state_trigger(
    "sensor.batocera_current_game, "
    "sensor.batocera_state, "
    "sensor.batocera_system, "
    "sensor.desktop_rspn8nu_activewindow, "
    "sensor.desktop_rspn8nu_gputemperature, "
    "switch.gaming_pc, "
    "binary_sensor.gaming_pc_online, "
    "sensor.theater_mode"
)
def on_theater_game_changed():
    # Debounce: a newer trigger cancels this run, so only the last burst event renders.
    task.unique("theater_game_art")
    task.sleep(0.5)
    update_game_poster()


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
    """Two-way sync: user/UI changes input_select -> triggers respective mode orchestrator."""
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
# THEATER MODE TELEMETRY & HARDWARE CONDUCTION
# ------------------------------------------------------------------------------
@time_trigger("startup")
@state_trigger(
    "media_player.theater_receiver, media_player.onn_pro, remote.onn_pro, "
    "sensor.mediasession2mqtt_1_application_id, sensor.batocera_state, switch.batocera, "
    "sensor.desktop_rspn8nu_activewindow, switch.gaming_pc, binary_sensor.gaming_pc_online"
)
def update_theater_mode():
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
@state_trigger("media_player.theater_receiver")
def update_theater_in_use():
    task.unique("theater_in_use_debounce")
    receiver_on = state.get(RECEIVER) == "on"

    if receiver_on:
        state.set(THEATER_IN_USE, value="on")
    else:
        task.sleep(5)
        if state.get(RECEIVER) != "on":
            state.set(THEATER_IN_USE, value="off")


@state_trigger("media_player.theater_receiver == 'off'")
def handle_receiver_power_off():
    """Detects external/unmanaged AVR power-off (e.g. Yamaha remote or front button) while theater is active."""
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


# ------------------------------------------------------------------------------
# SOUND MODES & AUDIO CONDUCTION
# ------------------------------------------------------------------------------
@state_trigger("sensor.batocera_state == 'playing'")
def configure_batocera_audio():
    if is_booting():
        return
    system_id = (safe_state_get(BATOCERA_SYSTEM) or "").lower()
    snd = "Straight" if system_id in RETRO_2CH_SYSTEMS else "Surround Decoder"
    set_receiver_sound_mode(snd)
    safe_service(rest_command.yamaha_set_center_trim, level=0.0)


@service
def apply_sports_audio_mode():
    if safe_state_get(THEATER_IN_USE) != "on":
        return
    set_receiver_sound_mode("Sports")
    level_float = safe_float(safe_state_get(ANNOUNCER_VOLUME), -10.0)
    safe_service(rest_command.yamaha_set_center_trim, level=level_float)


@service
def reset_standard_audio_mode(target_dsp="Standard"):
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


@state_trigger("input_number.theater_announcer_volume")
def sync_announcer_volume_to_hardware(value=None):
    if safe_state_get(THEATER_IN_USE) != "on":
        return
    if safe_state_get(THEATER_MODE) == "sports" or get_active_app_id() in SPORTS_APPS:
        level_float = safe_float(value, default=None)
        if level_float is not None:
            safe_service(rest_command.yamaha_set_center_trim, level=level_float)
            # Sync 3-way toggle state
            zone = _announcer_zone(level_float)
            if zone and zone != safe_state_get(ANNOUNCER_PRESET):
                input_select.select_option(entity_id=ANNOUNCER_PRESET, option=zone)


@service
def theater_set_announcer_preset(preset=None):
    if not preset:
        return
    if preset in ANNOUNCER_PRESET_LEVELS:
        input_select.select_option(entity_id=ANNOUNCER_PRESET, option=preset)
        new_val = ANNOUNCER_PRESET_LEVELS[preset]
        input_number.set_value(entity_id=ANNOUNCER_VOLUME, value=new_val)
        if safe_state_get(THEATER_IN_USE) == "on":
            safe_service(rest_command.yamaha_set_center_trim, level=new_val)


@state_trigger("input_select.theater_announcer_preset")
def sync_announcer_preset_to_hardware(value=None):
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
    vol_float = safe_float(safe_state_getattr(RECEIVER, "volume_level"), 0.5)
    step_val = safe_float(step_db, 1.0)
    delta = step_val / 97.0
    new_vol = min(1.0, max(0.0, vol_float + delta if direction == "Up" else vol_float - delta))
    safe_service(media_player.volume_set, entity_id=RECEIVER, volume_level=round(new_vol, 3))

    val_str = f"{direction} {int(step_val)} dB" if step_val.is_integer() else f"{direction} {step_val} dB"
    safe_service(rest_command.yamaha_master_volume_step, step=val_str)


@service
def theater_volume_up(step_db=1.0):
    _step_avr_volume("Up", step_db)


@service
def theater_volume_down(step_db=1.0):
    _step_avr_volume("Down", step_db)


@service
def theater_announcer_up(step=1.0):
    cur_val = safe_float(safe_state_get(ANNOUNCER_VOLUME), -10.0)
    step_val = safe_float(step, 1.0)
    new_val = min(10.0, round(cur_val + step_val, 1))
    input_number.set_value(entity_id=ANNOUNCER_VOLUME, value=new_val)


@service
def theater_announcer_down(step=1.0):
    cur_val = safe_float(safe_state_get(ANNOUNCER_VOLUME), 0.0)
    step_val = safe_float(step, 1.0)
    new_val = max(-10.0, round(cur_val - step_val, 1))
    input_number.set_value(entity_id=ANNOUNCER_VOLUME, value=new_val)


@service
def theater_announcer_mute():
    cur_val = safe_float(safe_state_get(ANNOUNCER_VOLUME), 0.0)
    new_val = 0.0 if cur_val <= -9.5 else -10.0
    input_number.set_value(entity_id=ANNOUNCER_VOLUME, value=new_val)


@state_trigger(
    "sensor.mediasession2mqtt_1_application_id, "
    "media_player.onn_pro.app_id, "
    "remote.onn_pro.current_activity"
)
def route_app_audio_mode():
    task.unique("theater_audio_routing")

    if is_booting() or safe_state_get(THEATER_IN_USE) != "on":
        return

    if safe_state_getattr(RECEIVER, "source") != "HDMI1":
        return

    app_id = get_active_app_id()
    if not app_id or app_id in ["com.google.android.apps.tv.launcherx", "com.google.android.tvlauncher"]:
        return

    if app_id in SPORTS_APPS or safe_state_get(THEATER_MODE) == "sports":
        apply_sports_audio_mode()
        return

    target_mode = APP_AUDIO_MODES.get(app_id, "Standard")
    reset_standard_audio_mode(target_dsp=target_mode)


# ------------------------------------------------------------------------------
# AUTO POWER-OFF & PROJECTOR COOLDOWN
# ------------------------------------------------------------------------------
def is_batocera_on():
    """Determines if the Batocera x86 laptop client is powered on or active."""
    return (
        safe_state_get(BATOCERA_SWITCH) == "on"
        or safe_state_get(BATOCERA_STATE) in ["playing", "idle"]
        or safe_float(safe_state_get(BATOCERA_CURRENT), 0.0) >= 0.05
    )


@service
def shutdown_batocera():
    """Performs clean software shutdown of Batocera console to protect filesystems and states."""
    if not is_batocera_on():
        return
    log.info("[Batocera] Clean software shutdown dispatched.")
    for btn in ["button.batocera_shutdown_2", "button.batocera_shutdown"]:
        try:
            button.press(entity_id=btn)
            return
        except Exception:
            continue
    try:
        shell_cmd = getattr(builtins, "shell_command", None) if "builtins" in globals() else None
        if shell_cmd:
            shell_cmd.batocera_shutdown()
    except Exception:
        pass


@state_trigger("float(sensor.batocera_current) < 0.05", state_hold=12)
def batocera_auto_power_off():
    if is_booting():
        return
    if safe_state_get(BATOCERA_SWITCH) == "on":
        switch.turn_off(entity_id=BATOCERA_SWITCH)
    reset_boxart_idle(source="idle", boxart_state="off")


def _cec_standby_burst(rounds=2, drop_receiver=True):
    """Sleep the Onn (broadcasts CEC standby) and drops receiver until projector current collapses.
    Never wakes Onn if it is already off/standby, preventing false wakeups and HDMI passthrough leaks."""
    for _ in range(rounds):
        if safe_state_get(ONN_PRO) == "on":
            safe_service(remote.send_command, entity_id=ONN_REMOTE, command="SLEEP")
            safe_service(media_player.turn_off, entity_id=ONN_PRO)
            task.sleep(1.0)
        if drop_receiver and safe_state_get(RECEIVER) == "on":
            safe_service(media_player.select_source, entity_id=RECEIVER, source="AUDIO1")
            task.sleep(0.5)
            safe_service(media_player.turn_off, entity_id=RECEIVER)
            task.sleep(2.0)
        if safe_float(safe_state_get(PROJECTOR_CURRENT), 99.0) < 0.5:
            return True
    return False


def safe_projector_cooldown():
    task.unique("projector_cooldown_worker")
    _projector_cooldown_body()


def _projector_cooldown_body():
    if safe_state_get(PROJECTOR_SWITCH) != "on":
        return

    log.info("[Theater Projector] Shutdown initiated. Commencing 90s thermal lock...")
    task.sleep(90)

    fan_stopped = False
    consecutive_low_reads = 0

    for attempt in range(25):
        mode = safe_state_get(THEATER_MODE)
        if mode in ["movie", "game", "sports"]:
            log.info("[Theater Projector] Session resumed. Cooldown power cut cancelled.")
            return

        try:
            current_val = float(safe_state_get(PROJECTOR_CURRENT))
        except (ValueError, TypeError):
            consecutive_low_reads = 0
            log.warning(f"[Theater Projector] Transient sensor reading on attempt {attempt + 1}/25. Retrying...")
            task.sleep(10)
            continue

        if current_val <= 0.06:
            consecutive_low_reads += 1
            if consecutive_low_reads >= 2:
                fan_stopped = True
                break
        else:
            consecutive_low_reads = 0
            # Lamp still lit: re-send CEC standby (twice total, ~110s and ~170s in)
            if current_val > 0.5 and attempt in (2, 8) and mode in ["music", "off"]:
                log.warning("[Theater Projector] Lamp drawing >0.5A. Re-sending CEC standby...")
                # In music mode keep the receiver on; only sleep the Onn
                _cec_standby_burst(rounds=1, drop_receiver=(mode == "off"))
                if mode == "off":
                    state.set(THEATER_MODE, value="off")
                    state.set(THEATER_IN_USE, value="off")

        task.sleep(10)

    if fan_stopped and safe_state_get(THEATER_MODE) in ["music", "off"]:
        log.info("[Theater Projector] Cooldown double-verified. Cutting projector mains.")
        switch.turn_off(entity_id=PROJECTOR_SWITCH)
    else:
        log.warning("[Theater Projector] Cooldown could not be verified. Mains left ON for safety.")


# ------------------------------------------------------------------------------
# ORCHESTRATION SERVICES & CROSS-MODE TEARDOWN
# ------------------------------------------------------------------------------
def _teardown_conflicting_sources(target_mode: str):
    """Prevents cross-mode session leaks, hardware lockups, and background audio bleed."""
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


@service
def play_movie():
    state.set(CURTAIN_CALL, value="off")
    task.unique("projector_cooldown_worker")
    _teardown_conflicting_sources("movie")

    state.set(THEATER_MODE, value="movie")
    state.set(THEATER_IN_USE, value="on")
    sync_theater_select("movie")
    release_sports_social_mode()

    # Immediately wipe any stale Spotify art from the marquee
    set_theater_poster(
        "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=800&q=80",
        "Stremio",
        "Ready to Stream • Stremio",
        backdrop_url="https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1200&q=80",
        media_type="movie", source="stremio", badge_icon="mdi:movie-open", badge_color="blue",
    )

    if safe_state_get("input_boolean.sandbox_mode") == "on":
        return

    switch.turn_on(entity_id=PROJECTOR_SWITCH)
    media_player.turn_on(entity_id=RECEIVER)
    media_player.select_source(entity_id=RECEIVER, source="HDMI1")

    media_player.turn_on(entity_id=ONN_PRO)
    task.sleep(1.0)

    launch_onn_app("com.stremio.one")
    task.sleep(0.5)
    update_theater_media_art()

    set_receiver_sound_mode("Standard")

    safe_service(rest_command.yamaha_set_center_trim, level=0.0)


@service
def play_game():
    state.set(CURTAIN_CALL, value="off")
    task.unique("projector_cooldown_worker")
    _teardown_conflicting_sources("game")

    switch.turn_on(entity_id=PROJECTOR_SWITCH)
    switch.turn_on(entity_id=BATOCERA_SWITCH)
    media_player.turn_on(entity_id=RECEIVER)
    task.sleep(2.0)
    media_player.select_source(entity_id=RECEIVER, source="HDMI2")
    set_receiver_sound_mode("Surround Decoder")

    safe_service(rest_command.yamaha_set_center_trim, level=0.0)

    state.set(THEATER_MODE, value="game")
    state.set(THEATER_IN_USE, value="on")
    sync_theater_select("game")
    release_sports_social_mode()


@service
def play_pc_game(app="moonlight", target="batocera"):
    """Orchestrates PC Gaming mode: boots PC via WOL, selects AVR surround sound, launches Moonlight on Batocera."""
    state.set(CURTAIN_CALL, value="off")
    task.unique("projector_cooldown_worker")
    _teardown_conflicting_sources("game")

    switch.turn_on(entity_id=PROJECTOR_SWITCH)
    switch.turn_on(entity_id=PC_SWITCH)
    media_player.turn_on(entity_id=RECEIVER)
    task.sleep(2.0)

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
        launch_onn_app("com.limelight")

    safe_service(rest_command.yamaha_set_center_trim, level=0.0)

    state.set(THEATER_MODE, value="game")
    state.set(THEATER_IN_USE, value="on")
    sync_theater_select("game")
    release_sports_social_mode()
    update_game_poster()


@service
def play_music():
    state.set(CURTAIN_CALL, value="off")
    _teardown_conflicting_sources("music")
    state.set(THEATER_MODE, value="music")
    state.set(THEATER_IN_USE, value="on")
    sync_theater_select("music")

    if is_projector_cold():
        switch.turn_off(entity_id=PROJECTOR_SWITCH)
        task.sleep(0.5)
    else:
        safe_service(remote.send_command, entity_id=ONN_REMOTE, command="SLEEP")
        task.create(safe_projector_cooldown)

    media_player.turn_on(entity_id=RECEIVER)
    media_player.select_source(entity_id=RECEIVER, source="HDMI1")

    # Sound mode directly set to 7ch Stereo
    set_receiver_sound_mode("7ch Stereo")

    safe_service(rest_command.yamaha_set_center_trim, level=0.0)

    # Wake Onn if needed, but do NOT launch any app (user controls via phone via Spotify Connect)
    media_player.turn_on(entity_id=ONN_PRO)
    update_theater_media_art()


@service
def theater_play_spotify_playlist(uri="spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", random_song=True):
    """Puts theater into Hi-Fi music mode and triggers target Spotify playlist via native media player or Spotcast."""
    play_music()
    task.sleep(1.0)
    try:
        media_player.play_media(
            entity_id=SPOTIFY_PLAYER,
            media_content_id=uri,
            media_content_type="playlist",
        )
    except Exception as e:
        log.warning(f"Native Spotify play_media attempt error, trying spotcast: {e}")
        try:
            service.call("spotcast", "start", entity_id=SPOTIFY_PLAYER, uri=uri, random_song=random_song)
        except Exception as e2:
            log.warning(f"Spotcast fallback error: {e2}")


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
    """Guarantees at least 1 ATSC 1.0 physical tuner is free for the basement theater."""
    if safe_state_get("input_boolean.sandbox_mode") == "on":
        return True

    t0 = (safe_state_get("sensor.tuner0") or "idle").lower().strip()
    t1 = (safe_state_get("sensor.tuner1") or "idle").lower().strip()
    if t0 not in TUNER_IDLE_STATES and t1 not in TUNER_IDLE_STATES:
        log.warning("HDHomeRun Contention: Both tuners busy. Preempting remote stream on Tuner 1 for basement theater.")
        return preempt_tuner_for_theater(target_tuner="1")
    return True


@service
def play_sports(app=None):
    """Sports mode. Default source is HDHomeRun; pass app="prime" to watch sports on Prime Video instead."""
    state.set(CURTAIN_CALL, value="off")
    task.unique("projector_cooldown_worker")
    _teardown_conflicting_sources("sports")

    use_prime = str(app or "").lower().strip() in ("prime", "prime_video", "amazon")
    source_label = "Prime Video" if use_prime else "HDHomeRun"

    state.set(THEATER_MODE, value="sports")
    state.set(THEATER_IN_USE, value="on")
    sync_theater_select("sports")

    # Immediately set sports marquee with Eagles logo/matchup so stale Spotify art is wiped
    opp = safe_state_getattr("sensor.philadelphia_eagles", "opponent_name")
    opp_abbr = safe_state_getattr("sensor.philadelphia_eagles", "opponent_abbr") or opp or "OPP"
    team_abbr = safe_state_getattr("sensor.philadelphia_eagles", "team_abbr") or "PHI"
    team_score = safe_state_getattr("sensor.philadelphia_eagles", "team_score")
    opp_score = safe_state_getattr("sensor.philadelphia_eagles", "opponent_score")
    quarter = safe_state_getattr("sensor.philadelphia_eagles", "quarter")
    clock = safe_state_getattr("sensor.philadelphia_eagles", "clock")
    down_dist = safe_state_getattr("sensor.philadelphia_eagles", "down_distance_text")
    last_play = safe_state_getattr("sensor.philadelphia_eagles", "last_play")
    possession = safe_state_getattr("sensor.philadelphia_eagles", "possession")
    team_logo = safe_state_getattr("sensor.philadelphia_eagles", "team_logo") or "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png"
    opp_logo = safe_state_getattr("sensor.philadelphia_eagles", "opponent_logo")
    game_state = safe_state_get("sensor.philadelphia_eagles")
    trim = safe_state_get(ANNOUNCER_VOLUME) or "0.0"
    sports_backdrop = "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=1200&q=80"

    if game_state == "IN" and team_score is not None and opp_score is not None:
        sports_title = f"{team_abbr} {team_score} - {opp_score} {opp_abbr}"
        sub_parts = []
        if quarter and clock:
            sub_parts.append(f"Q{quarter} {clock}")
        if down_dist:
            sub_parts.append(down_dist)
        sub_parts.append(f"Booth Trim: {trim} dB")
        sports_subtitle = " • ".join(sub_parts)
    elif game_state == "POST" and team_score is not None and opp_score is not None:
        sports_title = f"FINAL: {team_abbr} {team_score} - {opp_score} {opp_abbr}"
        sports_subtitle = f"Final Score • Stadium Surround • Booth Trim: {trim} dB"
    else:
        sports_title = f"Eagles vs {opp}" if opp else "Live Sports Broadcast"
        sports_subtitle = f"Stadium Surround • {source_label} • Booth Trim: {trim} dB"

    set_theater_poster(
        team_logo, sports_title, sports_subtitle,
        backdrop_url=sports_backdrop, media_type="sports", source="sports",
        badge_icon="mdi:football", badge_color="green",
        team_logo=team_logo,
        opponent_logo=opp_logo,
        team_score=team_score,
        opponent_score=opp_score,
        team_abbr=team_abbr,
        opponent_abbr=opp_abbr,
        quarter=quarter,
        clock=clock,
        down_distance_text=down_dist,
        last_play=last_play,
        possession=possession,
        game_state=game_state,
    )

    if safe_state_get("input_boolean.sandbox_mode") == "on":
        return

    switch.turn_on(entity_id=PROJECTOR_SWITCH)
    media_player.turn_on(entity_id=RECEIVER)
    media_player.select_source(entity_id=RECEIVER, source="HDMI1")
    media_player.turn_on(entity_id=ONN_PRO)
    task.sleep(1.0)

    if not use_prime:
        # Guarantee an ATSC tuner is unblocked before launching broadcast app
        ensure_hdhomerun_tuner_available()

    apply_sports_audio_mode()
    launch_onn_app(PRIME_VIDEO_PACKAGE if use_prime else "com.silicondust.view")
    task.sleep(0.5)
    update_theater_media_art()

    if safe_state_get(LIGHTING_MODE_SELECT) != MODE_SOCIAL:
        state.set(SOCIAL_SOURCE, value="sports")
        input_select.select_option(entity_id=LIGHTING_MODE_SELECT, option=MODE_SOCIAL)


@service
def session_end_house_lights():
    state.set(CURTAIN_CALL, value="on")

    # 1. Restore house lights first so the room isn't dark while the CEC burst runs
    safe_service(switch.turn_on, entity_id="switch.basement_adaptive_lighting_adaptive_lighting_basement_adaptive_lighting")

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
            safe_service(media_player.turn_off, entity_id=ONN_PRO)
    else:
        # Non-gaming: release foreground apps/tuner only if Onn is currently on
        if safe_state_get(ONN_PRO) == "on":
            safe_service(remote.send_command, entity_id=ONN_REMOTE, command="HOME")
            task.sleep(0.5)
            safe_service(remote.send_command, entity_id=ONN_REMOTE, command="SLEEP")
            safe_service(media_player.turn_off, entity_id=ONN_PRO)

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

    if safe_state_get(PROJECTOR_SWITCH) == "on":
        task.create(safe_projector_cooldown)


@service
def force_projector_off():
    media_player.turn_on(entity_id=RECEIVER)
    media_player.turn_on(entity_id=ONN_PRO)
    task.sleep(2.0)
    remote.send_command(entity_id=ONN_REMOTE, command="SLEEP")
    media_player.turn_off(entity_id=ONN_PRO)
    task.sleep(2.5)
    media_player.turn_off(entity_id=RECEIVER)
    safe_service(media_player.turn_off, entity_id=RECEIVER_ZONE_2)


@service
def theater_force_reconcile():
    """Forces hardware states, receiver input, sound mode, and UI sensors into full synchronization."""
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
    """Direct App Launching and Deep-Linking service for Onn 4K Pro & Theater."""
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
        launch_onn_app("com.google.android.youtube.tv")
    elif app_lower in ["netflix"]:
        launch_onn_app("com.netflix.ninja")
    elif app_lower in ["prime", "prime_video", "amazon"]:
        launch_onn_app(PRIME_VIDEO_PACKAGE)
    else:
        launch_onn_app(app)


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
    """
    Powers on theater, configures Yamaha audio to Bitstream, sets lighting to Cinema Shield,
    resolves IMDb metadata via Cinemeta, and deep-links directly into Stremio with autoPlay.
    """
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
        else "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=800&q=80"
    )
    backdrop_url = (
        meta.get("background")
        if meta and meta.get("background")
        else "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=1200&q=80"
    )

    # 2. Immediately set theatrical poster & state
    state.set(CURTAIN_CALL, value="off")
    task.unique("projector_cooldown_worker")
    _teardown_conflicting_sources("movie")

    state.set(THEATER_MODE, value="movie")
    state.set(THEATER_IN_USE, value="on")
    sync_theater_select("movie")
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

    if safe_state_get("input_boolean.sandbox_mode") == "on":
        return

    # 3. Hardware conduction: Mains + Yamaha AVR + Audio Routing
    switch.turn_on(entity_id=PROJECTOR_SWITCH)
    media_player.turn_on(entity_id=RECEIVER)
    media_player.select_source(entity_id=RECEIVER, source="HDMI1")
    set_receiver_sound_mode("Standard")

    safe_service(rest_command.yamaha_set_center_trim, level=0.0)

    # 4. Wake Onn Pro
    media_player.turn_on(entity_id=ONN_PRO)
    task.sleep(1.0)

    # 5. Deep Link Intent Construction
    if imdb_id and str(imdb_id).startswith("tt"):
        deep_link = f"stremio:///detail/movie/{imdb_id}/{imdb_id}?autoPlay=true"
    else:
        encoded_query = urllib.parse.quote(clean_term)
        deep_link = f"stremio:///search?search={encoded_query}"

    log.info(f"[Theater] Sending Stremio deep link: {deep_link}")

    # Send deep link via Android TV Remote activity
    safe_service(remote.turn_on, entity_id=ONN_REMOTE, activity=deep_link)

    # ADB explicit intent broadcast / am start
    try:
        service.call(
            "androidtv",
            "adb_command",
            entity_id=ONN_PRO,
            command=f'am start -a android.intent.action.VIEW -d "{deep_link}" -n com.stremio.one/.MainActivity',
        )
    except Exception:
        pass