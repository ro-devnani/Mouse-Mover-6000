import numpy as np
import cv2
from aimplotter.velocity_main import run_velocity_loop
from aimplotter.velocity_controller import VelocityController
from aimplotter.config import Config
from aimplotter.tracker import Track
from aimplotter.models import Ball


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


class FakeTracker:
    """Replays a preset sequence of track lists, ignoring detected balls."""
    def __init__(self, track_seq):
        self._it = iter(track_seq)

    def update(self, balls):
        return next(self._it)


class RecordingController(VelocityController):
    """Records reset()/step() calls in order so we can inspect interleaving."""
    def __init__(self, *args, **kwargs):
        self.calls = []
        super().__init__(*args, **kwargs)

    def reset(self):
        self.calls.append("reset")
        super().reset()

    def step(self, target_px, center, dt):
        self.calls.append(("step", target_px))
        return super().step(target_px, center, dt)


def test_lock_switch_resets_controller_feedforward():
    # Two different balls, both off-center so both frames take the "vel"
    # branch (never on-target, never idle). The fake tracker hands back a
    # different locked track id on frame 2, simulating the tracker's lock
    # jumping from ball A to ball B (e.g. A left frame, B is now nearest).
    C = Config()
    track_seq = [
        [Track(id=1, ball=Ball(cx=1400, cy=540, r=25), misses=0)],
        [Track(id=2, ball=Ball(cx=600, cy=540, r=25), misses=0)],
    ]
    tracker = FakeTracker(track_seq)

    p = FakeVP()
    ctrl = RecordingController(C.kp_v, C.kff, C.gain, C.max_speed_mm_s)

    # Only 2 frames: once the iterator is exhausted, next(it, None) yields
    # None and the loop stops -- matching track_seq's length exactly.
    frames = [_frame(1400, 540), _frame(600, 540)]
    it = iter(frames)

    run_velocity_loop(lambda: next(it, None), p, ctrl, C,
                      should_stop=lambda: False,
                      clock=_clock_from([0.0, 0.03, 0.06]),
                      tracker=tracker)

    step_indices = [i for i, c in enumerate(ctrl.calls)
                    if isinstance(c, tuple) and c[0] == "step"]
    assert len(step_indices) == 2, f"expected 2 step() calls, got {ctrl.calls}"
    first_step_i, second_step_i = step_indices

    # A reset() must land strictly between the two step() calls: that's the
    # controller dropping ball A's stale feedforward before it ever sees
    # ball B's target position.
    between = ctrl.calls[first_step_i + 1:second_step_i]
    assert "reset" in between, (
        f"controller.reset() was not called on lock switch; calls={ctrl.calls}"
    )
