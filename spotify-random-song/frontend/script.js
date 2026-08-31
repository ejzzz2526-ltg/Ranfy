// Fetches one random song (optionally filtered by genre/era from the
// sidebar), renders the cover art and Spotify embed player, and recolors
// the page + card theme to roughly match the album cover's dominant color.

const API_ENDPOINT = "/api/random-song";

const randomBtn = document.getElementById("randomBtn");
const albumCover = document.getElementById("albumCover");
const coverPlaceholder = document.getElementById("coverPlaceholder");
const songTitle = document.getElementById("songTitle");
const artistName = document.getElementById("artistName");
const spotifyLink = document.getElementById("spotifyLink");
const embedWrapper = document.getElementById("embedWrapper");
const clearFiltersBtn = document.getElementById("clearFiltersBtn");

// --- Sidebar filter comboboxes ---

let selectedGenre = "";
let selectedYear = "";

function setupCombobox(root, onSelect) {
  const input = root.querySelector(".combobox__input");
  const list = root.querySelector(".combobox__list");
  const items = Array.from(list.querySelectorAll("li"));

  function openList() {
    list.hidden = false;
  }
  function closeList() {
    list.hidden = true;
  }
  function filterItems() {
    const q = input.value.trim().toLowerCase();
    items.forEach((li) => {
      const label = li.textContent.toLowerCase();
      li.hidden = Boolean(q) && !label.includes(q);
    });
  }

  input.addEventListener("focus", () => {
    filterItems();
    openList();
  });
  input.addEventListener("input", () => {
    filterItems();
    openList();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeList();
  });

  items.forEach((li) => {
    li.addEventListener("click", () => {
      input.value = li.dataset.value ? li.textContent : "";
      closeList();
      onSelect(li.dataset.value || "");
    });
  });

  document.addEventListener("click", (e) => {
    if (!root.contains(e.target)) closeList();
  });

  return {
    clear() {
      input.value = "";
    },
  };
}

const genreCombobox = setupCombobox(
  document.getElementById("genreCombobox"),
  (value) => {
    selectedGenre = value;
  }
);

const yearCombobox = setupCombobox(
  document.getElementById("yearCombobox"),
  (value) => {
    selectedYear = value;
  }
);

clearFiltersBtn.addEventListener("click", () => {
  genreCombobox.clear();
  yearCombobox.clear();
  selectedGenre = "";
  selectedYear = "";
});

// --- Fetching and rendering a random song ---

async function loadRandomSong() {
  setLoading(true);

  try {
    const params = new URLSearchParams();
    if (selectedGenre) params.set("genre", selectedGenre);
    if (selectedYear) params.set("year", selectedYear);
    const url = params.toString() ? `${API_ENDPOINT}?${params}` : API_ENDPOINT;

    const response = await fetch(url);

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

  spotifyLink.href = song.spotify_url;
  spotifyLink.hidden = false;

  embedWrapper.innerHTML = "";
  const iframe = document.createElement("iframe");
  iframe.className = "embed-wrapper__iframe";
  iframe.width = "100%";
  iframe.height = "80";
  iframe.frameBorder = "0";
  iframe.loading = "lazy";
  iframe.allow = "autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture";
  iframe.src = `https://open.spotify.com/embed/track/${song.track_id}`;
  embedWrapper.appendChild(iframe);
  embedWrapper.hidden = false;

  if (song.album_cover) {
    applyThemeFromImage(song.album_cover);
  }
}

function renderError() {
  albumCover.hidden = true;
  coverPlaceholder.hidden = false;
  songTitle.textContent = "Couldn't load a song";
  artistName.textContent = "Try again, or try different filters.";
  spotifyLink.hidden = true;
  embedWrapper.hidden = true;
  embedWrapper.innerHTML = "";
}

function setLoading(isLoading) {
  randomBtn.disabled = isLoading;
  randomBtn.textContent = isLoading ? "Finding a song…" : "Random Song";
}

randomBtn.addEventListener("click", loadRandomSong);

// --- Cover-art dominant-color theming ---

function applyThemeFromImage(imageUrl) {
  const img = new Image();
  img.crossOrigin = "anonymous";

  img.onload = () => {
    try {
      const rgb = getDominantColor(img);
      const theme = buildThemeFromColor(rgb);
      applyTheme(theme);
    } catch (err) {
      console.warn("Could not extract theme color:", err);
    }
  };

  img.onerror = () => {};
  img.src = imageUrl;
}

function getDominantColor(img) {
  const size = 100;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0, size, size);

  const { data } = ctx.getImageData(0, 0, size, size);

  const step = 32;
  const buckets = new Map();

  for (let i = 0; i < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    const alpha = data[i + 3];

    if (alpha < 125) continue;

    const brightness = (r + g + b) / 3;
    if (brightness > 245 || brightness < 12) continue;

    const key = `${Math.floor(r / step)}-${Math.floor(g / step)}-${Math.floor(b / step)}`;

    if (!buckets.has(key)) {
      buckets.set(key, { count: 0, rSum: 0, gSum: 0, bSum: 0 });
    }
    const bucket = buckets.get(key);
    bucket.count++;
    bucket.rSum += r;
    bucket.gSum += g;
    bucket.bSum += b;
  }

  let best = null;
  for (const bucket of buckets.values()) {
    if (!best || bucket.count > best.count) best = bucket;
  }

  if (!best) {
    let r = 0, g = 0, b = 0, count = 0;
    for (let i = 0; i < data.length; i += 4) {
      r += data[i];
      g += data[i + 1];
      b += data[i + 2];
      count++;
    }
    return { r: r / count, g: g / count, b: b / count };
  }

  return {
    r: best.rSum / best.count,
    g: best.gSum / best.count,
    b: best.bSum / best.count,
  };
}

function buildThemeFromColor({ r, g, b }) {
  const bg = mix({ r, g, b }, { r: 255, g: 255, b: 255 }, 0.78);
  const cardBg = mix({ r, g, b }, { r: 255, g: 255, b: 255 }, 0.92);

  let navy = { r, g, b };
  let guard = 0;
  while (luminance(navy) > 90 && guard < 8) {
    navy = { r: navy.r * 0.75, g: navy.g * 0.75, b: navy.b * 0.75 };
    guard++;
  }

  const navyMid = mix(navy, { r, g, b }, 0.35);
  const navySoft = mix(navy, { r: 255, g: 255, b: 255 }, 0.35);
  const shadowDark = mix(bg, { r: 0, g: 0, b: 0 }, 0.15);

  return {
    bg: toHex(bg),
    cardBg: toHex(cardBg),
    navy: toHex(navy),
    navyMid: toHex(navyMid),
    navySoft: toHex(navySoft),
    shadowDark: toHex(shadowDark),
  };
}

function applyTheme(theme) {
  const root = document.documentElement.style;
  root.setProperty("--bg", theme.bg);
  root.setProperty("--card-bg", theme.cardBg);
  root.setProperty("--navy", theme.navy);
  root.setProperty("--navy-mid", theme.navyMid);
  root.setProperty("--navy-soft", theme.navySoft);
  root.setProperty("--shadow-dark", theme.shadowDark);
}

function mix(colorA, colorB, weightB) {
  return {
    r: colorA.r * (1 - weightB) + colorB.r * weightB,
    g: colorA.g * (1 - weightB) + colorB.g * weightB,
    b: colorA.b * (1 - weightB) + colorB.b * weightB,
  };
}

function luminance({ r, g, b }) {
  return 0.299 * r + 0.587 * g + 0.114 * b;
}

function toHex({ r, g, b }) {
  const clamp = (v) => Math.max(0, Math.min(255, Math.round(v)));
  const hex = (v) => clamp(v).toString(16).padStart(2, "0");
  return `#${hex(r)}${hex(g)}${hex(b)}`;
}