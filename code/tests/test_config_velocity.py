from aimplotter.config import Config


def test_velocity_defaults_present():
    c = Config()
    assert c.kp_v > 0
    assert c.kff >= 0
    assert c.max_speed_mm_s > 0
    assert c.vel_watchdog_ms == 200
    assert c.vel_deadzone_tol_px > 0


def test_velocity_fields_do_not_disturb_existing():
    c = Config()
    assert c.gain == 0.24          # existing stop-start knob untouched
    assert c.move_settle_s == 0.04
