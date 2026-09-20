// 2x3 affine, row-major: [a,b,tx, d,e,ty]
export function trs(pivot, tx, ty, rot, sx, sy){
  const r = rot * Math.PI / 180, c = Math.cos(r), s = Math.sin(r);
  const a = c*sx, b = -s*sy, d = s*sx, e = c*sy, px = pivot[0], py = pivot[1];
  return [a, b, px + tx - (a*px + b*py), d, e, py + ty - (d*px + e*py)];
}
export function mul(A, B){
  return [
    A[0]*B[0] + A[1]*B[3], A[0]*B[1] + A[1]*B[4], A[0]*B[2] + A[1]*B[5] + A[2],
    A[3]*B[0] + A[4]*B[3], A[3]*B[1] + A[4]*B[4], A[3]*B[2] + A[4]*B[5] + A[5]
  ];
}
const IDENT = [1,0,0, 0,1,0];

function seg(keys, v){
  const n = keys.length;
  if (v <= keys[0].v) return [0, 0];
  if (v >= keys[n-1].v) return [n-1, 0];
  for (let i = 0; i < n-1; i++){
    const a = keys[i].v, b = keys[i+1].v;
    if (v >= a && v <= b) return [i, b === a ? 0 : (v - a) / (b - a)];
  }
  return [n-1, 0];
}

export class DeformEngine {
  constructor(model, params){
    this.model = model; this.params = params; this.nodes = model.nodes;
    this.tbind = new Map(); this.mbind = new Map();
    for (const b of model.bindings){
      const m = b.type === 'transform' ? this.tbind : this.mbind;
      if (!m.has(b.target)) m.set(b.target, []);
      m.get(b.target).push(b);
    }
    const depth = new Map();
    const d = (id, seen) => {
      if (depth.has(id)) return depth.get(id);
      const n = this.nodes.get(id);
      const v = (n.parent === null || !this.nodes.has(n.parent) || seen.has(id))
        ? 0 : d(n.parent, new Set([...seen, id])) + 1;
      depth.set(id, v); return v;
    };
    for (const id of this.nodes.keys()) d(id, new Set());
    this.order = [...this.nodes.keys()].sort((a, b) => depth.get(a) - depth.get(b));
    this.world = new Map();
  }

  evaluate(){
    const p = this.params;
    for (const id of this.order){
      const n = this.nodes.get(id);
      let tx = 0, ty = 0, rot = 0, sx = 1, sy = 1;
      for (const b of (this.tbind.get(id) || [])){
        const [i, t] = seg(b.keys, p.get(b.param));
        const A = b.keys[i].a, B = b.keys[Math.min(i+1, b.keys.length-1)].a;
        tx  += A[0] + (B[0]-A[0])*t;
        ty  += A[1] + (B[1]-A[1])*t;
        rot += A[2] + (B[2]-A[2])*t;
        sx  *= A[3] + (B[3]-A[3])*t;
        sy  *= A[4] + (B[4]-A[4])*t;
      }
      const local = trs(n.pivot, tx, ty, rot, sx, sy);
      const par = n.parent !== null ? this.world.get(n.parent) : null;
      this.world.set(id, par ? mul(par, local) : local);
    }

    for (const L of this.model.layers){
      const mb = this.mbind.get(L.id);
      let src = L.basePos;
      if (mb){
        const s = L.scratch; s.set(L.basePos);
        for (const b of mb){
          const [i, t] = seg(b.keys, p.get(b.param));
          const A = b.keys[i].off, B = b.keys[Math.min(i+1, b.keys.length-1)].off;
          for (let k = 0; k < s.length; k++) s[k] += A[k] + (B[k]-A[k])*t;
        }
        src = s;
      }
      const M = this.world.get(L.id) || IDENT, out = L.curPos;
      for (let k = 0; k < src.length; k += 2){
        const x = src[k], y = src[k+1];
        out[k]   = M[0]*x + M[1]*y + M[2];
        out[k+1] = M[3]*x + M[4]*y + M[5];
      }
    }
  }
}