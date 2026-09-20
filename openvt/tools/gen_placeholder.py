"""Generates the built-in placeholder character: textures/*.png + model.json.
Run standalone:  python tools/gen_placeholder.py [out_dir]"""
import json
import os
import sys
from PIL import Image, ImageDraw, ImageFilter

W = H = 1024
SS = 2  # supersample for antialiasing

SKIN = (255, 226, 205, 255)
HAIR = (98, 66, 148, 255)
HAIR_LIGHT = (150, 118, 200, 255)
SHIRT = (78, 102, 178, 255)
COLLAR = (240, 240, 250, 255)
WHITE = (255, 255, 255, 255)
IRIS = (58, 168, 178, 255)
IRIS_DARK = (28, 100, 125, 255)
INK = (46, 34, 60, 255)
MOUTH = (178, 66, 86, 255)
BLUSH = (255, 140, 150, 120)


def _new(): return Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
def _s(pts): return [(x * SS, y * SS) for x, y in pts]
def _box(x0, y0, x1, y1): return [x0 * SS, y0 * SS, x1 * SS, y1 * SS]
def _mirror(pts): return [(W - x, y) for x, y in pts]


def _finish(im, blur=0):
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur * SS))
    return im.resize((W, H), Image.LANCZOS)


def draw_body():
    im = _new(); d = ImageDraw.Draw(im)
    d.rectangle(_box(470, 560, 554, 700), fill=SKIN)
    d.polygon(_s([(360, 690), (664, 690), (722, 770), (740, 1024), (284, 1024), (302, 770)]), fill=SHIRT)
    d.polygon(_s([(458, 690), (566, 690), (512, 750)]), fill=COLLAR)
    return _finish(im)


def draw_face():
    im = _new(); d = ImageDraw.Draw(im)
    d.ellipse(_box(342, 300, 682, 700), fill=SKIN)
    d.ellipse(_box(330, 470, 360, 540), fill=SKIN)
    d.ellipse(_box(664, 470, 694, 540), fill=SKIN)
    return _finish(im)


def draw_hair_back():
    im = _new(); d = ImageDraw.Draw(im)
    d.ellipse(_box(300, 240, 724, 720), fill=HAIR)
    d.polygon(_s([(300, 480), (724, 480), (746, 880), (700, 850), (660, 905), (600, 865),
                  (512, 900), (424, 865), (364, 905), (324, 850), (278, 880)]), fill=HAIR)
    return _finish(im)


def draw_hair_front():
    im = _new(); d = ImageDraw.Draw(im)
    top = [(322, 480), (332, 380), (372, 312), (440, 278), (512, 268), (584, 278), (652, 312), (692, 380), (702, 480)]
    zig = [(672, 530), (640, 458), (606, 522), (572, 446), (540, 512), (508, 436), (476, 508),
           (444, 448), (410, 520), (376, 458), (346, 528)]
    d.polygon(_s(top + zig), fill=HAIR)
    d.line(_s([(372, 330), (440, 296), (512, 286)]), fill=HAIR_LIGHT, width=10 * SS)
    return _finish(im)


def draw_hair_side(left=True):
    im = _new(); d = ImageDraw.Draw(im)
    pts = [(296, 420), (354, 410), (364, 700), (348, 830), (322, 770), (298, 810), (288, 600)]
    d.polygon(_s(pts if left else _mirror(pts)), fill=HAIR)
    return _finish(im)


def draw_eye_white(cx):
    im = _new(); d = ImageDraw.Draw(im)
    d.ellipse(_box(cx - 46, 468, cx + 46, 536), fill=WHITE)
    d.arc(_box(cx - 48, 464, cx + 48, 540), 180, 360, fill=INK, width=9 * SS)
    d.arc(_box(cx - 46, 468, cx + 46, 536), 0, 180, fill=INK, width=3 * SS)
    return _finish(im)


def draw_eye_iris(cx):
    im = _new(); d = ImageDraw.Draw(im)
    d.ellipse(_box(cx - 30, 474, cx + 30, 540), fill=IRIS)
    d.chord(_box(cx - 30, 474, cx + 30, 540), 180, 360, fill=IRIS_DARK)
    d.ellipse(_box(cx - 14, 490, cx + 14, 528), fill=INK)
    d.ellipse(_box(cx - 20, 480, cx - 6, 494), fill=WHITE)
    return _finish(im)


def draw_brow(cx):
    im = _new(); d = ImageDraw.Draw(im)
    d.line(_s([(cx - 42, 446), (cx, 432), (cx + 42, 444)]), fill=INK, width=7 * SS, joint="curve")
    return _finish(im)


def draw_mouth():
    im = _new(); d = ImageDraw.Draw(im)
    d.rounded_rectangle(_box(488, 590, 536, 610), radius=10 * SS, fill=MOUTH)
    return _finish(im)


def draw_blush(cx):
    im = _new(); d = ImageDraw.Draw(im)
    d.ellipse(_box(cx - 38, 540, cx + 38, 580), fill=BLUSH)
    return _finish(im, blur=6)


def mouth_offsets(cols=4, rows=4, amount=22.0):
    off = []
    for r in range(rows + 1):
        v = r / rows
        dy = max(0.0, (v - 0.35) / 0.65) * amount
        for _ in range(cols + 1):
            off += [0.0, round(dy, 2)]
    return off


def generate(out_dir):
    tex_dir = os.path.join(out_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)
    layers = []

    def layer(lid, im, parent, z, **kw):
        bb = im.getbbox()
        im.crop(bb).save(os.path.join(tex_dir, lid + ".png"))
        d = {"id": lid, "texture": f"textures/{lid}.png", "parent": parent, "z": z, "pos": [bb[0], bb[1]]}
        d.update(kw)
        layers.append(d)

    layer("hair_back", draw_hair_back(), "head", 0, pivot=[512, 300], mesh={"grid": [4, 6]})
    layer("torso", draw_body(), "body", 1, mesh={"grid": [3, 4]})
    layer("face", draw_face(), "head", 2, mesh={"grid": [3, 3]})
    layer("blush_l", draw_blush(432), "face_group", 3, blend="multiply")
    layer("blush_r", draw_blush(592), "face_group", 3, blend="multiply")
    layer("eye_white_l", draw_eye_white(440), "eye_l", 4)
    layer("eye_white_r", draw_eye_white(584), "eye_r", 4)
    layer("eye_iris_l", draw_eye_iris(440), "eye_l", 5, maskedBy=["eye_white_l"])
    layer("eye_iris_r", draw_eye_iris(584), "eye_r", 5, maskedBy=["eye_white_r"])
    layer("brow_l", draw_brow(440), "face_group", 6)
    layer("brow_r", draw_brow(584), "face_group", 6)
    layer("mouth", draw_mouth(), "face_group", 7, pivot=[512, 600], mesh={"grid": [4, 4], "clip": False})
    layer("hair_side_l", draw_hair_side(True), "head", 8, pivot=[325, 415], mesh={"grid": [2, 6]})
    layer("hair_side_r", draw_hair_side(False), "head", 8, pivot=[699, 415], mesh={"grid": [2, 6]})
    layer("hair_front", draw_hair_front(), "head", 9, pivot=[512, 290], mesh={"grid": [6, 3]})

    def tb(target, param, keys):
        return {"type": "transform", "target": target, "param": param,
                "keys": [dict(v=v, **k) for v, k in keys]}

    bindings = [
        tb("head", "headX", [(-30, {"tx": -28}), (30, {"tx": 28})]),
        tb("face_group", "headX", [(-30, {"tx": -22}), (30, {"tx": 22})]),
        tb("hair_front", "headX", [(-30, {"tx": -8}), (30, {"tx": 8})]),
        tb("hair_back", "headX", [(-30, {"tx": 12}), (30, {"tx": -12})]),
        tb("head", "headY", [(-30, {"ty": 14}), (30, {"ty": -14})]),
        tb("face_group", "headY", [(-30, {"ty": 16}), (30, {"ty": -16})]),
        tb("hair_front", "headY", [(-30, {"ty": 6}), (30, {"ty": -6})]),
        tb("head", "headAngleZ", [(-30, {"rot": -18}), (30, {"rot": 18})]),
        tb("body", "bodyX", [(-1, {"rot": -4, "tx": -10}), (1, {"rot": 4, "tx": 10})]),
        tb("body", "breath", [(0, {}), (1, {"sy": 1.015, "ty": -3})]),
        tb("eye_l", "eyeOpenL", [(0, {"sy": 0.06}), (1, {})]),
        tb("eye_r", "eyeOpenR", [(0, {"sy": 0.06}), (1, {})]),
        tb("eye_iris_l", "eyeBallX", [(-1, {"tx": -12}), (1, {"tx": 12})]),
        tb("eye_iris_r", "eyeBallX", [(-1, {"tx": -12}), (1, {"tx": 12})]),
        tb("eye_iris_l", "eyeBallY", [(-1, {"ty": -8}), (1, {"ty": 8})]),
        tb("eye_iris_r", "eyeBallY", [(-1, {"ty": -8}), (1, {"ty": 8})]),
        {"type": "morph", "target": "mouth", "param": "mouthOpen",
         "keys": [{"v": 0, "offsets": []}, {"v": 1, "offsets": mouth_offsets()}]},
        tb("mouth", "mouthForm", [(-1, {"sx": 0.75, "ty": 4}), (1, {"sx": 1.3, "ty": -3})]),
        tb("brow_l", "browY", [(-1, {"ty": 10}), (1, {"ty": -12})]),
        tb("brow_r", "browY", [(-1, {"ty": 10}), (1, {"ty": -12})]),
        tb("hair_front", "hairFrontSway", [(-1, {"rot": 10, "tx": -6}), (1, {"rot": -10, "tx": 6})]),
        tb("hair_back", "hairFrontSway", [(-1, {"rot": 5}), (1, {"rot": -5})]),
        tb("hair_side_l", "hairSideSway", [(-1, {"rot": 16}), (1, {"rot": -16})]),
        tb("hair_side_r", "hairSideSway", [(-1, {"rot": 16}), (1, {"rot": -16})]),
    ]

    model = {
        "name": "demo",
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
            {"id": "root", "pivot": [512, 512]},
            {"id": "body", "parent": "root", "pivot": [512, 1000]},
            {"id": "head", "parent": "body", "pivot": [512, 600]},
            {"id": "face_group", "parent": "head", "pivot": [512, 495]},
            {"id": "eye_l", "parent": "face_group", "pivot": [440, 502]},
            {"id": "eye_r", "parent": "face_group", "pivot": [584, 502]},
        ],
        "layers": layers,
        "bindings": bindings,
        "physics": [
            {"output": "hairFrontSway", "mode": "lag", "stiffness": 140, "damping": 9, "gain": 2.5,
             "inputs": [{"param": "headX", "weight": 1.0}, {"param": "headAngleZ", "weight": 0.6},
                        {"param": "headY", "weight": 0.3}]},
            {"output": "hairSideSway", "mode": "lag", "stiffness": 90, "damping": 6, "gain": 3.0,
             "inputs": [{"param": "headX", "weight": 1.0}, {"param": "headAngleZ", "weight": 0.8}]},
            {"output": "bodyX", "mode": "follow", "stiffness": 40, "damping": 8, "gain": 1.0,
             "inputs": [{"param": "headX", "weight": 0.7}]},
        ],
        "mapping": {"mirror": True},
    }
    with open(os.path.join(out_dir, "model.json"), "w", encoding="utf-8") as f:
        json.dump(model, f, indent=1)
    print(f"[gen] wrote placeholder model to {out_dir} ({len(layers)} layers)")


if __name__ == "__main__":
    generate(sys.argv[1] if len(sys.argv) > 1 else os.path.join("models", "demo"))