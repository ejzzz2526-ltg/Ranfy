// Minimal frontend logic: fetch one random song from the backend and
// render it. No other functionality by design.

const API_ENDPOINT = "/api/random-song";

const randomBtn = document.getElementById("randomBtn");
const albumCover = document.getElementById("albumCover");
const coverPlaceholder = document.getElementById("coverPlaceholder");
const songTitle = document.getElementById("songTitle");
const artistName = document.getElementById("artistName");
const spotifyLink = document.getElementById("spotifyLink");

async function loadRandomSong() {
  setLoading(true);

  try {
    const response = await fetch(API_ENDPOINT);

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    const song = await response.json();
    renderSong(song);
  } catch (err) {
    renderError();
    console.error("Failed to load random song:", err);
  } finally {
    setLoading(false);
  }
}

function renderSong(song) {
  albumCover.src = song.album_cover;
  albumCover.alt = `Album cover for ${song.album}`;
  albumCover.hidden = false;
  coverPlaceholder.hidden = true;

  songTitle.textContent = song.title;
  artistName.textContent = song.artist;
  const embedWrapper = document.getElementById("embedWrapper");
  const embedPlayer = document.getElementById("embedPlayer");
  embedPlayer.src = `https://open.spotify.com/embed/track/${song.track_id}`;
  embedWrapper.hidden = false;

  spotifyLink.href = song.spotify_url;
  spotifyLink.hidden = false;
}

function renderError() {
  albumCover.hidden = true;
  coverPlaceholder.hidden = false;
  songTitle.textContent = "Couldn't load a song";
  artistName.textContent = "Try again in a moment.";
  spotifyLink.hidden = true;
  document.getElementById("embedWrapper").hidden = true;
}

function setLoading(isLoading) {
  randomBtn.disabled = isLoading;
  randomBtn.textContent = isLoading ? "Finding a song…" : "Random Song";
}

randomBtn.addEventListener("click", loadRandomSong);
