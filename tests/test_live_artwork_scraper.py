"""
Smart Multi-Candidate Scraper for Movies, TV Shows, and YouTube.
Run: python3 ~/ha_config/tests/test_live_artwork_scraper.py
"""
import sqlite3
import os
import re
import json
import urllib.parse
import urllib.request

DB_PATH = os.path.expanduser("~/ha_config/home-assistant_v2.db")
SECRETS_PATH = os.path.expanduser("~/ha_config/secrets.yaml")
JSON_PATH = os.path.join(os.path.dirname(__file__), "telemetry_48h.json")

# 1. Fetch TMDB API Key
api_key = None
if os.path.exists(SECRETS_PATH):
    with open(SECRETS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("tmdb_api_key:"):
                api_key = line.split(":", 1)[1].strip().strip("\"'")
                break

raw_titles = []
if os.path.exists(DB_PATH):
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cursor = conn.cursor()
        query = """
        SELECT DISTINCT s.state
        FROM states s
        JOIN states_meta sm ON s.metadata_id = sm.metadata_id
        WHERE sm.entity_id = 'sensor.mediasession2mqtt_1_media_title'
          AND s.state NOT IN ('unavailable', 'unknown', 'None', '')
        ORDER BY s.last_updated_ts DESC
        LIMIT 10;
        """
        cursor.execute(query)
        raw_titles = [r[0] for r in cursor.fetchall()]
        conn.close()
    except Exception:
        raw_titles = []

if not raw_titles and os.path.exists(JSON_PATH):
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            telemetry = json.load(f)
        seen = set()
        for item in telemetry:
            if item.get("entity_id") == "sensor.mediasession2mqtt_1_media_title":
                st = item.get("state")
                if st and st not in ('unavailable', 'unknown', 'None', '') and st not in seen:
                    seen.add(st)
                    raw_titles.append(st)
    except Exception:
        raw_titles = []

if not raw_titles:
    raw_titles = [
        "Futurama S01E01 - Space Pilot 3000",
        "Severance - Good News About Hell",
        "Inception 2010 1080p Bluray",
        "NFL Blitz 2000 (USA)",
    ]

def search_tmdb(query_str):
    encoded = urllib.parse.quote(query_str)
    url = f"https://api.themoviedb.org/3/search/multi?api_key={api_key}&query={encoded}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 HomeAssistant/Pyscript"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            if results:
                best = results[0]
                return {
                    "type": best.get("media_type", "unknown").upper(),
                    "title": best.get("title") or best.get("name"),
                    "year": (best.get("first_air_date") or best.get("release_date") or "")[:4],
                    "poster": f"https://image.tmdb.org/t/p/w500{best.get('poster_path')}" if best.get('poster_path') else "",
                    "backdrop": f"https://image.tmdb.org/t/p/w780{best.get('backdrop_path')}" if best.get('backdrop_path') else "",
                }
    except Exception:
        pass
    return None

print(f"\n==================================================")
print(f"SMART TWO-WAY TMDB SCRAPER ON REAL TITLES")
print(f"==================================================")

for raw in raw_titles:
    print(f"\nRAW TITLE: '{raw}'")
    
    # Generate search candidates in priority order
    candidates = []
    if " - " in raw:
        parts = raw.split(" - ")
        candidates.append(parts[-1].strip())  # Stremio TV format: 'Episode - Show'
        candidates.append(parts[0].strip())   # Standard format: 'Show - Episode'
    
    # Strip season codes (S01E05, 1x05)
    clean = re.split(r"[-–—]|s\d{1,2}e\d{1,2}|\d{1,2}x\d{1,2}", raw, flags=re.IGNORECASE)[0].strip()
    if clean and clean not in candidates:
        candidates.append(clean)
    if raw not in candidates:
        candidates.append(raw)

    match = None
    winning_query = ""
    for candidate in candidates:
        res = search_tmdb(candidate)
        if res and res.get("poster"):
            match = res
            winning_query = candidate
            break

    if match:
        print(f"  ✓ MATCH FOUND via query '{winning_query}':")
        print(f"    [{match['type']}] {match['title']} ({match['year']})")
        print(f"    🖼️  {match['poster']}")
    else:
        print(f"  ℹ️ Non-theatrical content (YouTube/Podcast/Song) -> Uses live video thumbnail")

print(f"\n==================================================\n")