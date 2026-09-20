from __future__ import annotations
import json
import os
import numpy as np
from PIL import Image
from .meshgen import grid_mesh


class Node:
    def __init__(self, id, parent, pivot):
        self.id = id
        self.parent = parent
        self.pivot = np.asarray(pivot, dtype=np.float64)


class Layer:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Binding:
    def __init__(self, type, target, param, keys):
        self.type, self.target, self.param, self.keys = type, target, param, keys


class Model:
    def __init__(self):
        self.name = "model"
        self.width = 1024
        self.height = 1024
        self.params: list[dict] = []
        self.nodes: dict[str, Node] = {}
        self.layers: list[Layer] = []
        self.layer_by_id: dict[str, Layer] = {}
        self.bindings: list[Binding] = []
        self.physics: list[dict] = []
        self.mapping: dict = {}


def load_model(path: str) -> Model:
    json_path = os.path.join(path, "model.json") if os.path.isdir(path) else path
    base = os.path.dirname(os.path.abspath(json_path))
    with open(json_path, encoding="utf-8") as f:
        d = json.load(f)

    m = Model()
    m.name = d.get("name", os.path.basename(base))
    canvas = d.get("canvas", {})
    m.width, m.height = int(canvas.get("width", 1024)), int(canvas.get("height", 1024))
    m.params = d.get("params", [])

    for n in d.get("nodes", []):
        m.nodes[n["id"]] = Node(n["id"], n.get("parent"), n.get("pivot", [m.width / 2, m.height / 2]))

    for i, l in enumerate(d["layers"]):
        img = Image.open(os.path.join(base, l["texture"])).convert("RGBA")
        arr = np.ascontiguousarray(np.asarray(img, dtype=np.uint8))
        tw, th = img.size
        pos = l.get("pos", [0, 0])
        mesh = l.get("mesh", {})
        cols, rows = mesh.get("grid", [1, 1])
        clip = mesh.get("clip", True) and (cols * rows > 1)
        bp, uv, idx = grid_mesh(pos[0], pos[1], tw, th, cols, rows, arr[:, :, 3] if clip else None)
        masked = l.get("maskedBy") or []
        if isinstance(masked, str):
            masked = [masked]
        layer = Layer(
            id=l["id"], parent=l.get("parent"), texture=arr, tex_size=(tw, th),
            z=float(l.get("z", i)), order=i, opacity=float(l.get("opacity", 1.0)),
            blend=l.get("blend", "normal"), tint=l.get("tint", [1, 1, 1, 1]),
            masked_by=masked, visible=bool(l.get("visible", True)),
            base_pos=bp, uv=uv, idx=idx, cur_pos=bp.copy(),
        )
        if layer.id in m.nodes:
            raise ValueError(f"duplicate id: {layer.id}")
        m.layers.append(layer)
        m.layer_by_id[layer.id] = layer
        m.nodes[layer.id] = Node(layer.id, layer.parent, l.get("pivot", [pos[0] + tw / 2, pos[1] + th / 2]))

    m.layers.sort(key=lambda L: (L.z, L.order))

    for n in m.nodes.values():
        if n.parent is not None and n.parent not in m.nodes:
            print(f"[model] warning: {n.id} has unknown parent {n.parent}; attaching to root")
            n.parent = None

    for b in d.get("bindings", []):
        keys = sorted(b["keys"], key=lambda k: k["v"])
        if b["target"] not in m.nodes:
            print(f"[model] warning: binding targets unknown '{b['target']}', skipped")
            continue
        if b["type"] == "transform":
            kk = [(float(k["v"]), np.array([k.get("tx", 0.0), k.get("ty", 0.0), k.get("rot", 0.0),
                                             k.get("sx", 1.0), k.get("sy", 1.0)], dtype=np.float64)) for k in keys]
        elif b["type"] == "morph":
            layer = m.layer_by_id.get(b["target"])
            if layer is None:
                print(f"[model] warning: morph target {b['target']} is not a layer, skipped")
                continue
            n = layer.base_pos.shape[0]
            kk = []
            for k in keys:
                off = np.zeros((n, 2), dtype=np.float32)
                raw = np.asarray(k.get("offsets", []), dtype=np.float32).reshape(-1, 2)
                cnt = min(n, raw.shape[0])
                off[:cnt] = raw[:cnt]
                kk.append((float(k["v"]), off))
        else:
            print(f"[model] warning: unknown binding type {b['type']}")
            continue
        m.bindings.append(Binding(b["type"], b["target"], b["param"], kk))

    m.physics = d.get("physics", [])
    m.mapping = d.get("mapping", {})
    print(f"[model] loaded '{m.name}': {len(m.layers)} layers, {len(m.nodes)} nodes, "
          f"{len(m.bindings)} bindings, {len(m.physics)} springs")
    return m