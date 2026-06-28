from aimplotter.models import Ball
from aimplotter.config import Config


def test_ball_center():
    b = Ball(cx=10.0, cy=20.0, r=5.0)
    assert b.center == (10.0, 20.0)


def test_config_defaults():
    c = Config()
    assert c.baud == 115200
    assert c.screen_center == (960, 540)
    assert c.ki == 0.0  # pure PD by default
