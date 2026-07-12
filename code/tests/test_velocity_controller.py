import math
from aimplotter.velocity_controller import VelocityController


def test_velocity_proportional_to_error():
    c = VelocityController(kp_v=0.05, kff=0.0, gain=0.2, max_speed_mm_s=100.0)
    vx, vy = c.step(target_px=(1060.0, 440.0), center=(960.0, 540.0), dt=0.03)
    # error = (+100, -100); kff=0 so pure P
    assert math.isclose(vx, 5.0, abs_tol=1e-6)   # 100 * 0.05
    assert math.isclose(vy, -5.0, abs_tol=1e-6)  # -100 * 0.05


def test_feedforward_adds_target_motion():
    c = VelocityController(kp_v=0.0, kff=1.0, gain=0.2, max_speed_mm_s=100.0)
    # first sample seeds prev; error term zero (kp_v=0), no prev motion yet
    v0 = c.step(target_px=(960.0, 540.0), center=(960.0, 540.0), dt=0.1)
    assert v0 == (0.0, 0.0)
    # target moved +30px in x over dt=0.1s -> 300 px/s; ff = kff*gain*300 = 60 mm/s
    vx, vy = c.step(target_px=(990.0, 540.0), center=(960.0, 540.0), dt=0.1)
    assert math.isclose(vx, 60.0, abs_tol=1e-6)
    assert math.isclose(vy, 0.0, abs_tol=1e-6)


def test_velocity_is_clamped():
    c = VelocityController(kp_v=1.0, kff=0.0, gain=0.2, max_speed_mm_s=5.0)
    vx, vy = c.step(target_px=(1060.0, 540.0), center=(960.0, 540.0), dt=0.03)
    assert math.isclose(math.hypot(vx, vy), 5.0, abs_tol=1e-6)


def test_reset_clears_feedforward_history():
    c = VelocityController(kp_v=0.0, kff=1.0, gain=0.2, max_speed_mm_s=100.0)
    c.step(target_px=(960.0, 540.0), center=(960.0, 540.0), dt=0.1)
    c.reset()
    # after reset the next sample is treated as first -> no feedforward
    vx, vy = c.step(target_px=(990.0, 540.0), center=(960.0, 540.0), dt=0.1)
    assert vx == 0.0 and vy == 0.0


def test_zero_or_negative_dt_skips_feedforward():
    c = VelocityController(kp_v=0.0, kff=1.0, gain=0.2, max_speed_mm_s=100.0)
    c.step(target_px=(960.0, 540.0), center=(960.0, 540.0), dt=0.1)
    vx, vy = c.step(target_px=(990.0, 540.0), center=(960.0, 540.0), dt=0.0)
    assert vx == 0.0 and vy == 0.0
