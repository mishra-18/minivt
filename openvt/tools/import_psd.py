"""Import a layered PSD (e.g. a Live2D sample) into an OpenVT model folder.
Usage: python tools/import_psd.py input.psd models/name [--reverse-z]
Requires: pip install psd-tools"""
import json
import os
import re
import sys

try:
    from psd_tools import PSDImage
except ImportError:
    sys.exit("pip install psd-tools")

KEYS = [
    ("hair_back", ["back hair", "hair_back", "hairback", "後ろ髪", "後髪", "うしろ髪", "backhair"]),
    ("hair_front", ["front hair", "bangs", "fringe", "前髪", "hair_front", "fronthair"]),
    ("hair_side", ["hair", "髪", "サイド", "もみあげ"]),
    ("brow", ["brow", "眉"]),
    ("iris", ["iris", "pupil", "瞳", "黒目", "ハイライト", "highlight"]),
    ("eye", ["eye", "目", "まつ", "lash", "白目", "まぶた"]),
    ("mouth", ["mouth", "口", "lip", "唇", "teeth", "歯", "tongue", "舌"]),
    ("blush", ["blush", "cheek", "頬", "赤面"]),
    ("nose", ["nose", "鼻"]),
    ("face", ["face", "顔", "head", "頭", "skin", "肌", "ear", "耳", "輪郭"]),
    ("body", ["body", "体", "胴", "服", "cloth", "shirt", "arm", "腕", "hand", "手", "neck", "首",
              "leg", "脚", "skirt", "ribbon", "リボン", "首", "襟"]),
]


def classify(names):
    low = " ".join(names).lower()
    for cat, words in KEYS:
        if any(w in low for w in words):
            return cat
    return None


def safe_id(s, used):
    s = re.sub(r"[^0-9a-zA-Z_]+", "_", s).strip("_").lower() or "layer"
    base, i = s, 1
    while s in used:
        i += 1
        s = f"{base}_{i}"
    used.add(s)
    return s


def walk(group, chain=()):
    for layer in group:
        if not layer.is_visible():
            continue
        if layer.is_group():
            yield from walk(layer, chain + (layer.name,))
        else:
            yield chain, layer


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, out = sys.argv[1], sys.argv[2]
    reverse = "--reverse-z" in sys.argv
    psd = PSDImage.open(src)
    W, H = psd.width, psd.height
    tex_dir = os.path.join(out, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    leaves = list(walk(psd))
    if reverse:
        leaves.reverse()
    used, items = {"root", "body", "head", "face_group", "eye_l", "eye_r"}, []
    for z, (chain, layer) in enumerate(leaves):
        img = layer.topil()
        if img is None:
            continue
        img = img.convert("RGBA")
        bb = img.getbbox()
        if not bb:
            continue
        img = img.crop(bb)
        pos = [layer.left + bb[0], layer.top + bb[1]]
        lid = safe_id(layer.name, used)
        img.save(os.path.join(tex_dir, lid + ".png"))
        cx, cy = pos[0] + img.width / 2, pos[1] + img.height / 2
        items.append(dict(id=lid, z=z, pos=pos, size=[img.width, img.height], cx=cx, cy=cy,
                          cat=classify(list(chain) + [layer.name]), side="l" if cx < W / 2 else "r"))
    if not items:
        sys.exit("no pixel layers found")

    face_items = [i for i in items if i["cat"] in ("face", "eye", "iris", "mouth", "brow")]
    if face_items:
        fx0 = min(i["pos"][0] for i in face_items); fx1 = max(i["pos"][0] + i["size"][0] for i in face_items)
        fy0 = min(i["pos"][1] for i in face_items); fy1 = max(i["pos"][1] + i["size"][1] for i in face_items)
    else:
        fx0, fx1, fy0, fy1 = W * 0.3, W * 0.7, H * 0.1, H * 0.45
    head_pivot = [(fx0 + fx1) / 2, fy1]
    face_pivot = [(fx0 + fx1) / 2, (fy0 + fy1) / 2]

    def eye_pivot(side):
        es = [i for i in items if i["cat"] in ("eye", "iris") and i["side"] == side]
        if not es:
            return [W * (0.4 if side == "l" else 0.6), face_pivot[1]]
        return [sum(i["cx"] for i in es) / len(es), sum(i["cy"] for i in es) / len(es)]

    layers, bindings = [], []

    def tb(target, param, keys):
        bindings.append({"type": "transform", "target": target, "param": param,
                         "keys": [dict(v=v, **k) for v, k in keys]})

    for it in items:
        cat = it["cat"]
        d = {"id": it["id"], "texture": f"textures/{it['id']}.png", "z": it["z"], "pos": it["pos"]}
        top_center = [it["cx"], it["pos"][1]]
        if cat in ("hair_back", "hair_front", "hair_side"):
            d["parent"], d["pivot"], d["mesh"] = "head", top_center, {"grid": [3, 6]}
            sway = "hairFrontSway" if cat != "hair_side" else "hairSideSway"
            amp = 4 if cat == "hair_back" else 8 if cat == "hair_front" else 14
            tb(it["id"], sway, [(-1, {"rot": amp}), (1, {"rot": -amp})])
            tb(it["id"], "headX", [(-30, {"tx": 10 if cat == "hair_back" else -6}), (30, {"tx": -10 if cat == "hair_back" else 6})])
        elif cat == "face":
            d["parent"], d["mesh"] = "head", {"grid": [3, 3]}
        elif cat in ("eye", "iris"):
            d["parent"] = f"eye_{it['side']}"
            if cat == "iris":
                tb(it["id"], "eyeBallX", [(-1, {"tx": -it["size"][0] * 0.25}), (1, {"tx": it["size"][0] * 0.25})])
                tb(it["id"], "eyeBallY", [(-1, {"ty": -it["size"][1] * 0.15}), (1, {"ty": it["size"][1] * 0.15})])
        elif cat == "brow":
            d["parent"] = "face_group"
            tb(it["id"], "browY", [(-1, {"ty": it["size"][1] * 0.6}), (1, {"ty": -it["size"][1] * 0.8})])
        elif cat == "mouth":
            d["parent"], d["pivot"] = "face_group", top_center
            tb(it["id"], "mouthOpen", [(0, {}), (1, {"sy": 1.9})])
            tb(it["id"], "mouthForm", [(-1, {"sx": 0.8}), (1, {"sx": 1.25})])
        elif cat in ("blush", "nose"):
            d["parent"] = "face_group"
            if cat == "blush":
                d["blend"] = "multiply"
        elif cat == "body":
            d["parent"], d["mesh"] = "body", {"grid": [3, 4]}
        else:
            d["parent"] = "head" if it["cy"] < head_pivot[1] else "body"
        layers.append(d)

    tb("head", "headX", [(-30, {"tx": -W * 0.025}), (30, {"tx": W * 0.025})])
    tb("face_group", "headX", [(-30, {"tx": -W * 0.02}), (30, {"tx": W * 0.02})])
    tb("head", "headY", [(-30, {"ty": H * 0.012}), (30, {"ty": -H * 0.012})])
    tb("face_group", "headY", [(-30, {"ty": H * 0.015}), (30, {"ty": -H * 0.015})])
    tb("head", "headAngleZ", [(-30, {"rot": -18}), (30, {"rot": 18})])
    tb("body", "bodyX", [(-1, {"rot": -3}), (1, {"rot": 3})])
    tb("body", "breath", [(0, {}), (1, {"sy": 1.012})])
    tb("eye_l", "eyeOpenL", [(0, {"sy": 0.08}), (1, {})])
    tb("eye_r", "eyeOpenR", [(0, {"sy": 0.08}), (1, {})])

    model = {
        "name": os.path.basename(out.rstrip("/\\")),
        "canvas": {"width": W, "height": H},
        "params": [
            {"id": "headX", "min": -30, "max": 30, "default": 0},
            {"id": "headY", "min": -30, "max": 30, "default": 0},
            {"id": "headAngleZ", "min": -30, "max": 30, "default": 0},
            {"id": "bodyX", "min": -1, "max": 1, "default": 0},
            {"id": "eyeOpenL", "min": 0, "max": 1, "default": 1},
            {"id": "eyeOpenR", "min": 0, "max": 1, "default": 1},
            {"id": "eyeBallX", "min": -1, "max": 1, "default": 0},
            {"id": "eyeBallY", "min": -1, "max": 1, "default": 0},
            {"id": "mouthOpen", "min": 0, "max": 1, "default": 0},
            {"id": "mouthForm", "min": -1, "max": 1, "default": 0},
            {"id": "browY", "min": -1, "max": 1, "default": 0},
            {"id": "breath", "min": 0, "max": 1, "default": 0},
            {"id": "hairFrontSway", "min": -1, "max": 1, "default": 0},
            {"id": "hairSideSway", "min": -1, "max": 1, "default": 0},
        ],
        "nodes": [
            {"id": "root", "pivot": [W / 2, H / 2]},
            {"id": "body", "parent": "root", "pivot": [W / 2, H]},
            {"id": "head", "parent": "body", "pivot": head_pivot},
            {"id": "face_group", "parent": "head", "pivot": face_pivot},
            {"id": "eye_l", "parent": "face_group", "pivot": eye_pivot("l")},
            {"id": "eye_r", "parent": "face_group", "pivot": eye_pivot("r")},
        ],
        "layers": layers,
        "bindings": bindings,
        "physics": [
            {"output": "hairFrontSway", "mode": "lag", "stiffness": 140, "damping": 9, "gain": 2.5,
             "inputs": [{"param": "headX", "weight": 1.0}, {"param": "headAngleZ", "weight": 0.6}]},
            {"output": "hairSideSway", "mode": "lag", "stiffness": 90, "damping": 6, "gain": 3.0,
             "inputs": [{"param": "headX", "weight": 1.0}, {"param": "headAngleZ", "weight": 0.8}]},
            {"output": "bodyX", "mode": "follow", "stiffness": 40, "damping": 8, "gain": 1.0,
             "inputs": [{"param": "headX", "weight": 0.7}]},
        ],
        "mapping": {"mirror": True},
    }
    with open(os.path.join(out, "model.json"), "w", encoding="utf-8") as f:
        json.dump(model, f, indent=1, ensure_ascii=False)

    print(f"[import] {len(layers)} layers -> {out}")
    unknown = [i["id"] for i in items if i["cat"] is None]
    if unknown:
        print("[import] could not classify (attached by position):", ", ".join(unknown))
    print("[import] if layering looks inverted, rerun with --reverse-z")
    print(f"[import] run:  python main.py --model {out}")


if __name__ == "__main__":
    main()