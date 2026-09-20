from __future__ import annotations
import math
import os
import threading
import time
import urllib.request
from .base import BaseTracker, TrackingFrame

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_landmarker/"
             "face_landmarker/float16/1/face_landmarker.task")

class MediaPipeTracker(BaseTracker):
    name = "mediapipe"

    def __init__(self, camera=0, model_path="assets/face_landmarker.task", width=640, height=480, preview=False):
        import cv2                      # noqa  (raises ImportError -> caller falls back)
        import mediapipe as mp          # noqa
        from mediapipe.tasks import python as mp_py
        from mediapipe.tasks.python import vision
        self.cv2, self.mp, self.mp_py, self.vision = cv2, mp, mp_py, vision
        self.camera = camera
        self.model_path = model_path
        self.size = (width, height)
        self.preview = preview
        self.running = False
        self.thread = None
        self._latest = TrackingFrame()
        self._lock = threading.Lock()

    def start(self):
        if not os.path.exists(self.model_path):
            os.makedirs(os.path.dirname(self.model_path) or ".", exist_ok=True)
            print(f"[tracker] downloading face_landmarker.task ...")
            urllib.request.urlretrieve(MODEL_URL, self.model_path)
        v = self.vision
        opts = v.FaceLandmarkerOptions(
            base_options=self.mp_py.BaseOptions(model_asset_path=self.model_path),
            running_mode=v.RunningMode.VIDEO, num_faces=1,
            output_face_blendshapes=True, output_facial_transformation_matrixes=True,
            min_face_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.lm = v.FaceLandmarker.create_from_options(opts)
        backend = self.cv2.CAP_DSHOW if os.name == "nt" else 0
        self.cap = self.cv2.VideoCapture(self.camera, backend)
        self.cap.set(self.cv2.CAP_PROP_FRAME_WIDTH, self.size[0])
        self.cap.set(self.cv2.CAP_PROP_FRAME_HEIGHT, self.size[1])
        if not self.cap.isOpened():
            raise RuntimeError(f"camera {self.camera} could not be opened")
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print(f"[tracker] mediapipe running on camera {self.camera}")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if getattr(self, "cap", None):
            if self.preview:
                try: 
                    self.cv2.destroyWindow("OpenVT tracker")
                except Exception: 
                    pass
            self.cap.release()

    def poll(self) -> TrackingFrame:
        with self._lock:
            return self._latest

    def _loop(self):
        cv2, mp = self.cv2, self.mp
        t0 = time.monotonic()
        last_ts = -1
        while self.running:
            ok, bgr = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            ts = int((time.monotonic() - t0) * 1000)
            if ts <= last_ts:
                ts = last_ts + 1
            last_ts = ts
            try:
                res = self.lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)
            except Exception as e:  # pragma: no cover
                print("[tracker] detect error:", e)
                continue
            frame = self._to_frame(res)
            if self.preview:
                if res.face_landmarks:
                    h_, w_ = bgr.shape[:2]
                    for p in res.face_landmarks[0]:
                        cv2.circle(bgr, (int(p.x * w_), int(p.y * h_)), 1, (0, 255, 0), -1)
                cv2.putText(bgr, f"yaw{frame.yaw:+.0f} pit{frame.pitch:+.0f} rol{frame.roll:+.0f}",
                            (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.imshow("OpenVT tracker", bgr)
                cv2.waitKey(1)
            with self._lock:
                self._latest = frame

    def _to_frame(self, res) -> TrackingFrame:
        f = TrackingFrame()
        if not res.face_landmarks:
            return f
        f.ok = True
        if res.facial_transformation_matrixes:
            R = res.facial_transformation_matrixes[0]
            sy = math.sqrt(R[0][0] ** 2 + R[1][0] ** 2)
            f.yaw = math.degrees(math.atan2(-R[2][0], sy))
            f.pitch = math.degrees(math.atan2(R[2][1], R[2][2]))
            f.roll = math.degrees(math.atan2(R[1][0], R[0][0]))
        nose = res.face_landmarks[0][1]
        f.head_x, f.head_y = (nose.x - 0.5) * 2, (nose.y - 0.5) * 2
        bs = {c.category_name: c.score for c in res.face_blendshapes[0]} if res.face_blendshapes else {}
        g = bs.get
        f.blink_l, f.blink_r = g("eyeBlinkLeft", 0.0), g("eyeBlinkRight", 0.0)
        f.jaw_open = g("jawOpen", 0.0)
        f.smile = (g("mouthSmileLeft", 0.0) + g("mouthSmileRight", 0.0)) / 2
        f.pucker = max(g("mouthPucker", 0.0), g("mouthFunnel", 0.0))
        f.brow_up = (g("browInnerUp", 0.0) + g("browOuterUpLeft", 0.0) + g("browOuterUpRight", 0.0)) / 3
        f.brow_down = (g("browDownLeft", 0.0) + g("browDownRight", 0.0)) / 2
        f.look_l = (g("eyeLookOutLeft", 0.0) + g("eyeLookInRight", 0.0)) / 2
        f.look_r = (g("eyeLookInLeft", 0.0) + g("eyeLookOutRight", 0.0)) / 2
        f.look_u = (g("eyeLookUpLeft", 0.0) + g("eyeLookUpRight", 0.0)) / 2
        f.look_d = (g("eyeLookDownLeft", 0.0) + g("eyeLookDownRight", 0.0)) / 2
        return f