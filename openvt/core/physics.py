from __future__ import annotations


class Spring:
    """Damped spring on a param target.
    mode 'lag'   : output = (x - target)  -> hair trailing behind the head
    mode 'follow': output = x             -> body lazily following the head
    Inputs/outputs are in signed -1..1 param space."""

    def __init__(self, cfg: dict):
        self.output = cfg["output"]
        self.inputs = [(i["param"], float(i.get("weight", 1.0))) for i in cfg.get("inputs", [])]
        self.k = float(cfg.get("stiffness", 120.0))
        self.c = float(cfg.get("damping", 10.0))
        self.gain = float(cfg.get("gain", 1.0))
        self.mode = cfg.get("mode", "lag")
        self.x = None
        self.v = 0.0

    def target(self, params) -> float:
        return sum(w * params.signed(p) for p, w in self.inputs)

    def step(self, params, dt: float):
        t = self.target(params)
        if self.x is None:
            self.x, self.v = t, 0.0
        n = max(1, int(dt / (1.0 / 240.0)) + 1)
        h = dt / n
        for _ in range(n):
            a = -self.k * (self.x - t) - self.c * self.v
            self.v += a * h
            self.x += self.v * h
        out = (self.x - t) if self.mode == "lag" else self.x
        params.set_signed(self.output, out * self.gain)

    def reset(self):
        self.x, self.v = None, 0.0


class PhysicsSystem:
    def __init__(self, cfgs: list[dict]):
        self.springs = [Spring(c) for c in cfgs]
        self.enabled = True

    def step(self, params, dt: float, skip=()):
        if not self.enabled:
            return
        dt = min(dt, 0.05)
        for s in self.springs:
            if s.output in skip:
                continue
            s.step(params, dt)

    def reset(self):
        for s in self.springs:
            s.reset()