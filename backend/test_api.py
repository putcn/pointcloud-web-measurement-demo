"""Smoke tests for the FastAPI backend."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Minimal ASCII PLY fixture (4 points, no color)
# ---------------------------------------------------------------------------

_PLY_CONTENT = b"""\
ply
format ascii 1.0
element vertex 4
property float x
property float y
property float z
end_header
0.0 0.0 0.0
1.0 0.0 0.0
0.0 1.0 0.0
0.0 0.0 1.0
"""


@pytest.fixture()
def client():
    from main import app  # noqa: PLC0415

    return TestClient(app)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Upload validation
# ---------------------------------------------------------------------------


def test_upload_rejects_non_ply(client: TestClient) -> None:
    resp = client.post(
        "/api/jobs",
        files={"file": ("pointcloud.txt", io.BytesIO(b"not a ply"), "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_accepts_ply_and_returns_job_id(client: TestClient) -> None:
    resp = client.post(
        "/api/jobs",
        files={"file": ("cloud.ply", io.BytesIO(_PLY_CONTENT), "application/octet-stream")},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["status"] in ("queued", "processing", "completed", "failed")


# ---------------------------------------------------------------------------
# Job status
# ---------------------------------------------------------------------------


def test_job_status_after_upload(client: TestClient) -> None:
    resp = client.post(
        "/api/jobs",
        files={"file": ("cloud.ply", io.BytesIO(_PLY_CONTENT), "application/octet-stream")},
    )
    job_id = resp.json()["job_id"]

    status_resp = client.get(f"/api/jobs/{job_id}")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["job_id"] == job_id
    assert body["status"] in ("queued", "processing", "completed", "failed")


def test_unknown_job_returns_404(client: TestClient) -> None:
    resp = client.get("/api/jobs/doesnotexist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Mesh download – not yet ready
# ---------------------------------------------------------------------------


def test_mesh_not_ready_returns_409(client: TestClient) -> None:
    """If the job is queued/processing the mesh endpoint returns 409."""
    from main import Job, JobStatus, _jobs  # noqa: PLC0415

    # Insert a fake queued job without actually running reconstruction
    job_id = "fakejob123"
    _jobs[job_id] = Job(job_id=job_id, status=JobStatus.QUEUED)

    resp = client.get(f"/api/jobs/{job_id}/mesh")
    assert resp.status_code == 409
