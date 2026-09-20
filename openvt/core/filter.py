import math


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2.0 * math.pi * max(cutoff, 1e-6))
    return 1.0 / (1.0 + tau / max(dt, 1e-6))


class OneEuroFilter:
    """Adaptive low-pass: smooth when still, responsive when moving."""

    def __init__(self, min_cutoff=1.0, beta=0.05, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self):
        self.t = None
        self.x = None
        self.dx = 0.0

    def __call__(self, x: float, t: float) -> float:
        if self.t is None or self.x is None:
            self.t, self.x, self.dx = t, x, 0.0
            return x
        dt = max(t - self.t, 1e-6)
        self.t = t
        raw_dx = (x - self.x) / dt
        a_d = _alpha(self.d_cutoff, dt)
        self.dx = a_d * raw_dx + (1 - a_d) * self.dx
        cutoff = self.min_cutoff + self.beta * abs(self.dx)
        a = _alpha(cutoff, dt)
        self.x = a * x + (1 - a) * self.x
        return self.x