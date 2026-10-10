from enum import Enum
from typing import Optional
from pydantic import BaseModel, HttpUrl, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


class DownloadRequest(BaseModel):
    url: HttpUrl
    format: str = Field(default="mp4", pattern="^(mp4|mp3)$")
    quality: str = Field(default="best", pattern="^(best|1080|720|480|360)$")


class JobInfo(BaseModel):
    job_id: str
    status: JobStatus
    url: str
    format: str
    quality: str
    progress: float = 0.0
    title: Optional[str] = None
    filename: Optional[str] = None
    filesize: Optional[int] = None
    error: Optional[str] = None
    created_at: float
    updated_at: float


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus


class VideoInfoResponse(BaseModel):
    title: str
    duration: Optional[int]
    thumbnail: Optional[str]
    uploader: Optional[str]
    formats: list[dict]
