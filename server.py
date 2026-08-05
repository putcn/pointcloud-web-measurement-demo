from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path

import numpy as np
import open3d as o3d
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
JOBS_DIR = ROOT / "runtime" / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
jobs: dict[str, dict] = {}
lock = threading.Lock()

app = FastAPI(title="PointCloud Mesh Service")

def update(job_id: str, **values):
    with lock:
        jobs[job_id].update(values)

def reconstruct(job_id: str, source: Path):
    try:
        update(job_id, status="processing", message="正在清理点云并估计法线…", progress=20)
        cloud = o3d.io.read_point_cloud(str(source))
        if len(cloud.points) < 30:
            raise ValueError("点云至少需要 30 个点")
        cloud = cloud.voxel_down_sample(0.05)
        cloud, _ = cloud.remove_statistical_outlier(nb_neighbors=24, std_ratio=1.7)
        cloud.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.25, max_nn=48))
        cloud.orient_normals_consistent_tangent_plane(20)
        update(job_id, message="正在执行 Poisson 表面重建…", progress=55)
        mesh, density = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(cloud, depth=9)
        density = np.asarray(density)
        mesh.remove_vertices_by_mask(density < np.quantile(density, 0.03))
        mesh.remove_degenerate_triangles()
        mesh.remove_duplicated_triangles()
        mesh.remove_non_manifold_edges()
        if len(mesh.triangles) > 200_000:
            mesh = mesh.simplify_quadric_decimation(200_000)
        mesh.compute_vertex_normals()
        target = source.with_name("mesh.ply")
        o3d.io.write_triangle_mesh(str(target), mesh, write_vertex_colors=True)
        update(job_id, status="completed", message="Mesh 已生成，可切换到 Mesh 视图。", progress=100, mesh_url=f"/api/jobs/{job_id}/mesh")
    except Exception as exc:
        update(job_id, status="failed", message=str(exc), progress=100)

@app.post("/api/jobs")
async def create_job(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".ply"):
        raise HTTPException(400, "当前仅支持 .ply 文件")
    job_id = uuid.uuid4().hex
    directory = JOBS_DIR / job_id
    directory.mkdir()
    source = directory / "source.ply"
    size = 0
    with source.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                output.close(); shutil.rmtree(directory, ignore_errors=True)
                raise HTTPException(413, "文件超过 100 MB 限制")
            output.write(chunk)
    jobs[job_id] = {"id": job_id, "status": "queued", "progress": 5, "message": "文件已上传，等待后台任务。"}
    threading.Thread(target=reconstruct, args=(job_id, source), daemon=True).start()
    return jobs[job_id]

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    return job

@app.get("/api/jobs/{job_id}/mesh")
def get_mesh(job_id: str):
    mesh = JOBS_DIR / job_id / "mesh.ply"
    if not mesh.exists():
        raise HTTPException(404, "Mesh 尚未完成")
    return FileResponse(mesh, media_type="application/octet-stream", filename="mesh.ply")

app.mount("/", StaticFiles(directory=ROOT, html=True), name="web")
