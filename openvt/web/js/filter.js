const alpha = (cutoff, dt) => {
  const tau = 1 / (2 * Math.PI * Math.max(cutoff, 1e-6));
  return 1 / (1 + tau / Math.max(dt, 1e-6));
};

export class OneEuroFilter {
  constructor(minCutoff = 1.0, beta = 0.05, dCutoff = 1.0){
    this.minCutoff = minCutoff; this.beta = beta; this.dCutoff = dCutoff; this.reset();
  }
  reset(){ this.t = null; this.x = null; this.dx = 0; }
  apply(x, t){
    if (this.t === null || this.x === null){ this.t = t; this.x = x; this.dx = 0; return x; }
    const dt = Math.max(t - this.t, 1e-6); this.t = t;
    const rawDx = (x - this.x) / dt;
    const ad = alpha(this.dCutoff, dt);
    this.dx = ad * rawDx + (1 - ad) * this.dx;
    const a = alpha(this.minCutoff + this.beta * Math.abs(this.dx), dt);
    this.x = a * x + (1 - a) * this.x;
    return this.x;
  }
}