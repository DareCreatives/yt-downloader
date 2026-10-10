# YT Downloader

A clean, self-hosted YouTube downloader. No ads, no fake download buttons,
no redirects to sketchy sites. Just a URL box and a file.

Powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp) + FastAPI.

## Features

- Download best-quality video (up to whatever YouTube serves) or MP3 audio
- Real progress bar (job polling, not fake spinners)
- Resumable downloads (HTTP Range support)
- Auto-cleanup of files after 1 hour
- Single-file frontend, no build step
- Docker-ready

## Requirements

- Python 3.11+ **or** Docker
- `ffmpeg` installed on the host (needed to merge video + audio and to
  extract MP3). On macOS: `brew install ffmpeg`. On Debian/Ubuntu:
  `sudo apt install ffmpeg`.

## Quick start (local)

```bash
git clone https://github.com/yourname/yt-downloader.git
cd yt-downloader

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python run.py
```

Open http://localhost:8000

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

## Configuration

All settings are read from `.env` (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | HTTP port |
| `DEBUG` | `false` | Enable hot reload + debug logs |
| `DOWNLOAD_DIR` | `./downloads` | Where files are written |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | Parallel downloads |
| `FILE_TTL_SECONDS` | `3600` | Delete finished files after this |
| `COOKIES_FILE` | *(none)* | Path to a Netscape-format `cookies.txt` |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |

### Age-restricted or login-only videos

Export cookies from your browser using a "Get cookies.txt" extension,
save as `cookies.txt` in the project root, then set:

```
COOKIES_FILE=./cookies.txt
```

## API

| Method | Path | Description |
|---|---|---|
| `GET`  | `/api/health` | Health check |
| `POST` | `/api/info` | Fetch metadata for a URL |
| `POST` | `/api/download
