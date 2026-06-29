import math
from aimplotter.controller import PDController, on_target


def test_proportional_move_toward_target():
    c = PDController(gain=0.03, kp=1.0, ki=0.0, kd=0.0, max_move_mm=5.0)
    mx, my = c.step((100.0, -100.0))
    assert mx > 0 and my < 0                 # same direction as error
    assert math.isclose(mx, 3.0, abs_tol=1e-6)   # 100 * 0.03 * 1.0


def test_move_is_clamped():
    c = PDController(gain=1.0, kp=1.0, ki=0.0, kd=0.0, max_move_mm=5.0)
    mx, my = c.step((100.0, 0.0))
    assert math.isclose(math.hypot(mx, my), 5.0, abs_tol=1e-6)


def test_derivative_damps_on_growing_error():
    c = PDController(gain=0.0, kp=0.0, ki=0.0, kd=0.5, max_move_mm=100.0)
    c.step((10.0, 0.0))            # prev err set
    mx, _ = c.step((30.0, 0.0))    # delta = 20 -> 0.5*20 = 10
    assert math.isclose(mx, 10.0, abs_tol=1e-6)


def test_reset_clears_state():
    c = PDController(gain=0.0, kp=0.0, ki=0.0, kd=0.5, max_move_mm=100.0)
    c.step((10.0, 0.0))
    c.reset()
    mx, _ = c.step((10.0, 0.0))    # treated as first sample, delta=0
    assert math.isclose(mx, 0.0, abs_tol=1e-6)


def test_on_target_inside_hitbox():
    assert on_target((3.0, 0.0), radius=10.0, tol=2.0) is True
    assert on_target((20.0, 0.0), radius=10.0, tol=2.0) is False
