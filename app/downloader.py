import os, tempfile

def _get_cookie_file():
    cookie_content = os.getenv("YT_COOKIES")
    if not cookie_content:
        return None
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    f.write(cookie_content)
    f.close()
    return f.name
"""Wrapper around yt-dlp used by the job manager."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import yt_dlp

from app.config import settings

logger = logging.getLogger(__name__)


QUALITY_MAP = {
    "best": "bestvideo+bestaudio/best",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360": "bestvideo[height<=360]+bestaudio/best[height<=360]",
}


def _base_opts() -> dict:
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,          # only single video, not entire channels
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "restrictfilenames": True,    # safe filenames
    }
    if settings.cookies_file and Path(settings.cookies_file).is_file():
        opts["cookiefile"] = settings.cookies_file
    return opts


def _build_opts(
    job_id: str,
    fmt: str,
    quality: str,
    progress_hook: Callable[[dict], None],
) -> dict:
    out_dir = settings.download_dir / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    opts = _base_opts()
    opts["progress_hooks"] = [progress_hook]
    opts["outtmpl"] = str(out_dir / "%(title).150B-%(id)s.%(ext)s")

    if fmt == "mp3":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        opts["format"] = QUALITY_MAP.get(quality, QUALITY_MAP["best"])
        opts["merge_output_format"] = "mp4"

    return opts


def fetch_info(url: str) -> dict:
    """Fetch metadata without downloading (used for /info endpoint)."""
    opts = _base_opts()
    opts["skip_download"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "uploader": info.get("uploader"),
        "formats": [
            {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "resolution": f.get("resolution"),
                "filesize": f.get("filesize"),
                "note": f.get("format_note"),
            }
            for f in info.get("formats", [])
        ][:30],
    }


def download(url: str, job_id: str, fmt: str, quality: str,
             progress_hook: Callable[[dict], None]) -> Path:
    """Run the download; return the path to the produced file."""
    opts = _build_opts(job_id, fmt, quality, progress_hook)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # Resolve the actual output path via yt-dlp's own logic
    if fmt == "mp3":
        filepath = Path(ydl.prepare_filename(info)).with_suffix(".mp3")
    else:
        filepath = Path(ydl.prepare_filename(info))
        # merge_output_format may change extension
        if not filepath.exists() and filepath.suffix != ".mp4":
            mp4_candidate = filepath.with_suffix(".mp4")
            if mp4_candidate.exists():
                filepath = mp4_candidate

    if not filepath.exists():
        # Fallback: find whatever yt-dlp dropped in the job dir
        candidates = list((settings.download_dir / job_id).glob("*"))
        candidates = [c for c in candidates if c.is_file()]
        if not candidates:
            raise RuntimeError("Download finished but no file was produced.")
        filepath = max(candidates, key=lambda p: p.stat().st_size)

    return filepath
