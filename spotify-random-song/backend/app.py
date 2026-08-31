"""
app.py

Flask backend that calls the Spotify Web API live, on every request.
No database, no local storage of Spotify Content.

Flow per request to GET /api/random-song:
    1. Get a valid Client Credentials access token (reused in memory until
       it's close to expiring, then refreshed).
    2. If the request includes ?genre= and/or ?year= query params, build a
       targeted search query from those (genre is matched as an actual
       genre field via genre:"..." syntax, not a plain keyword). Otherwise,
       pick a random search query from SPOTIFY_SEARCH_QUERIES (fully
       random, as before).
    3. Probe the query to find its real result count, then pick a random
       offset guaranteed to be within that range (prevents narrow filters
       from landing past the end of the result set and coming back empty).
    4. Pick one random track out of the returned results.
    5. Return its metadata (including track_id, used to build the embed
       player) directly to the frontend. Nothing is saved.
"""

import os
import random
import time

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from pathlib import Path

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SEARCH_QUERIES = [
    q.strip() for q in os.getenv("SPOTIFY_SEARCH_QUERIES", "").split(",") if q.strip()
]

MAX_OFFSET = int(os.getenv("SPOTIFY_MAX_OFFSET", "190"))
RESULTS_PER_PAGE = 10

TOKEN_URL = "https://accounts.spotify.com/api/token"
SEARCH_URL = "https://api.spotify.com/v1/search"

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")

_token_cache = {"access_token": None, "expires_at": 0}


def get_access_token() -> str:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError(
            "Missing SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET environment variables."
        )

    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    resp = requests.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(CLIENT_ID, CLIENT_SECRET),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)
    return _token_cache["access_token"]


def extract_metadata(track: dict):
    try:
        images = track["album"]["images"]
        cover_url = images[0]["url"] if images else None
        if not cover_url:
            return None

        return {
            "track_id": track["id"],
            "title": track["name"],
            "artist": ", ".join(a["name"] for a in track["artists"]),
            "album": track["album"]["name"],
            "album_cover": cover_url,
            "spotify_url": track["external_urls"]["spotify"],
        }
    except (KeyError, IndexError, TypeError):
        return None


def spotify_search(query: str, offset: int, headers: dict) -> tuple[dict, dict]:
    """One search call. Returns (response_json, possibly-refreshed headers)."""
    params = {
        "q": query,
        "type": "track",
        "limit": RESULTS_PER_PAGE,
        "offset": offset,
    }

    resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=10)

    if resp.status_code == 401:
        _token_cache["access_token"] = None
        new_token = get_access_token()
        headers = {"Authorization": f"Bearer {new_token}"}
        resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=10)

    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", "1"))
        time.sleep(min(retry_after, 3))
        resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=10)

    resp.raise_for_status()
    return resp.json(), headers


def fetch_random_track(max_attempts: int = 4, override_query: str | None = None):
    if not override_query and not SEARCH_QUERIES:
        raise RuntimeError(
            "No search queries configured. Set SPOTIFY_SEARCH_QUERIES in your "
            "environment, e.g.: pop,rock,hip hop,year:2024,indie"
        )

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    for attempt in range(max_attempts):
        query = override_query if override_query else random.choice(SEARCH_QUERIES)

        # Step 1: probe with offset=0 to learn how many results this exact
        # query actually has. This prevents narrow filters (e.g. a precise
        # genre match, or a single decade with no genre) from randomly
        # requesting an offset past the end of the real result set, which
        # Spotify just returns as empty.
        probe_data, headers = spotify_search(query, offset=0, headers=headers)
        total = probe_data.get("tracks", {}).get("total", 0)

        if total == 0:
            continue  # this query genuinely has no results, try again

        # Step 2: pick a random offset guaranteed to be within the real
        # result count, capped at MAX_OFFSET for broad queries so we don't
        # page absurdly deep into huge result sets.
        highest_valid_offset = max(0, min(MAX_OFFSET, total - RESULTS_PER_PAGE))
        highest_valid_offset -= highest_valid_offset % RESULTS_PER_PAGE

        if highest_valid_offset == 0:
            tracks = probe_data.get("tracks", {}).get("items", [])
        else:
            offset = random.randrange(0, highest_valid_offset + 1, RESULTS_PER_PAGE)
            data, headers = spotify_search(query, offset=offset, headers=headers)
            tracks = data.get("tracks", {}).get("items", [])

        if not tracks:
            continue

        candidate = extract_metadata(random.choice(tracks))
        if candidate:
            return candidate

    return None


@app.get("/api/random-song")
def random_song():
    # Optional filters from the sidebar. Length-capped as a basic safety guard.
    genre = request.args.get("genre", "").strip()[:40]
    year = request.args.get("year", "").strip()[:20]

    def build_query(use_genre_filter: bool) -> str | None:
        parts = []
        if genre:
            # genre:"..." tells Spotify's search to match the genre field
            # specifically, instead of treating e.g. "house" as a plain
            # keyword that happens to match song/album titles containing
            # that word (which was causing results like "House of Balloons").
            parts.append(f'genre:"{genre}"' if use_genre_filter else genre)
        if year:
            parts.append(f"year:{year}")
        return " ".join(parts) if parts else None

    try:
        # Try the precise genre-field filter first.
        song = fetch_random_track(override_query=build_query(use_genre_filter=True))

        # Some niche genre tags have very few or zero exact matches in
        # Spotify's catalog. If the precise filter comes up empty, fall
        # back to plain keyword search rather than showing an error —
        # broader results are better than none, and this only triggers
        # for genres too narrow to return anything on their own.
        if song is None and genre:
            song = fetch_random_track(override_query=build_query(use_genre_filter=False))
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except requests.HTTPError as e:
        return jsonify({"error": f"Spotify API error: {e}"}), 502

    if song is None:
        return jsonify({"error": "Could not find a track, try again."}), 404

    return jsonify(song)


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)