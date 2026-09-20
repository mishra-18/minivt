import { ParamTable }      from './params.js';
import { loadModel }       from './model.js';
import { DeformEngine }    from './deform.js';
import { PhysicsSystem }   from './physics.js';
import { Renderer }        from './renderer.js';
import { Mapper, IdleAnimator } from './mapper.js';
import { MouseTracker, MediaPipeTracker } from './tracker.js';

const qs = new URLSearchParams(location.search);
const MODEL = qs.get('model') || './models/demo';
const BGS = {
  transparent: [0,0,0,0], green: [0,0.69,0.25,1],
  magenta: [1,0,1,1], black: [0,0,0,1], checker: [0,0,0,0]
};
let bgName = qs.get('bg') || 'transparent';

const cv    = document.getElementById('cv');
const stat  = document.getElementById('stat');
const panel = document.getElementById('panel');
const video = document.getElementById('vid');

const gl = cv.getContext('webgl2', {
  alpha: true, premultipliedAlpha: true, antialias: false,
  preserveDrawingBuffer: false, desynchronized: true
});
if (!gl){ stat.textContent = 'WebGL2 not supported'; throw new Error('no webgl2'); }

let renderer, model, params, deform, physics, mapper, idle, tracker, mouseTracker;
const overrides = new Set();
let sel = 0, pids = [], trackerOn = true;
const rows = new Map();

function applyBg(){
  document.body.className = bgName === 'checker' ? 'checker' : (bgName === 'green' ? 'green' : '');
  if (renderer) renderer.bg = BGS[bgName] || BGS.transparent;
}

function buildPanel(){
  panel.innerHTML = '';
  rows.clear();
  for (const id of pids){
    const d = params.defs.get(id);
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `<span>${id}</span>
      <input type="range" min="${d.min}" max="${d.max}" step="0.01" value="${d.def}">
      <span class="val">0.00</span><b title="release">×</b>`;
    const inp = row.querySelector('input');
    inp.addEventListener('input', () => { params.set(id, +inp.value); overrides.add(id); });
    row.querySelector('b').addEventListener('click', () => { overrides.delete(id); params.reset(id); });
    panel.appendChild(row);
    rows.set(id, { row, inp, val: row.querySelector('.val') });
  }
}

function resize(){
  const dpr = Math.min(devicePixelRatio || 1, 1);
  const w = Math.round(innerWidth * dpr), h = Math.round(innerHeight * dpr);
  if (cv.width !== w || cv.height !== h){
    cv.width = w; cv.height = h;
    if (renderer) renderer.resize(w, h);
  }
}

async function useCamera(){
  try {
    const t = new MediaPipeTracker(video);
    await t.start();
    if (tracker && tracker !== mouseTracker) tracker.stop();
    tracker = t;
    video.style.display = 'block';
    const b = document.getElementById('bCam');
    if (b){ b.textContent = '● camera on'; b.classList.add('on'); }
  } catch (e){
    console.warn('[tracker] camera failed:', e);
    alert('Camera/MediaPipe failed: ' + e.message + '\nStaying on cursor mode.');
  }
}

function useMouse(){
  if (tracker && tracker !== mouseTracker) tracker.stop();
  tracker = mouseTracker;
  video.style.display = 'none';
  const b = document.getElementById('bCam');
  if (b){ b.textContent = '▶\u00a0 Click to enable camera'; b.classList.remove('on'); }
}

const on = (id, fn) => { const el = document.getElementById(id); if (el) el.onclick = fn; };
on('bCam',   useCamera);
on('bMouse', useMouse);
on('bMir',   () => { if (mapper) mapper.mirror = !mapper.mirror; });
on('bCal',   () => { if (mapper) mapper.calibrate(); });
on('bPhy',   () => { if (physics) physics.enabled = !physics.enabled; });
on('bPan',   () => panel.classList.toggle('hide'));
on('bBg',    () => {
  const order = ['transparent','checker','green','black'];
  bgName = order[(order.indexOf(bgName) + 1) % order.length];
  applyBg();
});

addEventListener('keydown', e => {
  if (!params) return;
  const k = e.key.toLowerCase();
  if (k === 'tab'){ e.preventDefault(); sel = (sel + (e.shiftKey ? -1 : 1) + pids.length) % pids.length; }
  else if (k === 'r'){ params.reset(); overrides.clear(); physics.reset(); }
  else if (k === 'c'){ mapper.calibrate(); }
  else if (k === 't'){ trackerOn = !trackerOn; }
  else if (k === 'p'){ physics.enabled = !physics.enabled; }
  else if (k === 'm'){ mapper.mirror = !mapper.mirror; }
  else if (k === 'h'){ panel.classList.toggle('hide'); }
  else if (k === 'u'){ const u = document.getElementById('ui'); if (u) u.classList.toggle('hide'); }
  else if (k === 'backspace'){ overrides.delete(pids[sel]); params.reset(pids[sel]); }
  else if (k === 'arrowup' || k === 'arrowdown'){
    e.preventDefault();
    const id = pids[sel], d = params.defs.get(id);
    params.add(id, (d.max - d.min) * 0.02 * (k === 'arrowup' ? 1 : -1));
    overrides.add(id);
  }
});

(async function boot(){
  try {
    model = await loadModel(MODEL);
  } catch (e){
    stat.textContent = 'model load failed: ' + e.message;
    console.error(e);
    return;
  }
  params = new ParamTable();
  for (const p of model.params) params.define(p.id, p.min ?? 0, p.max ?? 1, p.default ?? null);
  pids = params.ids();
  deform = new DeformEngine(model, params);
  physics = new PhysicsSystem(model.physics);
  mapper = new Mapper(model.mapping);
  idle = new IdleAnimator();
  mouseTracker = new MouseTracker(cv);
  tracker = mouseTracker;

  resize();
  renderer = new Renderer(gl, model, BGS[bgName] || BGS.transparent);
  applyBg();
  buildPanel();
  addEventListener('resize', resize);
  if (qs.get('camera') === '1') useCamera();

  let prev = performance.now() / 1000, frames = 0, fpsT = prev;
  function loop(){
    requestAnimationFrame(loop);
    const t = performance.now() / 1000;
    const dt = Math.min(t - prev, 0.1); prev = t;

    const frame = trackerOn ? tracker.poll() : null;
    const tracked = mapper.apply(frame, params, t, overrides);
    idle.apply(params, t, tracked, overrides);
    physics.step(params, dt, overrides);
    deform.evaluate();
    resize();
    renderer.draw();

    frames++;
    if (t - fpsT >= 0.5){
      const fps = frames / (t - fpsT); frames = 0; fpsT = t;
      const id = pids[sel];
      stat.textContent = `${model.name} | ${trackerOn ? tracker.name : 'off'}:${tracked ? 'face' : 'idle'}`
        + ` | ${fps.toFixed(0)}fps | [${id}] ${params.get(id).toFixed(2)}`;
      for (const id2 of pids){
        const r = rows.get(id2);
        if (!r) continue;
        r.val.textContent = params.get(id2).toFixed(2);
        r.row.classList.toggle('ovr', overrides.has(id2));
        if (document.activeElement !== r.inp) r.inp.value = params.get(id2);
      }
    }
  }
  loop();
})();