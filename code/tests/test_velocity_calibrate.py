import numpy as np
import cv2
from aimplotter.velocity_calibrate import measure_gain_velocity
from aimplotter.config import Config


class FakeCap:
    """Yields a preset list of frames on successive grab() calls."""
    def __init__(self, frames):
        self._frames = list(frames)
        self._i = 0

    def grab(self):
        f = self._frames[self._i]
        self._i = min(self._i + 1, len(self._frames) - 1)
        return f

    def close(self):
        pass


class FakeVP:
    def __init__(self):
        self.velocities = []

    def set_velocity(self, vx, vy):
        self.velocities.append((vx, vy))


def _frame(cx, cy, r=25):
    f = np.zeros((1080, 1920, 3), dtype=np.uint8)
    cv2.circle(f, (cx, cy), r, (255, 80, 0), -1)
    return f


def test_gain_is_distance_over_pixel_shift():
    C = Config()
    # START ball at center; END ball shifted 40 px in x (same target).
    frames = [_frame(960, 540), _frame(1000, 540)]
    cap = FakeCap(frames)
    plotter = FakeVP()

    # 20 mm/s for 0.5 s -> 10 mm of travel; 40 px shift -> gain 0.25 mm/px
    gain = measure_gain_velocity(
        cap, plotter, C, calib_v_mm_s=20.0, move_s=0.5,
        prompt_fn=lambda msg: None, sleep_fn=lambda s: None,
    )
    assert abs(gain - 0.25) < 1e-6


def test_drives_out_then_returns_and_stops():
    C = Config()
    frames = [_frame(960, 540), _frame(1000, 540)]
    plotter = FakeVP()
    measure_gain_velocity(
        FakeCap(frames), plotter, C, calib_v_mm_s=20.0, move_s=0.5,
        prompt_fn=lambda msg: None, sleep_fn=lambda s: None,
    )
    # +v out, stop, -v back, stop
    assert plotter.velocities[0] == (20.0, 0.0)
    assert plotter.velocities[1] == (0.0, 0.0)
    assert plotter.velocities[2] == (-20.0, 0.0)
    assert plotter.velocities[-1] == (0.0, 0.0)
