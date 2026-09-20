function loadImage(url){
  return new Promise((res, rej) => {
    const im = new Image();
    im.onload = () => res(im);
    im.onerror = () => rej(new Error('image failed: ' + url));
    im.src = url;
  });
}

function alphaOf(img){
  const c = document.createElement('canvas');
  c.width = img.naturalWidth; c.height = img.naturalHeight;
  const ctx = c.getContext('2d', {willReadFrequently:true});
  ctx.drawImage(img, 0, 0);
  const d = ctx.getImageData(0, 0, c.width, c.height).data;
  const a = new Uint8Array(c.width * c.height);
  for (let i = 0, j = 3; i < a.length; i++, j += 4) a[i] = d[j];
  return {data:a, w:c.width, h:c.height};
}

// port of core/meshgen.py
function gridMesh(x0, y0, w, h, cols, rows, alpha, margin = 2){
  cols = Math.max(1, cols|0); rows = Math.max(1, rows|0);
  const nv = (cols + 1) * (rows + 1);
  const pos = new Float32Array(nv * 2), uv = new Float32Array(nv * 2);
  let k = 0;
  for (let r = 0; r <= rows; r++){
    const v = r / rows;
    for (let c = 0; c <= cols; c++){
      const u = c / cols;
      uv[k] = u; uv[k+1] = v;
      pos[k] = x0 + u * w; pos[k+1] = y0 + v * h;
      k += 2;
    }
  }
  const idx = [];
  const tw = alpha ? alpha.w : w, th = alpha ? alpha.h : h;
  for (let r = 0; r < rows; r++){
    for (let c = 0; c < cols; c++){
      if (alpha){
        const px0 = Math.max(0, ((c*tw/cols)|0) - margin), px1 = Math.min(tw, (((c+1)*tw/cols)|0) + margin);
        const py0 = Math.max(0, ((r*th/rows)|0) - margin), py1 = Math.min(th, (((r+1)*th/rows)|0) + margin);
        let any = false;
        for (let y = py0; y < py1 && !any; y++){
          const row = y * tw;
          for (let x = px0; x < px1; x++) if (alpha.data[row + x]){ any = true; break; }
        }
        if (!any) continue;
      }
      const i0 = r * (cols + 1) + c, i1 = i0 + 1, i2 = i0 + cols + 1, i3 = i2 + 1;
      idx.push(i0, i2, i1, i1, i2, i3);
    }
  }
  return {pos, uv, idx:new Uint32Array(idx)};
}

export async function loadModel(base){
  base = base.replace(/\/$/, '');
  const d = await (await fetch(base + '/model.json')).json();
  const m = {
    name: d.name || 'model',
    width: d.canvas?.width ?? 1024,
    height: d.canvas?.height ?? 1024,
    params: d.params || [],
    nodes: new Map(), layers: [], layerById: new Map(),
    bindings: [], physics: d.physics || [], mapping: d.mapping || {}
  };

  for (const n of (d.nodes || []))
    m.nodes.set(n.id, {id:n.id, parent:n.parent ?? null, pivot:n.pivot || [m.width/2, m.height/2]});

  const imgs = await Promise.all(d.layers.map(l => loadImage(base + '/' + l.texture)));

  d.layers.forEach((l, i) => {
    const img = imgs[i], tw = img.naturalWidth, th = img.naturalHeight;
    const pos = l.pos || [0, 0];
    const mesh = l.mesh || {};
    const [cols, rows] = mesh.grid || [1, 1];
    const clip = (mesh.clip !== false) && (cols * rows > 1);
    const g = gridMesh(pos[0], pos[1], tw, th, cols, rows, clip ? alphaOf(img) : null);
    let masked = l.maskedBy || [];
    if (typeof masked === 'string') masked = [masked];
    const layer = {
      id:l.id, parent:l.parent ?? null, image:img, texSize:[tw, th],
      z:+(l.z ?? i), order:i, opacity:+(l.opacity ?? 1), blend:l.blend || 'normal',
      tint:l.tint || [1,1,1,1], maskedBy:masked, visible:l.visible !== false,
      basePos:g.pos, uv:g.uv, idx:g.idx,
      curPos:new Float32Array(g.pos), scratch:new Float32Array(g.pos.length)
    };
    if (m.nodes.has(layer.id)) throw new Error('duplicate id: ' + layer.id);
    m.layers.push(layer); m.layerById.set(layer.id, layer);
    m.nodes.set(layer.id, {
      id:layer.id, parent:layer.parent,
      pivot:l.pivot || [pos[0] + tw/2, pos[1] + th/2]
    });
  });

  m.layers.sort((a, b) => (a.z - b.z) || (a.order - b.order));

  for (const n of m.nodes.values())
    if (n.parent !== null && !m.nodes.has(n.parent)){
      console.warn(`[model] ${n.id}: unknown parent ${n.parent}`); n.parent = null;
    }

  for (const b of (d.bindings || [])){
    const keys = [...b.keys].sort((p, q) => p.v - q.v);
    if (!m.nodes.has(b.target)){ console.warn('[model] unknown target', b.target); continue; }
    if (b.type === 'transform'){
      m.bindings.push({type:'transform', target:b.target, param:b.param,
        keys:keys.map(k => ({v:+k.v, a:[k.tx ?? 0, k.ty ?? 0, k.rot ?? 0, k.sx ?? 1, k.sy ?? 1]}))});
    } else if (b.type === 'morph'){
      const layer = m.layerById.get(b.target);
      if (!layer){ console.warn('[model] morph target is not a layer:', b.target); continue; }
      const n = layer.basePos.length;
      m.bindings.push({type:'morph', target:b.target, param:b.param,
        keys:keys.map(k => {
          const off = new Float32Array(n);
          const raw = k.offsets || [];
          off.set(raw.slice(0, n));
          return {v:+k.v, off};
        })});
    }
  }
  console.log(`[model] '${m.name}': ${m.layers.length} layers, ${m.nodes.size} nodes, `
            + `${m.bindings.length} bindings, ${m.physics.length} springs`);
  return m;
}