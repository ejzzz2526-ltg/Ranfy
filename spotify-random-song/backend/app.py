"""
app.py

Flask backend that calls the Spotify Web API live, on every request.
No database, no local storage of Spotify Content.

Flow per request to GET /api/random-song:
    1. Get a valid Client Credentials access token (reused in memory until
       it's close to expiring, then refreshed).
    2. Pick a random search query from SPOTIFY_SEARCH_QUERIES and a random
       offset, call Spotify's Search endpoint.
    3. Pick one random track out of the returned results.
    4. Return its metadata (including track_id, used to build the embed
       player) directly to the frontend. Nothing is saved.
"""

import os
import random
import time

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, send_from_directory
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


def fetch_random_track(max_attempts: int = 4):
    if not SEARCH_QUERIES:
        raise RuntimeError(
            "No search queries configured. Set SPOTIFY_SEARCH_QUERIES in your "
            "environment, e.g.: pop,rock,hip hop,year:2024,indie"
        )

    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    for attempt in range(max_attempts):
        query = random.choice(SEARCH_QUERIES)
        offset = random.randrange(0, MAX_OFFSET + 1, RESULTS_PER_PAGE)

        params = {
            "q": query,
            "type": "track",
            "limit": RESULTS_PER_PAGE,
            "offset": offset,
        }

        resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=10)

        if resp.status_code == 401:
            _token_cache["access_token"] = None
            token = get_access_token()
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=10)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "1"))
            time.sleep(min(retry_after, 3))
            continue

        resp.raise_for_status()
        tracks = resp.json().get("tracks", {}).get("items", [])
        if not tracks:
            continue

        candidate = extract_metadata(random.choice(tracks))
        if candidate:
            return candidate

    return None


@app.get("/api/random-song")
def random_song():
    try:
        song = fetch_random_track()
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