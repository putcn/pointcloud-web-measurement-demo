#!/usr/bin/env python3
"""Generate a small, LiDAR-like urban street point cloud in ASCII PLY."""
from pathlib import Path
import math
import random

random.seed(20260804)
points = []

def add(x, y, z, rgb, noise=0.018, keep=0.94):
    if random.random() > keep:
        return
    points.append((x + random.gauss(0, noise), y + random.gauss(0, noise), z + random.gauss(0, noise), *rgb))

def plane(x0, x1, y0, y1, z, step, rgb):
    x = x0
    while x <= x1:
        y = y0
        while y <= y1:
            add(x, y, z, rgb, 0.014)
            y += step
        x += step

def facade(x0, x1, y, z0, z1, step, rgb):
    x = x0
    while x <= x1:
        z = z0
        while z <= z1:
            add(x, y, z, rgb, 0.022, 0.87)
            z += step
        x += step

def box(cx, cy, length, width, height, rgb):
    for x in frange(cx - length / 2, cx + length / 2, 0.09):
        for y in (cy - width / 2, cy + width / 2):
            for z in frange(0.12, height, 0.10): add(x, y, z, rgb, 0.012)
    for y in frange(cy - width / 2, cy + width / 2, 0.09):
        for x in (cx - length / 2, cx + length / 2):
            for z in frange(0.12, height, 0.10): add(x, y, z, rgb, 0.012)
    plane(cx - length / 2, cx + length / 2, cy - width / 2, cy + width / 2, height, 0.10, rgb)

def frange(a, b, step):
    while a <= b + 1e-9:
        yield a
        a += step

# Road, sidewalks, lane markings, and building facades.
plane(-16, 16, -4.4, 4.4, 0, 0.14, (63, 68, 74))
plane(-16, 16, -7.0, -4.4, 0.12, 0.14, (132, 136, 139))
plane(-16, 16, 4.4, 7.0, 0.12, 0.14, (132, 136, 139))
for x0 in range(-15, 16, 4):
    plane(x0, x0 + 2.0, -0.10, 0.10, 0.035, 0.06, (243, 218, 80))
facade(-16, 16, -7.0, 0.15, 7.5, 0.16, (164, 151, 138))
facade(-16, 16, 7.0, 0.15, 6.2, 0.16, (184, 181, 168))
# Windows, cars, street lamps, and low-poly trees.
for x0 in (-12, -6, 1, 8, 13):
    for z0 in (1.2, 3.2, 5.2):
        plane(x0, x0 + 2.2, -6.97, -6.97, z0, 0.15, (74, 130, 172))
for cx, cy, color in [(-7.0, -2.3, (203, 62, 52)), (3.5, 2.4, (49, 115, 194)), (10.5, -2.5, (236, 236, 232))]:
    box(cx, cy, 4.3, 1.85, 1.55, color)
for x in (-13, -3, 6, 14):
    for z in frange(0.15, 5.8, 0.12): add(x, 4.9, z, (70, 74, 76), 0.01, 0.97)
    for a in range(0, 360, 18):
        r = math.radians(a)
        add(x + 0.55 * math.cos(r), 4.9 + 0.55 * math.sin(r), 5.8, (255, 220, 118), 0.015)
for x, y in [(-10, 5.8), (-1, 5.8), (9, 5.8)]:
    for z in frange(0.15, 2.0, 0.10): add(x, y, z, (100, 70, 40), 0.015)
    for _ in range(520):
        theta = random.random() * math.tau
        phi = math.acos(1 - 2 * random.random())
        radius = random.uniform(0.4, 1.15)
        add(x + radius * math.sin(phi) * math.cos(theta), y + radius * math.sin(phi) * math.sin(theta), 2.2 + radius * math.cos(phi), (66, random.randint(110, 170), 70), 0.03, 0.82)

out = Path(__file__).resolve().parents[1] / 'samples' / 'synthetic-lidar-street.ply'
out.parent.mkdir(parents=True, exist_ok=True)
with out.open('w', encoding='utf-8') as f:
    f.write('ply\nformat ascii 1.0\n')
    f.write(f'element vertex {len(points)}\n')
    f.write('property float x\nproperty float y\nproperty float z\n')
    f.write('property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n')
    for x, y, z, r, g, b in points:
        f.write(f'{x:.4f} {y:.4f} {z:.4f} {r} {g} {b}\n')
print(f'Wrote {len(points):,} LiDAR-like points to {out}')
