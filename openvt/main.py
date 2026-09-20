"""OpenVT - minimal open-source 2D VTuber renderer.   python main.py [--model models/demo]"""
from __future__ import annotations
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import glfw
from OpenGL.GL import glGetString, GL_VERSION, GL_RENDERER

from core.params import ParamTable
from core.model import load_model
from core.deform import DeformEngine
from core.physics import PhysicsSystem
from render.renderer import Renderer
from track.mapper import Mapper, IdleAnimator
from track.mouse_tracker import MouseTracker

BG = {"green": (0.0, 0.69, 0.25), "magenta": (1.0, 0.0, 1.0), "black": (0.0, 0.0, 0.0), "gray": (0.18, 0.18, 0.2)}


def parse_bg(s):
    if s in BG:
        return BG[s]
    r, g, b = (float(x) for x in s.split(","))
    return (r / 255, g / 255, b / 255) if max(r, g, b) > 1 else (r, g, b)


def ensure_demo(path):
    if not os.path.exists(os.path.join(path, "model.json")):
        from tools.gen_placeholder import generate
        print("[main] no model found, generating placeholder character ...")
        generate(path)


def make_tracker(args, window):
    if args.no_tracker:
        return MouseTracker(window)
    try:
        from track.mediapipe_tracker import MediaPipeTracker
        t = MediaPipeTracker(camera=args.camera,
                             model_path=os.path.join(ROOT, "assets", "face_landmarker.task"),
                             preview=args.preview)
        t.start()
        return t
    except Exception as e:
        print(f"[tracker] MediaPipe unavailable ({type(e).__name__}: {e})")
        print("[tracker] -> mouse tracker. Move mouse = head, LMB = mouth, RMB = blink. See README for webcam setup.")
        return MouseTracker(window)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.path.join(ROOT, "models", "demo"))
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--no-tracker", action="store_true", help="skip webcam, use mouse")
    ap.add_argument("--preview", action="store_true", help="show webcam + landmarks")
    ap.add_argument("--bg", default="green", help="green|magenta|black|gray|r,g,b")
    ap.add_argument("--size", default="768x768")
    ap.add_argument("--no-vsync", action="store_true")
    args = ap.parse_args()

    ensure_demo(args.model)
    model = load_model(args.model)
    params = ParamTable()
    for p in model.params:
        params.define(p["id"], p.get("min", 0), p.get("max", 1), p.get("default"))
    deform = DeformEngine(model, params)
    physics = PhysicsSystem(model.physics)

    if not glfw.init():
        raise SystemExit("glfw init failed")
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, True)
    w, h = (int(v) for v in args.size.lower().split("x"))
    window = glfw.create_window(w, h, "OpenVT", None, None)
    if not window:
        glfw.terminate()
        raise SystemExit("could not create an OpenGL 3.3 window - update your GPU drivers")
    glfw.make_context_current(window)
    glfw.swap_interval(0 if args.no_vsync else 1)
    print("[gl]", glGetString(GL_VERSION).decode(), "|", glGetString(GL_RENDERER).decode())

    fbw, fbh = glfw.get_framebuffer_size(window)
    renderer = Renderer(model, fbw, fbh, parse_bg(args.bg))
    glfw.set_framebuffer_size_callback(window, lambda _w, W, H: renderer.resize(W, H))

    tracker = make_tracker(args, window)
    mapper = Mapper(model.mapping)
    if isinstance(tracker, MouseTracker):
        mapper.mirror = True
    idle = IdleAnimator()

    pids = params.ids()
    state = {"sel": 0, "overrides": set(), "tracker_on": True, "quit": False}

    def on_key(_win, key, _sc, action, mods):
        if action != glfw.PRESS:
            return
        if key == glfw.KEY_ESCAPE:
            state["quit"] = True
        elif key == glfw.KEY_TAB:
            state["sel"] = (state["sel"] + (-1 if mods & glfw.MOD_SHIFT else 1)) % len(pids)
        elif key == glfw.KEY_R:
            params.reset(); state["overrides"].clear(); physics.reset()
        elif key == glfw.KEY_C:
            mapper.calibrate(); print("[mapper] neutral pose calibrated")
        elif key == glfw.KEY_T:
            state["tracker_on"] = not state["tracker_on"]
        elif key == glfw.KEY_P:
            physics.enabled = not physics.enabled
        elif key == glfw.KEY_M:
            mapper.mirror = not mapper.mirror; print("[mapper] mirror =", mapper.mirror)
        elif key == glfw.KEY_BACKSPACE:
            sel = pids[state["sel"]]; params.reset(sel); state["overrides"].discard(sel)

    glfw.set_key_callback(window, on_key)
    print("[keys] Tab/Shift+Tab select param | Up/Down adjust | Backspace release | R reset all | "
          "C calibrate | T tracker on/off | P physics on/off | M mirror | Esc quit")

    t_prev = glfw.get_time()
    fps_t, frames, fps = t_prev, 0, 0.0
    while not glfw.window_should_close(window) and not state["quit"]:
        glfw.poll_events()
        t = glfw.get_time()
        dt = min(t - t_prev, 0.1)
        t_prev = t

        frame = tracker.poll() if state["tracker_on"] else None
        tracked = mapper.apply(frame, params, t, state["overrides"])
        idle.apply(params, t, dt, tracked, state["overrides"])

        sel = pids[state["sel"]]
        d = params.defs[sel]
        step = (d.max - d.min) * dt * 0.8
        if glfw.get_key(window, glfw.KEY_UP) == glfw.PRESS:
            params.add(sel, step); state["overrides"].add(sel)
        if glfw.get_key(window, glfw.KEY_DOWN) == glfw.PRESS:
            params.add(sel, -step); state["overrides"].add(sel)

        physics.step(params, dt, state["overrides"])
        deform.evaluate()
        renderer.draw()
        glfw.swap_buffers(window)

        frames += 1
        if t - fps_t >= 0.5:
            fps = frames / (t - fps_t); frames, fps_t = 0, t
            src = tracker.name if state["tracker_on"] else "off"
            face = "face" if tracked else "idle"
            glfw.set_window_title(window, f"OpenVT | {model.name} | {src}:{face} | {fps:.0f} fps | "
                                          f"[{sel}] {params.get(sel):+.2f} | phys {'on' if physics.enabled else 'off'}")

    tracker.stop()
    glfw.terminate()


if __name__ == "__main__":
    main()