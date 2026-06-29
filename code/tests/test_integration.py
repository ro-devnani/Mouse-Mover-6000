import numpy as np
import cv2
from aimplotter.main import run_loop
from aimplotter.controller import PDController
from aimplotter.drift import DriftCorrector
from aimplotter.config import Config


class FakeP:
    def __init__(self):
        self._pos = (0.0, 0.0)
        self.clicks = 0
        self.jogs = 0

    @property
    def position(self):
        return self._pos

    def jog(self, dx, dy):
        self._pos = (self._pos[0] + dx, self._pos[1] + dy)
        self.jogs += 1
        return True

    def click(self):
        self.clicks += 1


def _frame(cx, cy, r=25):
    f = np.zeros((1080, 1920, 3), dtype=np.uint8)
    if cx is not None:
        cv2.circle(f, (cx, cy), r, (255, 80, 0), -1)
    return f


def test_loop_jogs_then_clicks_then_drifts():
    C = Config()
    # frame 1: ball far from center -> jog; frame 2: ball ON center -> click;
    # frames 3-... : no ball -> drift after idle threshold
    frames = [_frame(1200, 700), _frame(960, 540)]
    frames += [_frame(None, None)] * (C.drift_idle_frames + 1)
    it = iter(frames)

    def source():
        return next(it, None)

    p = FakeP()
    ctrl = PDController(C.gain, C.kp, C.ki, C.kd, C.max_move_mm)
    drift = DriftCorrector(C.bed_center_mm, C.drift_idle_frames, C.drift_step_mm)

    actions = run_loop(source, p, ctrl, drift, C, should_stop=lambda: False)

    assert "jog" in actions
    assert "click" in actions
    assert "drift" in actions
    assert p.clicks >= 1


def test_loop_stops_on_kill_switch():
    C = Config()
    p = FakeP()
    ctrl = PDController(C.gain, C.kp, C.ki, C.kd, C.max_move_mm)
    drift = DriftCorrector(C.bed_center_mm, C.drift_idle_frames, C.drift_step_mm)
    actions = run_loop(lambda: _frame(1200, 700), p, ctrl, drift, C,
                       should_stop=lambda: True)
    assert actions == []
