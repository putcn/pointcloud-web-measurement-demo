import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

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
let cloud = null;
let measuring = false;
let firstPoint = null;
let markerGroup = new THREE.Group();
scene.add(markerGroup);
const status = document.querySelector('#measure-status');
const list = document.querySelector('#measurements');

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

function loadCloud(data, name) {
  if (cloud) scene.remove(cloud);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(data.positions, 3));
  if (data.colors) geometry.setAttribute('color', new THREE.Float32BufferAttribute(data.colors, 3));
  geometry.computeBoundingSphere();
  const material = new THREE.PointsMaterial({ size: Number(document.querySelector('#point-size').value) * 0.01, vertexColors: Boolean(data.colors), color: data.colors ? 0xffffff : 0x4dd8ff, sizeAttenuation: true });
  cloud = new THREE.Points(geometry, material);
  cloud.name = name;
  scene.add(cloud);
  const sphere = geometry.boundingSphere;
  controls.target.copy(sphere.center);
  camera.position.copy(sphere.center).add(new THREE.Vector3(sphere.radius * 1.5 + 1, sphere.radius * 1.1 + 1, sphere.radius * 1.7 + 1));
  controls.update();
  clearMeasurements();
  status.textContent = `已加载 ${name}：${geometry.attributes.position.count.toLocaleString()} 个点`;
}

async function loadSample(name) {
  const response = await fetch(`./samples/${name}.ply`);
  if (!response.ok) throw new Error('示例文件加载失败');
  loadCloud(parseAsciiPly(await response.text()), `${name}.ply`);
}

document.querySelector('#file-input').addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try { loadCloud(parseAsciiPly(await file.text()), file.name); } catch (error) { alert(error.message); }
});
document.querySelectorAll('[data-sample]').forEach(button => button.addEventListener('click', () => loadSample(button.dataset.sample).catch(e => alert(e.message))));
document.querySelector('#point-size').addEventListener('input', e => { if (cloud) cloud.material.size = Number(e.target.value) * 0.01; });
document.querySelector('#background').addEventListener('input', e => scene.background.set(e.target.value));
document.querySelector('#grid').addEventListener('change', e => grid.visible = e.target.checked);
document.querySelector('#measure-toggle').addEventListener('click', e => {
  measuring = !measuring; firstPoint = null; e.target.textContent = measuring ? '退出长度量测' : '开始长度量测';
  status.textContent = measuring ? '请点击第一个点。' : '量测关闭。';
});
document.querySelector('#clear-measurements').addEventListener('click', clearMeasurements);

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
