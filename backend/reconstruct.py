"""Open3D-based point cloud to mesh reconstruction pipeline."""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# Triangle budget for web delivery
_MAX_TRIANGLES = 200_000


def reconstruct(input_ply: Path, output_glb: Path) -> None:
    """Read a PLY point cloud, run Poisson reconstruction, export GLB.

    Parameters
    ----------
    input_ply:
        Path to the input ASCII or binary PLY file.
    output_glb:
        Destination path for the exported GLB mesh.

    Notes
    -----
    The generated geometry is an **inferred surface**.  Measurements should
    remain snapped to original point cloud points, not to mesh vertices.
    """
    try:
        import open3d as o3d  # type: ignore
    except ImportError as exc:
        raise RuntimeError("open3d is not installed") from exc

    log.info("Loading point cloud from %s", input_ply)
    pcd = o3d.io.read_point_cloud(str(input_ply))
    if len(pcd.points) == 0:
        raise ValueError("Point cloud contains no points")

    log.info("Points loaded: %d", len(pcd.points))

    # Voxel downsample to a manageable density
    voxel_size = _estimate_voxel_size(pcd)
    log.info("Voxel downsample with size %.4f", voxel_size)
    pcd = pcd.voxel_down_sample(voxel_size)

    # Remove statistical outliers
    log.info("Removing statistical outliers")
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)

    # Estimate and consistently orient normals
    log.info("Estimating normals")
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size * 3, max_nn=30)
    )
    pcd.orient_normals_consistent_tangent_plane(k=15)

    # Poisson surface reconstruction
    log.info("Running Poisson surface reconstruction")
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=9, width=0, scale=1.1, linear_fit=False
    )

    # Remove low-density vertices (trim artefacts at the convex hull boundary)
    log.info("Removing low-density vertices")
    densities_np = np.asarray(densities)
    threshold = np.quantile(densities_np, 0.05)
    vertices_to_remove = densities_np < threshold
    mesh.remove_vertices_by_mask(vertices_to_remove)

    # Basic mesh cleanup
    log.info("Cleaning mesh")
    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_triangles()
    mesh.remove_duplicated_vertices()
    mesh.remove_non_manifold_edges()

    # Simplify to web-friendly triangle budget
    n_triangles = len(mesh.triangles)
    if n_triangles > _MAX_TRIANGLES:
        log.info("Simplifying mesh from %d to %d triangles", n_triangles, _MAX_TRIANGLES)
        mesh = mesh.simplify_quadric_decimation(_MAX_TRIANGLES)

    # Compute vertex normals for smooth shading in Three.js
    mesh.compute_vertex_normals()

    log.info("Exporting mesh to %s", output_glb)
    output_glb.parent.mkdir(parents=True, exist_ok=True)
    success = o3d.io.write_triangle_mesh(str(output_glb), mesh, write_ascii=False)
    if not success:
        raise RuntimeError("open3d failed to write the mesh file")

    log.info("Reconstruction complete: %d triangles", len(mesh.triangles))


def _estimate_voxel_size(pcd) -> float:  # type: ignore[no-untyped-def]
    """Heuristic: target ~100 000 points after downsampling."""
    import open3d as o3d  # type: ignore

    target = 100_000
    n = len(pcd.points)
    if n <= target:
        return 0.0  # no downsampling needed – open3d treats 0 as no-op

    bbox = pcd.get_axis_aligned_bounding_box()
    extent = np.asarray(bbox.get_extent())
    volume = float(np.prod(extent[extent > 0]))
    # voxel_size^3 * target ≈ volume
    voxel_size = float((volume / target) ** (1.0 / 3.0))
    return max(voxel_size, 1e-4)
