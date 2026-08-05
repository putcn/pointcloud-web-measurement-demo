# PointCloud Web Measurement Demo

一个基于 Web 的点云查看、空间长度量测和异步 Mesh 重建示例。用户在浏览器选择 ASCII PLY 后，前端会立刻显示点云；同时文件被提交给 FastAPI 后端，后端使用 Open3D 执行 Poisson 表面重建并提供生成的 Mesh。

> 当前 `main` 已具备后端异步重建 API。前端的任务状态面板与点云/Mesh 视图切换将在后续提交中接入该 API。

## 当前功能

- Three.js 点云浏览：旋转、平移、缩放、点大小和背景调整。
- 点云两点距离量测。
- ASCII PLY 本地加载与示例点云。
- FastAPI 异步 PLY 上传、任务状态查询和 Mesh 下载接口。
- Open3D 网格管线：体素下采样、统计离群点滤波、法线估计、Poisson 重建、低置信度区域剔除和网格简化。

## 快速启动

### macOS / Linux

```bash
git clone https://github.com/putcn/pointcloud-web-measurement-demo.git
cd pointcloud-web-measurement-demo
./scripts/start.sh
```

脚本会创建 `.venv`、安装依赖，并启动服务。浏览器访问 [http://localhost:8000](http://localhost:8000)。

### Windows PowerShell

```powershell
git clone https://github.com/putcn/pointcloud-web-measurement-demo.git
cd pointcloud-web-measurement-demo
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\start.ps1
```

### 手动启动

需要 Python 3.11 或更高版本：

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

## Docker

```bash
docker build -t pointcloud-web-measurement-demo .
docker run --rm -p 8000:8000 pointcloud-web-measurement-demo
```

访问 [http://localhost:8000](http://localhost:8000)。容器内的上传文件和生成 Mesh 位于 `runtime/jobs`，容器删除后会被清理；生产部署应挂载持久卷或接入对象存储。

## API

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/jobs` | 使用 multipart 字段 `file` 上传 `.ply` 并创建异步任务 |
| `GET` | `/api/jobs/{job_id}` | 查询 `queued`、`processing`、`completed` 或 `failed` 状态 |
| `GET` | `/api/jobs/{job_id}/mesh` | 在任务完成后下载 `mesh.ply` |

上传目前限制为 100 MB，运行时文件按 job ID 隔离。服务重启后内存中的任务状态会丢失；这是示例实现，生产环境应使用数据库与持久化任务队列。

## 数据与量测

当前浏览器端解析器支持 **ASCII PLY** 的 `x y z` 和可选 `red green blue` 顶点属性。量测值使用源坐标单位：若点云单位为米，显示距离即为米。

Mesh 是由算法推断/补全的连续表面，尤其在遮挡和稀疏区域可能产生不真实的封口；工程量测应继续吸附到原始点云，而不是仅依据重建网格。

## 示例场景

```bash
python3 scripts/generate_lidar_street.py
```

该命令会生成 `samples/synthetic-lidar-street.ply`：一个包含道路、人行道、车道线、建筑立面、车辆、路灯和树木的合成 LiDAR 风格街景。它适合验证渲染、量测与网格化流程，不用于替代真实标定扫描数据。
