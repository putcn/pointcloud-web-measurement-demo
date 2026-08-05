"""FastAPI backend for asynchronous server-side mesh reconstruction."""
from __future__ import annotations

import logging
import os
import re
import uuid
from enum import Enum
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Directory that holds per-job sub-folders; created at startup
JOBS_DIR = Path(os.environ.get("JOBS_DIR", "/tmp/pointcloud_jobs"))
JOBS_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "200")) * 1_024 * 1_024

# CORS origins – allow only localhost ports in development
_CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
_ALLOWED_ORIGINS = [o.strip() for o in _CORS_ORIGINS.split(",") if o.strip()]

# Pattern that matches only the hex job IDs we generate (uuid4().hex → 32 hex chars)
_JOB_ID_RE = re.compile(r'^[0-9a-f]{32}$')


def _safe_job_dir(job_id: str) -> Path:
    """Return the job directory for *job_id* after validating the format.

    Raises HTTPException 400 if *job_id* does not match the expected pattern,
    preventing path traversal via crafted job IDs.
    """
    if not _JOB_ID_RE.match(job_id):
        raise HTTPException(status_code=400, detail="无效的 job_id 格式")
    return JOBS_DIR / job_id

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="PointCloud Mesh API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory job store (sufficient for single-worker demo)
# ---------------------------------------------------------------------------


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0  # 0-100
    error: str | None = None
    # Stored as string so Pydantic can serialise it; never exposed in API responses
    _glb_path: str = ""

    model_config = {"populate_by_name": True}


# job_id -> Job
_jobs: dict[str, Job] = {}
# Separate trusted path store – never derived from user input in request handlers
_job_glb_paths: dict[str, Path] = {}


# ---------------------------------------------------------------------------
# Background reconstruction task
# ---------------------------------------------------------------------------


def _run_reconstruction(job_id: str, ply_path: Path, glb_path: Path) -> None:
    job = _jobs[job_id]
    job.status = JobStatus.PROCESSING
    job.progress = 10
    try:
        from reconstruct import reconstruct  # local module

        reconstruct(ply_path, glb_path)
        job.status = JobStatus.COMPLETED
        job.progress = 100
        log.info("Job %s completed", job_id)
    except Exception as exc:  # noqa: BLE001
        job.status = JobStatus.FAILED
        job.error = str(exc)
        log.exception("Job %s failed", job_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/jobs", status_code=202)
async def upload_ply(file: UploadFile, background_tasks: BackgroundTasks) -> dict:
    """Upload a PLY file and enqueue mesh reconstruction.

    Returns a job id that can be polled with GET /api/jobs/{job_id}.
    """
    # Validate extension
    filename = file.filename or ""
    if not filename.lower().endswith(".ply"):
        raise HTTPException(status_code=400, detail="只接受 .ply 文件")

    # Read with size guard
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大，最大允许 {MAX_UPLOAD_BYTES // 1_048_576} MB",
        )

    # Isolate by job id
    job_id = uuid.uuid4().hex
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    ply_path = job_dir / "input.ply"
    glb_path = job_dir / "mesh.glb"
    ply_path.write_bytes(data)

    job = Job(job_id=job_id)
    _jobs[job_id] = job
    _job_glb_paths[job_id] = glb_path  # trusted path, never derived from request data again

    background_tasks.add_task(_run_reconstruction, job_id, ply_path, glb_path)

    return {"job_id": job_id, "status": job.status}


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str) -> Job:
    """Return current status and progress for a job."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job 不存在")
    return job


@app.get("/api/jobs/{job_id}/mesh")
async def get_mesh(job_id: str) -> FileResponse:
    """Download the reconstructed GLB mesh for a completed job."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job 不存在")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Mesh 尚未就绪")
    # Use the trusted path stored at upload time – never re-derived from job_id
    glb_path = _job_glb_paths.get(job_id)
    if glb_path is None or not glb_path.is_file():
        raise HTTPException(status_code=404, detail="Mesh 文件不存在")
    return FileResponse(
        path=str(glb_path),
        media_type="model/gltf-binary",
        filename="mesh.glb",
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
