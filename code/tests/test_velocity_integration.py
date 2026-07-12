import numpy as np
import cv2
from aimplotter.velocity_main import run_velocity_loop
from aimplotter.velocity_controller import VelocityController
from aimplotter.config import Config


class FakeVP:
    def __init__(self):
        self.velocities = []
        self.clicks = 0

    def set_velocity(self, vx, vy):
        self.velocities.append((vx, vy))

    def click(self):
        self.clicks += 1


def _frame(cx, cy, r=25):
    f = np.zeros((1080, 1920, 3), dtype=np.uint8)
    if cx is not None:
        cv2.circle(f, (cx, cy), r, (255, 80, 0), -1)
    return f


def _clock_from(seq):
    it = iter(seq)
    return lambda: next(it)


def test_loop_streams_velocity_then_clicks_then_idles():
    C = Config()
    # frame 1: ball off-center -> vel; frame 2: ball ON center -> click;
    # frame 3: no ball -> idle (velocity zeroed)
    frames = [_frame(1200, 700), _frame(960, 540), _frame(None, None)]
    it = iter(frames)

    def source():
        return next(it, None)

    p = FakeVP()
    ctrl = VelocityController(C.kp_v, C.kff, C.gain, C.max_speed_mm_s)
    clock = _clock_from([0.0, 0.03, 0.06, 0.09])

    actions = run_velocity_loop(source, p, ctrl, C,
                                should_stop=lambda: False, clock=clock)

    assert "vel" in actions
    assert "click" in actions
    assert "idle" in actions
    assert p.clicks >= 1
    assert p.velocities[-1] == (0.0, 0.0)   # idle zeroes velocity


def test_loop_stops_on_kill_switch():
    C = Config()
    p = FakeVP()
    ctrl = VelocityController(C.kp_v, C.kff, C.gain, C.max_speed_mm_s)
    actions = run_velocity_loop(lambda: _frame(1200, 700), p, ctrl, C,
                                should_stop=lambda: True,
                                clock=_clock_from([0.0, 0.03]))
    assert actions == []


def test_offcenter_frame_commands_nonzero_velocity():
    C = Config()
    frames = [_frame(1400, 540), _frame(None, None)]
    it = iter(frames)
    p = FakeVP()
    ctrl = VelocityController(C.kp_v, C.kff, C.gain, C.max_speed_mm_s)
    run_velocity_loop(lambda: next(it, None), p, ctrl, C,
                      should_stop=lambda: False,
                      clock=_clock_from([0.0, 0.03, 0.06]))
    vx, vy = p.velocities[0]
    assert vx != 0.0     # ball right of center -> nonzero x velocity
