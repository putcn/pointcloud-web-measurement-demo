# PointCloud Web Measurement Demo

一个无需后端构建步骤的静态 Web 示例：在浏览器加载 ASCII PLY 点云，使用鼠标交互浏览三维场景，并通过选取两点计算空间距离。点云数据不会上传到服务器；用户选择文件后仅在当前浏览器内存中解析。

## 功能

- 选择本地 ASCII PLY 文件加载
- 两份版本控制内的彩色示例点云：`room.ply` 与 `bridge.ply`
- OrbitControls 三维旋转、平移、缩放
- 点大小、背景、网格开关
- 点云射线拾取、两点长度测量、可视化端点与连线
- Docker/Nginx 静态部署

## 本地运行

由于示例文件使用 `fetch` 加载，请使用 HTTP server，而非直接双击 HTML：

```bash
python3 -m http.server 8080
# open http://localhost:8080
```

或：

```bash
docker build -t pointcloud-measure-demo .
docker run --rm -p 8080:80 pointcloud-measure-demo
```

## 输入和单位

当前 MVP 仅支持 **ASCII PLY**，并读取顶点 `x y z` 与可选 `red green blue` 属性。量测值会以 `scene units` 显示：若源数据坐标单位为米，则显示值即为米。生产环境应在上传侧校验文件大小/格式，并扩展 LAS/LAZ/E57 的服务端转换（例如 PDAL + PotreeConverter）。

## 架构演进

大规模 LiDAR 数据推荐采用：`Upload API → 对象存储 → PDAL/PotreeConverter 异步任务 → Potree octree tiles → 浏览器`。测量记录应保存端点三维坐标、点云版本、操作者和时间，而不应仅保存最终距离。

## 技术

- Three.js：渲染、射线拾取、轨道控制
- 原生 ES Modules：避免打包器，使样例可直接部署
- Docker + Nginx：静态托管
