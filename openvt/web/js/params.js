export class ParamTable {
  constructor(){ this.defs = new Map(); this.values = new Map(); }
  define(id, mn=0, mx=1, def=null){
    if (def === null) def = Math.min(Math.max(0, mn), mx);
    this.defs.set(id, {id, min:+mn, max:+mx, def:+def});
    this.values.set(id, +def);
  }
  has(id){ return this.defs.has(id); }
  ids(){ return [...this.defs.keys()]; }
  get(id, fb=0){ const v = this.values.get(id); return v === undefined ? fb : v; }
  set(id, v){
    const d = this.defs.get(id); if (!d) return;
    this.values.set(id, Math.min(Math.max(+v, d.min), d.max));
  }
  add(id, dv){ this.set(id, this.get(id) + dv); }
  signed(id){
    const d = this.defs.get(id); if (!d) return 0;
    const v = this.values.get(id);
    const span = v >= d.def ? (d.max - d.def) : (d.def - d.min);
    return span <= 0 ? 0 : (v - d.def) / span;
  }
  setSigned(id, s){
    const d = this.defs.get(id); if (!d) return;
    s = Math.min(Math.max(+s, -1), 1);
    const span = s >= 0 ? (d.max - d.def) : (d.def - d.min);
    this.set(id, d.def + s * span);
  }
  reset(id=null){
    if (id === null) for (const [k,d] of this.defs) this.values.set(k, d.def);
    else if (this.defs.has(id)) this.values.set(id, this.defs.get(id).def);
  }
}