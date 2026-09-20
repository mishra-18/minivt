from __future__ import annotations
import math
import random
from core.filter import OneEuroFilter

HEAD_PARAMS = {"headX", "headY", "headAngleZ"}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Mapper:
    """TrackingFrame -> params. All signs/gains live here, not in the model."""

    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {}
        self.mirror = bool(cfg.get("mirror", True))
        self.yaw_sign = float(cfg.get("yaw_sign", 1.0))
        self.pitch_sign = float(cfg.get("pitch_sign", 1.0))
        self.roll_sign = float(cfg.get("roll_sign", 1.0))
        self.head_gain = float(cfg.get("head_gain", 1.3))
        self.deadzone = float(cfg.get("deadzone_deg", 0.6))
        self.blink_lo, self.blink_hi = cfg.get("blink_range", [0.35, 0.7])
        self.link_eyes = float(cfg.get("link_eyes", 0.3))
        self.head_cutoff = float(cfg.get("head_cutoff", 1.5))
        self.face_cutoff = float(cfg.get("face_cutoff", 4.0))
        self.beta = float(cfg.get("smooth_beta", 0.1))
        self.filters: dict[str, OneEuroFilter] = {}
        self.neutral = [0.0, 0.0, 0.0]
        self._calib = False

    def calibrate(self):
        self._calib = True

    def _f(self, pid, x, t):
        f = self.filters.get(pid)
        if f is None:
            cutoff = self.head_cutoff if pid in HEAD_PARAMS else self.face_cutoff
            f = self.filters[pid] = OneEuroFilter(cutoff, self.beta)
        return f(x, t)

    def _open(self, raw_open):
        x = _clamp((raw_open - self.blink_lo) / max(self.blink_hi - self.blink_lo, 1e-3), 0.0, 1.0)
        return x * x * (3 - 2 * x)

    def _dz(self, v):
        return 0.0 if abs(v) < self.deadzone else v - math.copysign(self.deadzone, v)

    def apply(self, frame, params, t, skip=()) -> bool:
        if frame is None or not frame.ok:
            return False
        if self._calib:
            self.neutral = [frame.yaw, frame.pitch, frame.roll]
            for f in self.filters.values():
                f.reset()
            self._calib = False

        ms = -1.0 if self.mirror else 1.0
        yaw = self._dz(frame.yaw - self.neutral[0])
        pitch = self._dz(frame.pitch - self.neutral[1])
        roll = self._dz(frame.roll - self.neutral[2])

        out = {
            "headX": yaw * ms * self.yaw_sign * self.head_gain,
            "headY": -pitch * self.pitch_sign * self.head_gain,
            "headAngleZ": -roll * ms * self.roll_sign,
            "mouthOpen": _clamp(frame.jaw_open * 1.6, 0.0, 1.0),
            "mouthForm": _clamp(frame.smile * 1.8 - frame.pucker * 1.5, -1.0, 1.0),
            "browY": _clamp((frame.brow_up - frame.brow_down) * 1.6, -1.0, 1.0),
            "eyeBallX": _clamp(-ms * (frame.look_r - frame.look_l) * 1.5, -1.0, 1.0),
            "eyeBallY": _clamp((frame.look_d - frame.look_u) * 1.5, -1.0, 1.0),
        }
        oL, oR = self._open(1 - frame.blink_l), self._open(1 - frame.blink_r)
        if abs(oL - oR) < self.link_eyes:
            oL = oR = (oL + oR) / 2
        if self.mirror:
            out["eyeOpenL"], out["eyeOpenR"] = oL, oR
        else:
            out["eyeOpenL"], out["eyeOpenR"] = oR, oL

        for pid, v in out.items():
            if pid in skip or not params.has(pid):
                continue
            params.set(pid, self._f(pid, v, t))
        return True


class IdleAnimator:
    """Breathing always; gentle sway + auto blink when nothing is tracking."""

    def __init__(self):
        self.next_blink = 2.0
        self.blink_t0 = None

    def apply(self, params, t, dt, tracked: bool, skip=()):
        if params.has("breath") and "breath" not in skip:
            params.set("breath", 0.5 - 0.5 * math.cos(t * 2 * math.pi / 3.6))
        if tracked:
            return
        idle = {"headX": 5 * math.sin(t * 0.6), "headY": 2.5 * math.sin(t * 0.9 + 1),
                "headAngleZ": 2 * math.sin(t * 0.45), "eyeBallX": 0.25 * math.sin(t * 0.3)}
        for pid, v in idle.items():
            if pid not in skip:
                params.set(pid, v)
        if self.blink_t0 is None and t >= self.next_blink:
            self.blink_t0 = t
        o = 1.0
        if self.blink_t0 is not None:
            u = (t - self.blink_t0) / 0.22
            if u >= 1.0:
                self.blink_t0 = None
                self.next_blink = t + random.uniform(2.0, 5.0)
            else:
                o = abs(u * 2 - 1)
        for pid in ("eyeOpenL", "eyeOpenR"):
            if pid not in skip:
                params.set(pid, o)