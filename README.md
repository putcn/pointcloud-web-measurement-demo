# PointCloud Web Measurement Demo

一个浏览器端点云预览 + 后端服务端 Mesh 重建演示：在浏览器加载 ASCII PLY 点云，立即渲染三维点云预览，并异步上传至 FastAPI 后端，使用 Open3D 进行 Poisson 曲面重建，重建完成后可在 Mesh 视图中浏览。

## 功能

- 选择本地 ASCII PLY 文件，立即在浏览器渲染点云预览
- 两份版本控制内的彩色示例点云：`room.ply` 与 `bridge.ply`
- OrbitControls 三维旋转、平移、缩放
- 点大小、背景、网格开关
- 点云射线拾取、两点长度测量、可视化端点与连线（仅点云视图可用）
- 上传 PLY 至后端，异步生成 Mesh，状态面板显示 排队中 / 生成中 / 完成 / 失败
- Mesh 视图：三维浏览重建 GLB 网格（测量功能在 Mesh 视图下禁用）
- Docker Compose 一键本地运行

> **注意**：生成的 Mesh 为推断曲面，仅供可视化参考。精确量测请始终切换至点云视图并吸附到原始点。

## 本地开发

### 仅前端（无 Mesh 重建）

```bash
python3 -m http.server 8080
# open http://localhost:8080
```

### 完整服务（前端 + 后端）

需要安装 Docker 和 Docker Compose：

```bash
docker compose up --build
# 前端: http://localhost:8080
# 后端 API: http://localhost:8000/docs
```

### 仅启动后端（用于开发）

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## 运行测试

```bash
cd backend
pip install -r requirements.txt
pytest test_api.py -v
```

## 输入要求

- 当前前端仅支持 **ASCII PLY**，读取顶点 `x y z` 与可选 `red green blue`（uint8）属性
- 后端同时支持 ASCII 和 binary PLY（由 Open3D 读取）
- 默认最大上传大小：200 MB（可通过环境变量 `MAX_UPLOAD_MB` 调整）

## 重建流水线

1. Open3D 读取点云
2. 体素降采样（目标约 10 万点）
3. 统计离群点去除
4. 法向量估计与一致定向
5. Poisson 曲面重建（depth=9）
6. 去除低密度顶点（密度分位数 < 5%）
7. 网格清理（退化三角形、重复顶点等）
8. 二次误差简化至最多 200 000 三角面
9. 导出 GLB（由 Three.js GLTFLoader 加载）

## 环境变量（后端）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `JOBS_DIR` | `/tmp/pointcloud_jobs` | 任务文件存放目录 |
| `MAX_UPLOAD_MB` | `200` | 最大上传文件大小（MB） |
| `CORS_ORIGINS` | `http://localhost:8080,...` | 允许的 CORS 来源，逗号分隔 |

## 架构演进

大规模 LiDAR 数据推荐采用：`Upload API → 对象存储 → PDAL/PotreeConverter 异步任务 → Potree octree tiles → 浏览器`。测量记录应保存端点三维坐标、点云版本、操作者和时间，而不应仅保存最终距离。

## 技术

- Three.js：渲染、射线拾取、轨道控制、GLTFLoader
- FastAPI + uvicorn：异步 REST API，BackgroundTasks 任务队列
- Open3D：点云处理与 Poisson 曲面重建
- 原生 ES Modules：避免打包器，使样例可直接部署
- Docker Compose：前端（Nginx）+ 后端（Python）一键运行
