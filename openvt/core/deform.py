from __future__ import annotations
import math
import numpy as np


def trs(pivot, tx, ty, rot_deg, sx, sy) -> np.ndarray:
    """M = T(pivot + t) * R * S * T(-pivot), 3x3 in canvas pixel space (y down)."""
    r = math.radians(rot_deg)
    c, s = math.cos(r), math.sin(r)
    a, b = c * sx, -s * sy
    d, e = s * sx, c * sy
    px, py = pivot
    return np.array([[a, b, px + tx - (a * px + b * py)],
                     [d, e, py + ty - (d * px + e * py)],
                     [0.0, 0.0, 1.0]])


def lerp_keys(keys, v):
    if v <= keys[0][0]:
        return keys[0][1]
    if v >= keys[-1][0]:
        return keys[-1][1]
    for i in range(len(keys) - 1):
        v0, a = keys[i]
        v1, b = keys[i + 1]
        if v0 <= v <= v1:
            t = 0.0 if v1 == v0 else (v - v0) / (v1 - v0)
            return a + (b - a) * t
    return keys[-1][1]


class DeformEngine:
    def __init__(self, model, params):
        self.model = model
        self.params = params
        self.nodes = model.nodes
        self.order = self._topo()
        self.tbind: dict[str, list] = {}
        self.mbind: dict[str, list] = {}
        for b in model.bindings:
            (self.tbind if b.type == "transform" else self.mbind).setdefault(b.target, []).append(b)
        self.world = {nid: np.eye(3) for nid in self.nodes}

    def _topo(self):
        depth = {}

        def d(nid, seen=()):
            if nid in depth:
                return depth[nid]
            n = self.nodes[nid]
            if n.parent is None or n.parent not in self.nodes or nid in seen:
                depth[nid] = 0
            else:
                depth[nid] = d(n.parent, seen + (nid,)) + 1
            return depth[nid]

        for nid in self.nodes:
            d(nid)
        return sorted(self.nodes, key=lambda k: depth[k])

    def evaluate(self):
        p = self.params
        for nid in self.order:
            n = self.nodes[nid]
            acc = np.array([0.0, 0.0, 0.0, 1.0, 1.0])
            for b in self.tbind.get(nid, ()):
                k = lerp_keys(b.keys, p.get(b.param))
                acc[:3] += k[:3]
                acc[3:] *= k[3:]
            local = trs(n.pivot, *acc)
            parent = self.world.get(n.parent) if n.parent is not None else None
            self.world[nid] = local if parent is None else parent @ local

        for layer in self.model.layers:
            pos = layer.base_pos
            mb = self.mbind.get(layer.id)
            if mb:
                pos = pos.copy()
                for b in mb:
                    pos += lerp_keys(b.keys, p.get(b.param))
            M = self.world[layer.id]
            layer.cur_pos = np.ascontiguousarray((pos @ M[:2, :2].T + M[:2, 2]).astype(np.float32))