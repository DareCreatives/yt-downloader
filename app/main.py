from __future__ import annotations

import logging
from pathlib import Path

import aiofiles
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import __version__, downloader
from app.config import settings
from app.jobs import manager
from app.models import (
    DownloadRequest,
    JobCreatedResponse,
    JobInfo,
    JobStatus,
    VideoInfoResponse,
)
from app.utils import is_supported_url

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("yt-downloader")

app = FastAPI(title="YT Downloader", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.post("/api/info", response_model=VideoInfoResponse)
async def info(req: DownloadRequest) -> VideoInfoResponse:
    url = str(req.url)
    if not is_supported_url(url):
        raise HTTPException(400, "Only YouTube URLs are supported.")
    try:
        data = downloader.fetch_info(url)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Could not fetch video info: {e}") from e
    return VideoInfoResponse(**data)


@app.post("/api/download", response_model=JobCreatedResponse)
async def create_download(req: DownloadRequest) -> JobCreatedResponse:
    url = str(req.url)
    if not is_supported_url(url):
        raise HTTPException(400, "Only YouTube URLs are supported.")

    job = manager.create_job(url=url, fmt=req.format, quality=req.quality)
    return JobCreatedResponse(job_id=job.job_id, status=job.status)


@app.get("/api/job/{job_id}", response_model=JobInfo)
async def job_status(job_id: str) -> JobInfo:
    job = manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return job


@app.get("/api/file/{job_id}")
async def download_file(job_id: str, request: Request):
    path = manager.get_file_path(job_id)
    if not path:
        raise HTTPException(404, "File not ready or expired.")

    filename = path.name
    media_type = "audio/mpeg" if path.suffix == ".mp3" else "video/mp4"

    # Support HTTP Range requests for seeking / resumable downloads
    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        start, end = _parse_range(range_header, file_size)
        chunk_size = end - start + 1

        async def stream():
            async with aiofiles.open(path, "rb") as f:
                await f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    data = await f.read(min(1024 * 256, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        return StreamingResponse(stream(), status_code=206,
                                 media_type=media_type, headers=headers)

    return FileResponse(path, media_type=media_type, filename=filename)


def _parse_range(header: str, size: int) -> tuple[int, int]:
    try:
        units, _, rng = header.partition("=")
        if units.strip().lower() != "bytes":
            raise ValueError
        start_s, _, end_s = rng.partition("-")
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else size - 1
        end = min(end, size - 1)
        start = max(0, start)
        if start > end:
            raise ValueError
        return start, end
    except (ValueError, AttributeError):
        raise HTTPException(416, "Invalid Range header.")
