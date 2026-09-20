const CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14';
const TASK = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/' +
             'face_landmarker/float16/1/face_landmarker.task';

export const emptyFrame = () => ({
  ok:false, yaw:0, pitch:0, roll:0, headX:0, headY:0,
  blinkL:0, blinkR:0, jawOpen:0, smile:0, pucker:0, browUp:0, browDown:0,
  lookL:0, lookR:0, lookU:0, lookD:0
});

export class MouseTracker {
  constructor(canvas){
    this.name = 'mouse'; this.nx = 0; this.ny = 0; this.lmb = false; this.rmb = false;
    const set = e => {
      const r = canvas.getBoundingClientRect();
      this.nx = Math.max(-1, Math.min(1, (e.clientX - r.left) / r.width * 2 - 1));
      this.ny = Math.max(-1, Math.min(1, (e.clientY - r.top) / r.height * 2 - 1));
    };
    addEventListener('pointermove', set);
    addEventListener('pointerdown', e => { set(e); if (e.button === 0) this.lmb = true; if (e.button === 2) this.rmb = true; });
    addEventListener('pointerup',   e => { if (e.button === 0) this.lmb = false; if (e.button === 2) this.rmb = false; });
    addEventListener('contextmenu', e => e.preventDefault());
  }
  async start(){}
  stop(){}
  poll(){
    const f = emptyFrame(); f.ok = true;
    f.yaw = -this.nx * 25; f.pitch = this.ny * 20;
    f.headX = this.nx; f.headY = this.ny;
    f.jawOpen = this.lmb ? 0.7 : 0;
    f.blinkL = f.blinkR = this.rmb ? 1 : 0;
    f.lookR = Math.max(this.nx, 0); f.lookL = Math.max(-this.nx, 0);
    f.lookD = Math.max(this.ny, 0); f.lookU = Math.max(-this.ny, 0);
    return f;
  }
}

export class MediaPipeTracker {
  constructor(video){ this.name = 'mediapipe'; this.video = video; this._latest = emptyFrame(); }

  async start(){
    const { FaceLandmarker, FilesetResolver } = await import(`${CDN}/vision_bundle.mjs`);
    const fileset = await FilesetResolver.forVisionTasks(`${CDN}/wasm`);
    this.lm = await FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: TASK, delegate: 'GPU' },
      runningMode: 'VIDEO', numFaces: 1,
      outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true
    });
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480 }, audio: false });
    this.video.srcObject = stream;
    await this.video.play();
    this.stream = stream;
    this.lastTs = -1;
    console.log('[tracker] mediapipe running');
  }

  stop(){
    this.stream?.getTracks().forEach(t => t.stop());
    this.lm?.close?.();
  }

  poll(){
    if (!this.lm || this.video.readyState < 2) return this._latest;
    let ts = performance.now();
    if (ts <= this.lastTs) ts = this.lastTs + 1;
    this.lastTs = ts;
    let res;
    try { res = this.lm.detectForVideo(this.video, ts); }
    catch { return this._latest; }
    this._latest = this._toFrame(res);
    return this._latest;
  }

  _toFrame(res){
    const f = emptyFrame();
    if (!res?.faceLandmarks?.length) return f;
    f.ok = true;
    const mats = res.facialTransformationMatrixes;
    if (mats?.length){
      const d = mats[0].data;              // column-major 4x4
      const R = (r, c) => d[c * 4 + r];
      const sy = Math.hypot(R(0,0), R(1,0));
      f.yaw   = Math.atan2(-R(2,0), sy) * 180 / Math.PI;
      f.pitch = Math.atan2(R(2,1), R(2,2)) * 180 / Math.PI;
      f.roll  = Math.atan2(R(1,0), R(0,0)) * 180 / Math.PI;
    }
    const nose = res.faceLandmarks[0][1];
    f.headX = (nose.x - 0.5) * 2; f.headY = (nose.y - 0.5) * 2;
    const bs = {};
    for (const c of (res.faceBlendshapes?.[0]?.categories || [])) bs[c.categoryName] = c.score;
    const g = k => bs[k] || 0;
    f.blinkL = g('eyeBlinkLeft'); f.blinkR = g('eyeBlinkRight');
    f.jawOpen = g('jawOpen');
    f.smile = (g('mouthSmileLeft') + g('mouthSmileRight')) / 2;
    f.pucker = Math.max(g('mouthPucker'), g('mouthFunnel'));
    f.browUp = (g('browInnerUp') + g('browOuterUpLeft') + g('browOuterUpRight')) / 3;
    f.browDown = (g('browDownLeft') + g('browDownRight')) / 2;
    f.lookL = (g('eyeLookOutLeft') + g('eyeLookInRight')) / 2;
    f.lookR = (g('eyeLookInLeft') + g('eyeLookOutRight')) / 2;
    f.lookU = (g('eyeLookUpLeft') + g('eyeLookUpRight')) / 2;
    f.lookD = (g('eyeLookDownLeft') + g('eyeLookDownRight')) / 2;
    return f;
  }
}