# Bulk Video Downloader

A cross-platform GUI application for downloading videos from YouTube, Vimeo, Twitter/X, Reddit, and **1800+ sites** using [yt-dlp](https://github.com/yt-dlp/yt-dlp).

Works on **Windows**, **Linux**, and **macOS**.

---

## Features

- **Bulk download** — Add multiple URLs and download them all in one click
- **7 download modes** — Best quality, audio-only (MP3/native), video-only, 720p/1080p/4K caps
- **Per-URL progress** — See real-time download percentage for each URL
- **Overall progress bar** — Track how many URLs have been processed
- **Color-coded status** — Green (done), red (failed), yellow (downloading)
- **Live output log** — See yt-dlp output in real-time with color-coded messages
- **Auto-retry** — Failed downloads retry automatically (configurable attempts)
- **Download archive** — Skip already-downloaded videos on re-runs
- **URL deduplication** — Duplicate URLs are detected and skipped
- **Import from file** — Load URLs from a text file (supports comments with `#`)
- **Paste from clipboard** — Paste multiple URLs at once
- **Configurable settings** — Rate limit, proxy, subtitle language, container format, and more
- **Settings persistence** — All settings saved to `config.json`
- **Update yt-dlp** — One-click update button built in
- **Save logs** — Export the output log to a file
- **Native UI** — Uses system theme (Windows native on Windows, clean look on Linux/macOS)

---

## Requirements

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.8+ | Runtime |
| **yt-dlp** | Latest | Video downloading engine |
| **ffmpeg** | Latest | Merging video+audio, post-processing |
| **ffprobe** | Latest | Media info (usually comes with ffmpeg) |

---

## Installation

### 1. Install Python

- **Windows**: Download from [python.org](https://www.python.org/downloads/) — check "Add to PATH" during install
- **Linux**: Usually pre-installed. If not: `sudo apt install python3 python3-tk`
- **macOS**: `brew install python` or download from python.org

### 2. Install yt-dlp

```bash
pip install yt-dlp
```

Or with pipx (recommended for isolation):
```bash
pipx install yt-dlp
```

### 3. Install ffmpeg

- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) or use:
  ```
  winget install ffmpeg
  ```
- **Linux**:
  ```bash
  sudo apt install ffmpeg
  ```
- **macOS**:
  ```bash
  brew install ffmpeg
  ```

### 4. Install tkinter (Linux only, if needed)

Most systems have it pre-installed. If you get a `ModuleNotFoundError`:
```bash
sudo apt install python3-tk
```

---

## Usage

### Running the app

```bash
# Linux / macOS
python3 bulk_video_downloader.py

# Windows
python bulk_video_downloader.py
```

### Adding URLs

You have 3 ways to add URLs:

1. **+ Add URL** — Type or paste a single URL
2. **Paste URLs** — Paste multiple URLs from your clipboard (one per line)
3. **Import File** — Load URLs from a `.txt` file

#### File format for Import

```text
# My video list (lines starting with # are comments)
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://vimeo.com/123456789
https://twitter.com/user/status/123456789

# JSON array format is also supported:
[
  "https://www.youtube.com/watch?v=abc123",
  "https://www.youtube.com/watch?v=def456"
]
```

### Downloading

1. Add your URLs
2. Select a **Mode** (download quality/format)
3. Choose an **Output** folder (defaults to `./downloads`)
4. Click **Start Download**
5. Watch the progress in the URL list and Live Output panel

### Download Modes

| Mode | Description |
|------|-------------|
| Best video + audio | Highest quality video + audio merged (default) |
| Audio only (MP3) | Extracts audio and converts to MP3 (320kbps) |
| Audio only (native codec) | Keeps original audio codec (opus/m4a), no re-encoding |
| Video only (no audio) | Downloads video stream only |
| 720p max | Best quality up to 720p |
| 1080p max | Best quality up to 1080p |
| 4K max | Best quality up to 2160p |

---

## Settings

Click the **Settings** tab to configure. Settings are saved to `config.json` when you click "Save Settings".

### Download

| Setting | Description | Default |
|---------|-------------|---------|
| Retries | Number of retry attempts per URL on failure | 3 |
| Rate limit | Bandwidth cap (e.g. `5M` = 5 MB/s, `500K` = 500 KB/s) | unlimited |
| Container format | Output format for merged video (mp4, mkv, webm) | mp4 |

### Network

| Setting | Description | Default |
|---------|-------------|---------|
| Proxy | HTTP/SOCKS proxy (e.g. `socks5://127.0.0.1:1080`) | none |

### Embedding

| Setting | Description | Default |
|---------|-------------|---------|
| Embed subtitles | Download and embed subtitles into the file | On |
| Subtitle languages | Language codes (e.g. `en`, `en,es,fr`) | en |
| Embed thumbnail | Embed video thumbnail as cover art | On |
| Embed metadata | Embed title, artist, date, etc. | On |
| Embed chapters | Embed video chapters if available | On |

### Behavior

| Setting | Description | Default |
|---------|-------------|---------|
| Use download archive | Track downloaded IDs to skip on re-runs | On |
| Single video only | Ignore playlists, download single video | On |

### Advanced

| Setting | Description | Default |
|---------|-------------|---------|
| Extra yt-dlp arguments | Any additional yt-dlp flags (space-separated) | empty |

---

## Files Created

| File | Purpose |
|------|---------|
| `config.json` | Your saved settings |
| `download_archive.txt` | List of already-downloaded video IDs (prevents re-downloading) |
| `downloads/` | Default output folder for downloaded videos |

---

## Tips & Tricks

### Download with cookies (for age-restricted or private videos)

1. Export cookies from your browser using a browser extension (e.g. "Get cookies.txt LOCALLY")
2. Save as `cookies.txt` in the same folder
3. In Settings > Advanced > Extra yt-dlp arguments, add:
   ```
   --cookies cookies.txt
   ```

### Geo-restricted content

Add to Extra yt-dlp arguments:
```
--geo-bypass
```

### Download with specific subtitles

Change "Subtitle languages" in Settings to:
```
en,es,fr,ja
```
This downloads English, Spanish, French, and Japanese subtitles.

### Download entire playlists

1. Uncheck "Single video only (no playlists)" in Settings
2. Paste the playlist URL

### Use with a VPN/proxy

Set the proxy in Settings > Network:
```
socks5://127.0.0.1:1080
http://user:pass@proxy.example.com:8080
```

### Limit download speed

Set rate limit in Settings > Download:
```
5M      → 5 megabytes/second
500K    → 500 kilobytes/second
2.5M    → 2.5 megabytes/second
```

---

## Troubleshooting

### "yt-dlp not found"
Make sure yt-dlp is installed and in your PATH:
```bash
pip install yt-dlp
yt-dlp --version
```

### "ffmpeg not found"
Install ffmpeg and ensure it's in your PATH:
```bash
ffmpeg -version
```

### Downloads fail with "403 Forbidden"
Try updating yt-dlp (click "Update yt-dlp" button) or use cookies.

### "No module named _tkinter" (Linux)
```bash
sudo apt install python3-tk
```

### GUI looks different on Linux
The app uses native system theme. On Linux it uses the "clam" ttk theme which provides a clean cross-platform appearance.

---

## Updating yt-dlp

Click the **"Update yt-dlp"** button in the Downloads tab, or run manually:
```bash
pip install -U yt-dlp
```

Keep yt-dlp updated — sites frequently change their APIs.

---

## Supported Sites

yt-dlp supports **1800+ sites** including:
- YouTube (videos, shorts, playlists, channels)
- Vimeo
- Twitter/X
- Reddit
- Instagram
- TikTok
- Twitch (VODs, clips)
- Facebook
- Dailymotion
- SoundCloud
- Bandcamp
- And many more...

Full list: [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

---

## License

This project is provided as-is for personal use. Please respect copyright laws and the terms of service of the websites you download from.

---

## Credits

- Original concept by [EDM115](https://github.com/EDM115)
- GUI edition by officialputuid
- Powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ffmpeg](https://ffmpeg.org/)
