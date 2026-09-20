from dataclasses import dataclass


@dataclass
class TrackingFrame:
    ok: bool = False
    yaw: float = 0.0      # deg, + = subject turned to THEIR left
    pitch: float = 0.0    # deg, + = looking down
    roll: float = 0.0     # deg, + = top of head toward THEIR right
    head_x: float = 0.0   # -1..1 in camera image
    head_y: float = 0.0
    blink_l: float = 0.0  # 0 open .. 1 closed (subject's left eye)
    blink_r: float = 0.0
    jaw_open: float = 0.0
    smile: float = 0.0
    pucker: float = 0.0
    brow_up: float = 0.0
    brow_down: float = 0.0
    look_l: float = 0.0   # gaze toward subject's left
    look_r: float = 0.0
    look_u: float = 0.0
    look_d: float = 0.0


class BaseTracker:
    name = "none"

    def start(self): ...
    def stop(self): ...
    def poll(self) -> TrackingFrame:
        return TrackingFrame()