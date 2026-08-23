# Spin — Random Spotify Song

A minimal website that shows one random song (album cover, title, artist, and
a "Listen on Spotify" link) each time you press a button. Built to be fast,
cheap to run, and ready for Google AdSense.

## How it works

```
Spotify API
      ↓
app.py (Flask)  →  GET /api/random-song
      ↓
frontend (HTML/CSS/JS)
```

The website calls the Spotify API directly. Each button click just
asks the backend for a random song.

## Project structure

```
spotify-random-song/
├── backend/
│   ├── app.py              # Flask API + serves the frontend
│   ├── requirements.txt
│   └── .env.example         # Copy to .env and fill in
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── README.md
```

## 1. Get Spotify API credentials

1. Go to https://developer.spotify.com/dashboard and log in.
2. Click **Create app**. Fill in a name/description; you don't need a redirect
   URI for this project since it only uses the Client Credentials flow
   (app-only auth, no user login).
3. Copy the **Client ID** and **Client Secret**.

## 2. Local setup

```bash
cd spotify-random-song/backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and fill in:
#   SPOTIFY_CLIENT_ID
#   SPOTIFY_CLIENT_SECRET
#   SPOTIFY_PLAYLIST_IDS   (comma-separated public playlist IDs to pull tracks from)
```


```



## 3. Run the site locally

```bash
python app.py
```

Visit http://localhost:5000 — click **Random Song**.

## 5. Deploying

This is a small Flask app, so it runs well on any
low-cost host that supports Python (e.g. a small VM, Render, Railway, Fly.io,
PythonAnywhere).

Production run command (do not use `python app.py` / Flask's dev server in
production):

```bash
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:8000 app:app
```

Deployment checklist:

- Set `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` as environment variables
  on your host (don't upload your `.env` file).
- Run `init_db.py` once on the server, then `import_songs.py` to populate
  `songs.db`. Re-run `import_songs.py` periodically (e.g. a weekly cron job)
  to refresh the catalog — this never affects the live site's uptime since
  it writes to the database independently of the running web process.
- Put a reverse proxy (nginx, or your host's built-in one) in front of
  gunicorn for TLS/HTTPS.
- `songs.db` should be on persistent storage — if your host uses ephemeral
  filesystems (e.g. some serverless platforms), point `DB_PATH` at a mounted
  volume, or use a managed SQLite service (e.g. Turso/LiteFS) instead.

## Google AdSense

Two empty, clearly-labeled ad slots are already reserved in the layout
(`.ad-slot--top` above the card, `.ad-slot--bottom` below it) so ad units can
be dropped in later without changing the page structure. No AdSense script is
included yet, as requested — add your AdSense snippet and ad unit code
into those containers when you're ready to monetize.

## Spotify developer policy notes

- Album art is always loaded directly from the URL Spotify's API returns
  (`i.scdn.co`) — it is never downloaded or re-hosted.
- Every song links directly back to the track on Spotify ("Listen on
  Spotify"), and the page credits Spotify as the data/attribution source.
- The Client Credentials flow is used for the import script, which is
  app-only auth with no access to any user's personal data — there's no
  login, account, or user data collection anywhere in this project.
