import glfw
from .base import BaseTracker, TrackingFrame


class MouseTracker(BaseTracker):
    """Fallback when no camera/mediapipe: mouse = head, LMB = mouth, RMB = blink."""
    name = "mouse"

    def __init__(self, window):
        self.window = window

    def poll(self) -> TrackingFrame:
        w, h = glfw.get_window_size(self.window)
        x, y = glfw.get_cursor_pos(self.window)
        nx = max(-1.0, min(1.0, (x / max(w, 1)) * 2 - 1))
        ny = max(-1.0, min(1.0, (y / max(h, 1)) * 2 - 1))
        lmb = glfw.get_mouse_button(self.window, glfw.MOUSE_BUTTON_LEFT) == glfw.PRESS
        rmb = glfw.get_mouse_button(self.window, glfw.MOUSE_BUTTON_RIGHT) == glfw.PRESS
        f = TrackingFrame(ok=True)
        f.yaw = -nx * 25.0          # mapper mirrors -> mouse right = avatar right
        f.pitch = ny * 20.0
        f.head_x, f.head_y = nx, ny
        f.jaw_open = 0.7 if lmb else 0.0
        f.blink_l = f.blink_r = 1.0 if rmb else 0.0
        f.look_r, f.look_l = max(nx, 0.0), max(-nx, 0.0)
        f.look_d, f.look_u = max(ny, 0.0), max(-ny, 0.0)
        return f