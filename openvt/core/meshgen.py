import numpy as np


def grid_mesh(x0, y0, w, h, cols, rows, alpha=None, margin=2):
    """Regular grid over a texture rect in canvas space. Vertex count is always
    (cols+1)*(rows+1); cells that are fully transparent are simply not indexed."""
    cols, rows = max(1, int(cols)), max(1, int(rows))
    us = np.linspace(0.0, 1.0, cols + 1)
    vs = np.linspace(0.0, 1.0, rows + 1)
    uv = np.array([(u, v) for v in vs for u in us], dtype=np.float32)
    pos = uv * np.array([w, h], dtype=np.float32) + np.array([x0, y0], dtype=np.float32)

    idx = []
    th, tw = (alpha.shape if alpha is not None else (h, w))
    for r in range(rows):
        for c in range(cols):
            if alpha is not None:
                px0 = max(0, int(c * tw / cols) - margin)
                px1 = min(tw, int((c + 1) * tw / cols) + margin)
                py0 = max(0, int(r * th / rows) - margin)
                py1 = min(th, int((r + 1) * th / rows) + margin)
                if alpha[py0:py1, px0:px1].max(initial=0) == 0:
                    continue
            i0 = r * (cols + 1) + c
            i1 = i0 + 1
            i2 = i0 + cols + 1
            i3 = i2 + 1
            idx += [i0, i2, i1, i1, i2, i3]
    return pos, uv, np.array(idx, dtype=np.uint32)