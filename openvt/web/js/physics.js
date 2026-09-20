export class Spring {
  constructor(cfg){
    this.output = cfg.output;
    this.inputs = (cfg.inputs || []).map(i => [i.param, i.weight ?? 1]);
    this.k = cfg.stiffness ?? 120;
    this.c = cfg.damping ?? 10;
    this.gain = cfg.gain ?? 1;
    this.mode = cfg.mode || 'lag';
    this.x = null; this.v = 0;
  }
  target(p){ let s = 0; for (const [id, w] of this.inputs) s += w * p.signed(id); return s; }
  step(p, dt){
    const t = this.target(p);
    if (this.x === null){ this.x = t; this.v = 0; }
    const n = Math.max(1, Math.floor(dt / (1/240)) + 1), h = dt / n;
    for (let i = 0; i < n; i++){
      const a = -this.k * (this.x - t) - this.c * this.v;
      this.v += a * h; this.x += this.v * h;
    }
    p.setSigned(this.output, (this.mode === 'lag' ? this.x - t : this.x) * this.gain);
  }
  reset(){ this.x = null; this.v = 0; }
}

export class PhysicsSystem {
  constructor(cfgs){ this.springs = (cfgs || []).map(c => new Spring(c)); this.enabled = true; }
  step(p, dt, skip){
    if (!this.enabled) return;
    dt = Math.min(dt, 0.05);
    for (const s of this.springs) if (!skip.has(s.output)) s.step(p, dt);
  }
  reset(){ for (const s of this.springs) s.reset(); }
}