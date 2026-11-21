# ==============================================================================
# THEATER ART: online poster and box art lookups for theater.py
# ==============================================================================
# Movie and TV posters: TMDB (needs tmdb_api_key in secrets.yaml), then Cinemeta,
# then TVMaze. Game box art: SteamGridDB (steamgriddb_api_key), then RAWG
# (rawg_api_key), then the libretro thumbnail repos.
#
# theater.py decides which poster to show and calls _fetch_movie_or_tv_art() and
# _fetch_game_art_from_secrets() here. Both are plain functions: call them without
# await. Only the blocking HTTP request runs in a thread, through task.executor.
#
# Saving this file reloads theater.py too (pyscript reloads every file that
# imports a module), so edit it with the theater idle.
# ==============================================================================
import re
import time
import urllib.parse

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
# API KEYS FROM secrets.yaml
# ------------------------------------------------------------------------------
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
    """A value from secrets.yaml. Read once, then cached until this file reloads."""
    if key_name in _SECRETS_CACHE:
        return _SECRETS_CACHE[key_name] or None
    val = task.executor(_scan_secrets_file, SECRET_PATHS, key_name)
    _SECRETS_CACHE[key_name] = val or ""
    return val or None


RE_GENERIC_SEASON = re.compile(r"^(?:season|series|episode|ep|s)\s*\d+$", re.IGNORECASE)


def get_search_candidates(raw_title, artist=None):
    """Titles to try in art lookups, best guess first. Cleans up file names (extension,
    resolution and codec tags, year) and splits 'Show S01E02 Episode' and 'Show -
    Episode' into their parts."""
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
# ART LOOKUP CACHE AND OUTAGE BACKOFF
# Lookups are cached in memory (CACHE_TTL_HIT / CACHE_TTL_MISS). After
# CIRCUIT_MAX_FAILURES failed requests in a row, a service is skipped for
# CIRCUIT_COOLDOWN seconds (a "circuit breaker"), so a site that's down
# doesn't slow down every poster.
# ------------------------------------------------------------------------------
_ART_CACHE = {}          # key -> (timestamp, data)
_CIRCUIT_STATE = {}      # service_name -> {"failures": int, "tripped_until": float}

CACHE_TTL_HIT = 3600     # 1 hour for successful art lookup
CACHE_TTL_MISS = 300     # 5 minutes negative cache for non-matches
CIRCUIT_MAX_FAILURES = 3 # Trip after 3 consecutive network failures
CIRCUIT_COOLDOWN = 300   # 5-minute recovery backoff


def _is_circuit_open(service_name: str) -> bool:
    """True while a service is being skipped after repeated failures (see
    CIRCUIT_COOLDOWN)."""
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
    """Count a failed request. After CIRCUIT_MAX_FAILURES in a row, skip that service
    for CIRCUIT_COOLDOWN seconds."""
    cs = _CIRCUIT_STATE.setdefault(service_name, {"failures": 0, "tripped_until": 0})
    cs["failures"] += 1
    if cs["failures"] >= CIRCUIT_MAX_FAILURES:
        cs["tripped_until"] = time.time() + CIRCUIT_COOLDOWN
        try:
            log.warning(f"[Theater Resilience] Circuit breaker tripped for {service_name}! Backing off for {CIRCUIT_COOLDOWN}s.")
        except Exception:
            pass


def _record_service_success(service_name: str):
    """A request worked: clear that service's failure count."""
    cs = _CIRCUIT_STATE.get(service_name)
    if cs:
        cs["failures"] = 0
        cs["tripped_until"] = 0


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


def _title_words(text):
    """The lowercase words of a title, without punctuation."""
    return [w for w in re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).split() if w]


def _title_resembles(candidate, item):
    """True when a search result's name plausibly is the title searched for: one
    contains the other as whole words, or they share most of the shorter one's words.
    Whole words, so "Her" doesn't match "The Other Side"."""
    want = _title_words(candidate)
    if not want:
        return False
    for key in ("title", "name", "original_title", "original_name"):
        have = _title_words(item.get(key))
        if not have:
            continue
        a, b = f" {' '.join(want)} ", f" {' '.join(have)} "
        if a in b or b in a:
            return True
        shorter = want if len(want) <= len(have) else have
        shared = len(set(want) & set(have))
        if shared / len(set(shorter)) >= 0.6:
            return True
    return False


def _tmdb_art(candidates):
    """Look each search term up on TMDB (needs tmdb_api_key in secrets.yaml).
    Returns the art dict for the first good match, or None."""
    api_key = _read_secret("tmdb_api_key")
    if not api_key:
        return None
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
        # Take the first top result that has a poster and whose name resembles
        # what was searched; TMDB pads thin searches with unrelated titles.
        best = None
        for item in results[:5]:
            if (item.get("media_type") in ["movie", "tv"] and item.get("poster_path")
                    and _title_resembles(candidate, item)):
                best = item
                break
        if not best:
            continue
        poster_path = best.get("poster_path")
        backdrop_path = best.get("backdrop_path")
        if poster_path:
            return {
                "poster": f"https://image.tmdb.org/t/p/w500{poster_path}",
                "backdrop": f"https://image.tmdb.org/t/p/w780{backdrop_path}" if backdrop_path else "",
                "title": best.get("title") or best.get("name") or candidate,
                "media_type": best.get("media_type", "movie"),
                "source": "tmdb",
            }
    return None


def _cinemeta_art(candidates):
    """Look each search term up on Cinemeta (Stremio's catalog; no API key), first
    for an exact name match, then for a close one (_title_resembles).
    Returns the art dict for the first match, or None."""
    searched = {}  # (search term, catalog) -> results, so the second pass doesn't download again
    for pass_mode in ("exact", "fuzzy"):
        for candidate in candidates:
            if _is_circuit_open("cinemeta"):
                break
            encoded = urllib.parse.quote(candidate)
            match_found = None
            for cat in ["series", "movie"]:
                if (candidate, cat) not in searched:
                    data = _fetch_json(
                        "cinemeta",
                        f"https://v3-cinemeta.strem.io/catalog/{cat}/top/search={encoded}.json",
                        timeout=3,
                    )
                    searched[(candidate, cat)] = (data or {}).get("metas", [])[:4]
                for m in searched[(candidate, cat)]:
                    m_name = m.get("name", "").strip()
                    if pass_mode == "exact" and m_name.lower() == candidate.lower():
                        match_found = (m, cat)
                        break
                    elif pass_mode == "fuzzy" and _title_resembles(candidate, m):
                        match_found = (m, cat)
                        break
                if match_found:
                    break

            if match_found:
                meta, cat = match_found
                poster_url = meta.get("poster")
                bg_url = meta.get("background") or poster_url
                if poster_url:
                    # Ask for a bigger image than the catalog's thumbnail
                    if "_V1_SX250.jpg" in poster_url:
                        poster_url = poster_url.replace("_V1_SX250.jpg", "_V1_SX700.jpg")
                    elif "/small/" in poster_url:
                        poster_url = poster_url.replace("/small/", "/medium/")
                    return {
                        "poster": poster_url,
                        "backdrop": bg_url,
                        "title": meta.get("name") or candidate,
                        "media_type": meta.get("type", cat),
                        "source": "cinemeta",
                    }
    return None


def _tvmaze_art(candidates):
    """Look each search term up on TVMaze (TV shows only; no API key).
    Returns the art dict for the first show with an image, or None."""
    for candidate in candidates:
        if _is_circuit_open("tvmaze"):
            break
        encoded = urllib.parse.quote(candidate)
        data = _fetch_json("tvmaze", f"https://api.tvmaze.com/singlesearch/shows?q={encoded}", timeout=3)
        if data and data.get("image"):
            img = data["image"].get("original") or data["image"].get("medium")
            if img:
                return {
                    "poster": img,
                    "backdrop": img,
                    "title": data.get("name") or candidate,
                    "media_type": "tv",
                    "source": "tvmaze",
                }
    return None


def _movie_or_tv_art_lookup(raw_title, artist=None):
    """Poster and backdrop for a movie or show. Tries TMDB, then Cinemeta, then TVMaze.
    Returns {poster, backdrop, title, media_type, source}, or None. Results are
    cached, misses for less time than hits."""
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

    res = _tmdb_art(candidates) or _cinemeta_art(candidates) or _tvmaze_art(candidates)
    if res:
        _ART_CACHE[cache_key] = (time.time(), res)
        return res

    # Don't negative-cache when a service was down: a brief outage would pin the fallback poster.
    had_outage = any([_is_circuit_open(s) for s in ("tmdb", "cinemeta", "tvmaze")])
    if not had_outage:
        _ART_CACHE[cache_key] = (time.time(), None)
    return None


def _fetch_movie_or_tv_art(raw_title, artist=None):
    """_movie_or_tv_art_lookup, but logs and returns None instead of raising."""
    try:
        return _movie_or_tv_art_lookup(raw_title, artist)
    except Exception as e:
        log.warning(f"[Theater] Movie/TV art lookup failed for {raw_title!r}: {e}")
        return None


def _fetch_sgdb_asset(url, api_key):
    """The first image URL from a SteamGridDB grid or hero request, or None."""
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
    """Box art from the libretro-thumbnails repos on GitHub (no API key). Tries the
    title alone and with common region tags such as '(USA)'."""
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
    """Box art for a game: SteamGridDB (needs steamgriddb_api_key), then RAWG
    (rawg_api_key), then libretro. ROM file names are cleaned first. Returns {poster,
    backdrop, title, source}, or None. Cached like movie art."""
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
    """_game_art_lookup, but logs and returns None instead of raising."""
    try:
        return _game_art_lookup(game_title, system_id)
    except Exception as e:
        log.warning(f"[Theater] Game art lookup failed for {game_title!r} ({system_id}): {e}")
        return None
