# Synthetic LiDAR Street Scene

`scripts/generate_lidar_street.py` produces `samples/synthetic-lidar-street.ply`: a deterministic, colored ASCII PLY representing a small urban road segment. It contains a roadway, sidewalks, dashed lane marking, façades and windows, three vehicles, street lamps, and trees. Surfaces are sampled densely, then given coordinate noise and random dropouts so that they resemble a LiDAR scan rather than a watertight mesh.

## Generate

```bash
python3 scripts/generate_lidar_street.py
python3 -m http.server 8080
```

Open the viewer, select `samples/synthetic-lidar-street.ply`, enable length measurement, and select two points. Coordinates are authored in **meters**, so the displayed scene-unit distance is meters.

This is synthetic data made for UI, rendering, and measurement testing; it is not a replacement for calibrated field-scanner data.
