"""Simple in-memory job manager with a thread pool.

Swap this for Celery/RQ + Redis if you need persistence or multi-worker scale.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from app import downloader
from app.config import settings
from app.models import JobInfo, JobStatus

logger = logging.getLogger(__name__)


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobInfo] = {}
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_downloads,
            thread_name_prefix="yt-dl",
        )
        self._start_cleanup_thread()

    # ---------- public API ----------

    def create_job(self, url: str, fmt: str, quality: str) -> JobInfo:
        job_id = uuid.uuid4().hex
        now = time.time()
        job = JobInfo(
            job_id=job_id,
            status=JobStatus.QUEUED,
            url=url,
            format=fmt,
            quality=quality,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job_id] = job

        self._executor.submit(self._run, job_id)
        return job

    def get_job(self, job_id: str) -> Optional[JobInfo]:
        with self._lock:
            return self._jobs.get(job_id)

    def get_file_path(self, job_id: str) -> Optional[Path]:
        job = self.get_job(job_id)
        if not job or job.status != JobStatus.COMPLETED or not job.filename:
            return None
        path = settings.download_dir / job_id / job.filename
        return path if path.is_file() else None

    # ---------- internals ----------

    def _update(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for k, v in fields.items():
                setattr(job, k, v)
            job.updated_at = time.time()

    def _progress_hook(self, job_id: str):
        def hook(d: dict) -> None:
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                progress = (downloaded / total * 100.0) if total else 0.0
                self._update(
                    job_id,
                    status=JobStatus.DOWNLOADING,
                    progress=round(progress, 2),
                    title=d.get("info_dict", {}).get("title"),
                )
            elif d.get("status") == "finished":
                self._update(job_id, progress=99.0)
        return hook

    def _run(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        try:
            self._update(job_id, status=JobStatus.DOWNLOADING)
            filepath = downloader.download(
                url=job.url,
                job_id=job_id,
                fmt=job.format,
                quality=job.quality,
                progress_hook=self._progress_hook(job_id),
            )
            self._update(
                job_id,
                status=JobStatus.COMPLETED,
                progress=100.0,
                filename=filepath.name,
                filesize=filepath.stat().st_size,
            )
            logger.info("Job %s completed: %s", job_id, filepath.name)
        except Exception as e:  # noqa: BLE001
            logger.exception("Job %s failed", job_id)
            self._update(job_id, status=JobStatus.FAILED, error=str(e)[:500])

    # ---------- housekeeping ----------

    def _start_cleanup_thread(self) -> None:
        def loop() -> None:
            while True:
                time.sleep(60)
                self._cleanup()

        t = threading.Thread(target=loop, daemon=True, name="yt-dl-cleanup")
        t.start()

    def _cleanup(self) -> None:
        """Delete finished jobs + their files after TTL."""
        cutoff = time.time() - settings.file_ttl_seconds
        to_remove: list[str] = []
        with self._lock:
            for job_id, job in self._jobs.items():
                if job.status in (JobStatus.COMPLETED, JobStatus.FAILED) and job.updated_at < cutoff:
                    to_remove.append(job_id)
            for job_id in to_remove:
                self._jobs.pop(job_id, None)

        for job_id in to_remove:
            job_dir = settings.download_dir / job_id
            if job_dir.is_dir():
                for f in job_dir.iterdir():
                    try:
                        f.unlink()
                    except OSError:
                        pass
                try:
                    job_dir.rmdir()
                except OSError:
                    pass


manager = JobManager()
