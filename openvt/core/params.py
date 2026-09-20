from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ParamDef:
    id: str
    min: float
    max: float
    default: float


class ParamTable:
    """Named, clamped floats. The only interface between tracking and rendering."""

    def __init__(self):
        self.defs: dict[str, ParamDef] = {}
        self.values: dict[str, float] = {}

    def define(self, pid: str, mn: float = 0.0, mx: float = 1.0, default=None):
        if default is None:
            default = min(max(0.0, mn), mx)
        self.defs[pid] = ParamDef(pid, float(mn), float(mx), float(default))
        self.values[pid] = float(default)

    def has(self, pid): return pid in self.defs
    def ids(self): return list(self.defs.keys())

    def get(self, pid, fallback=0.0) -> float:
        return self.values.get(pid, fallback)

    def set(self, pid, v):
        d = self.defs.get(pid)
        if d is None:
            return
        self.values[pid] = min(max(float(v), d.min), d.max)

    def add(self, pid, dv):
        self.set(pid, self.get(pid) + dv)

    def signed(self, pid) -> float:
        """Value mapped to -1..1 around default (default -> 0)."""
        d = self.defs.get(pid)
        if d is None:
            return 0.0
        v = self.values[pid]
        span = (d.max - d.default) if v >= d.default else (d.default - d.min)
        return 0.0 if span <= 0 else (v - d.default) / span

    def set_signed(self, pid, s):
        d = self.defs.get(pid)
        if d is None:
            return
        s = min(max(float(s), -1.0), 1.0)
        span = (d.max - d.default) if s >= 0 else (d.default - d.min)
        self.set(pid, d.default + s * span)

    def reset(self, pid=None):
        if pid is None:
            for k, d in self.defs.items():
                self.values[k] = d.default
        elif pid in self.defs:
            self.values[pid] = self.defs[pid].default