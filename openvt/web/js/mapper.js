import { OneEuroFilter } from './filter.js';

const HEAD = new Set(['headX', 'headY', 'headAngleZ']);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export class Mapper {
  constructor(cfg = {}){
    this.mirror     = cfg.mirror !== false;
    this.yawSign    = cfg.yaw_sign   ?? 1;
    this.pitchSign  = cfg.pitch_sign ?? 1;
    this.rollSign   = cfg.roll_sign  ?? 1;
    this.headGain   = cfg.head_gain  ?? 1.3;
    this.deadzone   = cfg.deadzone_deg ?? 0.6;
    [this.blinkLo, this.blinkHi] = cfg.blink_range || [0.35, 0.7];
    this.linkEyes   = cfg.link_eyes   ?? 0.3;
    this.headCutoff = cfg.head_cutoff ?? 1.5;
    this.faceCutoff = cfg.face_cutoff ?? 4.0;
    this.beta       = cfg.smooth_beta ?? 0.1;
    this.filters = new Map();
    this.neutral = [0, 0, 0];
    this._calib = false;
  }
  calibrate(){ this._calib = true; }
  _f(id, x, t){
    let f = this.filters.get(id);
    if (!f){ f = new OneEuroFilter(HEAD.has(id) ? this.headCutoff : this.faceCutoff, this.beta);
             this.filters.set(id, f); }
    return f.apply(x, t);
  }
  _open(raw){
    const x = clamp((raw - this.blinkLo) / Math.max(this.blinkHi - this.blinkLo, 1e-3), 0, 1);
    return x * x * (3 - 2 * x);
  }
  _dz(v){ return Math.abs(v) < this.deadzone ? 0 : v - Math.sign(v) * this.deadzone; }

  apply(frame, params, t, skip){
    if (!frame || !frame.ok) return false;
    if (this._calib){
      this.neutral = [frame.yaw, frame.pitch, frame.roll];
      for (const f of this.filters.values()) f.reset();
      this._calib = false;
    }
    const ms = this.mirror ? -1 : 1;
    const yaw = this._dz(frame.yaw - this.neutral[0]);
    const pitch = this._dz(frame.pitch - this.neutral[1]);
    const roll = this._dz(frame.roll - this.neutral[2]);

    const out = {
      headX: yaw * ms * this.yawSign * this.headGain,
      headY: -pitch * this.pitchSign * this.headGain,
      headAngleZ: -roll * ms * this.rollSign,
      mouthOpen: clamp(frame.jawOpen * 1.6, 0, 1),
      mouthForm: clamp(frame.smile * 1.8 - frame.pucker * 1.5, -1, 1),
      browY: clamp((frame.browUp - frame.browDown) * 1.6, -1, 1),
      eyeBallX: clamp(-ms * (frame.lookR - frame.lookL) * 1.5, -1, 1),
      eyeBallY: clamp((frame.lookD - frame.lookU) * 1.5, -1, 1),
    };
    let oL = this._open(1 - frame.blinkL), oR = this._open(1 - frame.blinkR);
    if (Math.abs(oL - oR) < this.linkEyes){ oL = oR = (oL + oR) / 2; }
    out.eyeOpenL = this.mirror ? oL : oR;
    out.eyeOpenR = this.mirror ? oR : oL;

    for (const [id, v] of Object.entries(out)){
      if (skip.has(id) || !params.has(id)) continue;
      params.set(id, this._f(id, v, t));
    }
    return true;
  }
}

export class IdleAnimator {
  constructor(){ this.next = 2; this.t0 = null; }
  apply(params, t, tracked, skip){
    if (params.has('breath') && !skip.has('breath'))
      params.set('breath', 0.5 - 0.5 * Math.cos(t * 2 * Math.PI / 3.6));
    if (tracked) return;
    const idle = {
      headX: 5 * Math.sin(t * 0.6), headY: 2.5 * Math.sin(t * 0.9 + 1),
      headAngleZ: 2 * Math.sin(t * 0.45), eyeBallX: 0.25 * Math.sin(t * 0.3)
    };
    for (const [id, v] of Object.entries(idle)) if (!skip.has(id)) params.set(id, v);
    if (this.t0 === null && t >= this.next) this.t0 = t;
    let o = 1;
    if (this.t0 !== null){
      const u = (t - this.t0) / 0.22;
      if (u >= 1){ this.t0 = null; this.next = t + 2 + Math.random() * 3; }
      else o = Math.abs(u * 2 - 1);
    }
    for (const id of ['eyeOpenL', 'eyeOpenR']) if (!skip.has(id)) params.set(id, o);
  }
}