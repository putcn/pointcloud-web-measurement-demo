import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// ---------------------------------------------------------------------------
// Renderer / scene
// ---------------------------------------------------------------------------
const container = document.querySelector('#viewer');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
container.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color('#101827');
const camera = new THREE.PerspectiveCamera(55, 1, 0.01, 100000);
camera.position.set(9, 8, 12);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
const grid = new THREE.GridHelper(30, 30, 0x42526b, 0x243044);
scene.add(grid);
scene.add(new THREE.AxesHelper(2));
const raycaster = new THREE.Raycaster();
raycaster.params.Points.threshold = 0.15;
const pointer = new THREE.Vector2();

// ---------------------------------------------------------------------------
// Scene objects
// ---------------------------------------------------------------------------
let cloud = null;     // THREE.Points
let meshObj = null;   // THREE.Group (GLB)
let measuring = false;
let firstPoint = null;
let markerGroup = new THREE.Group();
scene.add(markerGroup);

// ---------------------------------------------------------------------------
// UI elements
// ---------------------------------------------------------------------------
const status = document.querySelector('#measure-status');
const list = document.querySelector('#measurements');
const meshStatusPanel = document.querySelector('#mesh-status-panel');
const meshStatusText = document.querySelector('#mesh-status-text');
const meshProgressBar = document.querySelector('#mesh-progress-bar');
const btnCloudView = document.querySelector('#btn-cloud-view');
const btnMeshView = document.querySelector('#btn-mesh-view');
const meshNote = document.querySelector('#mesh-note');
const measureToggleBtn = document.querySelector('#measure-toggle');

// ---------------------------------------------------------------------------
// Backend URL (configurable for Docker / dev)
// ---------------------------------------------------------------------------
const BACKEND = (window.BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '');

// ---------------------------------------------------------------------------
// View state: 'cloud' | 'mesh'
// ---------------------------------------------------------------------------
let activeView = 'cloud';

function setView(view) {
  activeView = view;
  const showCloud = view === 'cloud';
  if (cloud) cloud.visible = showCloud;
  if (meshObj) meshObj.visible = !showCloud;
  markerGroup.visible = showCloud;

  btnCloudView.classList.toggle('active', showCloud);
  btnMeshView.classList.toggle('active', !showCloud);
  measureToggleBtn.disabled = !showCloud;
  meshNote.classList.toggle('hidden', showCloud);

  if (!showCloud && measuring) {
    measuring = false;
    firstPoint = null;
    measureToggleBtn.textContent = '开始长度量测';
    status.textContent = 'Mesh 视图下量测不可用，请切换回点云视图。';
  }
}

btnCloudView.addEventListener('click', () => setView('cloud'));
btnMeshView.addEventListener('click', () => {
  if (!btnMeshView.disabled) setView('mesh');
});

// ---------------------------------------------------------------------------
// Resize / render loop
// ---------------------------------------------------------------------------
function resize() {
  const { width, height } = container.getBoundingClientRect();
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
}
addEventListener('resize', resize);
resize();

function render() { controls.update(); renderer.render(scene, camera); requestAnimationFrame(render); }
render();

// ---------------------------------------------------------------------------
// ASCII PLY parser (browser-side, kept from original)
// ---------------------------------------------------------------------------
function parseAsciiPly(text) {
  const lines = text.replace(/\r/g, '').split('\n');
  if (lines[0]?.trim() !== 'ply') throw new Error('只支持 PLY 文件');
  let count = 0, headerEnd = -1, hasColor = false;
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('element vertex')) count = Number(line.split(/\s+/)[2]);
    if (line.includes('property uchar red')) hasColor = true;
    if (line === 'end_header') { headerEnd = i; break; }
  }
  if (headerEnd < 0 || !count) throw new Error('无效或不含顶点的 ASCII PLY');
  const positions = [], colors = [];
  for (let i = headerEnd + 1; i < lines.length && positions.length / 3 < count; i++) {
    const p = lines[i].trim().split(/\s+/).map(Number);
    if (p.length < 3 || p.slice(0, 3).some(Number.isNaN)) continue;
    positions.push(p[0], p[1], p[2]);
    if (hasColor && p.length >= 6) colors.push(p[3] / 255, p[4] / 255, p[5] / 255);
  }
  return { positions, colors: colors.length ? colors : null };
}

// ---------------------------------------------------------------------------
// Load / display a point cloud
// ---------------------------------------------------------------------------
function loadCloud(data, name) {
  if (cloud) scene.remove(cloud);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(data.positions, 3));
  if (data.colors) geometry.setAttribute('color', new THREE.Float32BufferAttribute(data.colors, 3));
  geometry.computeBoundingSphere();
  const material = new THREE.PointsMaterial({ size: Number(document.querySelector('#point-size').value) * 0.01, vertexColors: Boolean(data.colors), color: data.colors ? 0xffffff : 0x4dd8ff, sizeAttenuation: true });
  cloud = new THREE.Points(geometry, material);
  cloud.name = name;
  cloud.visible = activeView === 'cloud';
  scene.add(cloud);
  const sphere = geometry.boundingSphere;
  controls.target.copy(sphere.center);
  camera.position.copy(sphere.center).add(new THREE.Vector3(sphere.radius * 1.5 + 1, sphere.radius * 1.1 + 1, sphere.radius * 1.7 + 1));
  controls.update();
  clearMeasurements();
  status.textContent = `已加载 ${name}：${geometry.attributes.position.count.toLocaleString()} 个点`;
}

// ---------------------------------------------------------------------------
// Load GLB mesh from URL and add to scene
// ---------------------------------------------------------------------------
function loadMeshFromUrl(url) {
  const loader = new GLTFLoader();
  loader.load(url, (gltf) => {
    if (meshObj) scene.remove(meshObj);
    meshObj = gltf.scene;
    meshObj.visible = activeView === 'mesh';
    // Add lighting so the mesh is visible
    if (!scene.getObjectByName('__ambientLight')) {
      const amb = new THREE.AmbientLight(0xffffff, 0.6);
      amb.name = '__ambientLight';
      scene.add(amb);
      const dir = new THREE.DirectionalLight(0xffffff, 0.8);
      dir.name = '__dirLight';
      dir.position.set(10, 20, 10);
      scene.add(dir);
    }
    scene.add(meshObj);
    setMeshStatus('completed', 'Mesh 已就绪，可切换至 Mesh 视图。', 100);
    btnMeshView.disabled = false;
  }, undefined, (err) => {
    setMeshStatus('failed', `Mesh 加载失败：${err.message || err}`, 0);
  });
}

// ---------------------------------------------------------------------------
// Mesh status helpers
// ---------------------------------------------------------------------------
function setMeshStatus(state, text, progress) {
  meshStatusPanel.classList.remove('hidden', 'status-processing', 'status-completed', 'status-failed');
  if (state) meshStatusPanel.classList.add(`status-${state}`);
  meshStatusText.textContent = text;
  meshProgressBar.style.width = `${progress}%`;
}

// ---------------------------------------------------------------------------
// Backend upload + polling
// ---------------------------------------------------------------------------
let _pollTimer = null;

async function uploadAndReconstruct(file) {
  // Reset mesh view button
  btnMeshView.disabled = true;
  if (activeView === 'mesh') setView('cloud');
  if (meshObj) { scene.remove(meshObj); meshObj = null; }
  setMeshStatus('processing', '正在上传文件…', 5);

  let jobId;
  try {
    const formData = new FormData();
    formData.append('file', file);
    const resp = await fetch(`${BACKEND}/api/jobs`, { method: 'POST', body: formData });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || resp.statusText);
    }
    const data = await resp.json();
    jobId = data.job_id;
    setMeshStatus('processing', '正在后台生成 Mesh…', 15);
  } catch (e) {
    setMeshStatus('failed', `上传失败：${e.message}`, 0);
    return;
  }

  // Poll status
  if (_pollTimer) clearInterval(_pollTimer);
  _pollTimer = setInterval(async () => {
    try {
      const resp = await fetch(`${BACKEND}/api/jobs/${jobId}`);
      if (!resp.ok) return;
      const job = await resp.json();
      const stateLabels = { queued: '排队中…', processing: '正在后台生成 Mesh…', completed: 'Mesh 生成完成，正在加载…', failed: `生成失败：${job.error || '未知错误'}` };
      const progressMap = { queued: 20, processing: Math.max(job.progress || 20, 20), completed: 90, failed: 0 };
      setMeshStatus(job.status, stateLabels[job.status] || job.status, progressMap[job.status] ?? 0);

      if (job.status === 'completed') {
        clearInterval(_pollTimer);
        loadMeshFromUrl(`${BACKEND}/api/jobs/${jobId}/mesh`);
      } else if (job.status === 'failed') {
        clearInterval(_pollTimer);
      }
    } catch (_) { /* network glitch, keep polling */ }
  }, 2000);
}

// ---------------------------------------------------------------------------
// Sample loader
// ---------------------------------------------------------------------------
async function loadSample(name) {
  const response = await fetch(`./samples/${name}.ply`);
  if (!response.ok) throw new Error('示例文件加载失败');
  loadCloud(parseAsciiPly(await response.text()), `${name}.ply`);
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------
document.querySelector('#file-input').addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    // Immediate browser-side preview
    loadCloud(parseAsciiPly(await file.text()), file.name);
    // Async backend reconstruction
    uploadAndReconstruct(file);
  } catch (error) { alert(error.message); }
});

document.querySelectorAll('[data-sample]').forEach(button => button.addEventListener('click', () => loadSample(button.dataset.sample).catch(e => alert(e.message))));
document.querySelector('#point-size').addEventListener('input', e => { if (cloud) cloud.material.size = Number(e.target.value) * 0.01; });
document.querySelector('#background').addEventListener('input', e => scene.background.set(e.target.value));
document.querySelector('#grid').addEventListener('change', e => grid.visible = e.target.checked);
measureToggleBtn.addEventListener('click', e => {
  measuring = !measuring; firstPoint = null; e.target.textContent = measuring ? '退出长度量测' : '开始长度量测';
  status.textContent = measuring ? '请点击第一个点。' : '量测关闭。';
});
document.querySelector('#clear-measurements').addEventListener('click', clearMeasurements);

// ---------------------------------------------------------------------------
// Measurement helpers
// ---------------------------------------------------------------------------
function addMarker(position, color = 0xffcc33) {
  const marker = new THREE.Mesh(new THREE.SphereGeometry(0.07, 16, 12), new THREE.MeshBasicMaterial({ color }));
  marker.position.copy(position); markerGroup.add(marker);
}
function addMeasurement(a, b) {
  addMarker(a); addMarker(b);
  const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), new THREE.LineBasicMaterial({ color: 0xffcc33 }));
  markerGroup.add(line);
  const distance = a.distanceTo(b);
  const item = document.createElement('li');
  item.textContent = `${distance.toFixed(3)} scene units`;
  list.appendChild(item);
  status.textContent = `测量完成：${distance.toFixed(3)} scene units。请继续点击下一组端点。`;
}
function clearMeasurements() { markerGroup.clear(); firstPoint = null; list.replaceChildren(); }

renderer.domElement.addEventListener('pointerdown', event => {
  if (!measuring || !cloud || event.button !== 0) return;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObject(cloud)[0];
  if (!hit) return;
  if (!firstPoint) { firstPoint = hit.point.clone(); addMarker(firstPoint, 0x66e0ff); status.textContent = '已选第一个点，请点击第二个点。'; }
  else { addMeasurement(firstPoint, hit.point.clone()); firstPoint = null; }
});

loadSample('room').catch(() => {});
