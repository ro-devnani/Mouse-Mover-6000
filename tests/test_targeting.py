from aimplotter.models import Ball
from aimplotter.config import Config
from aimplotter.targeting import nearest_to_center, error_vector


def test_ball_center():
    b = Ball(cx=10.0, cy=20.0, r=5.0)
    assert b.center == (10.0, 20.0)


def test_config_defaults():
    c = Config()
    assert c.baud == 115200
    assert c.screen_center == (960, 540)
    assert c.ki == 0.0  # pure PD by default


def test_nearest_to_center_picks_closest():
    near = Ball(cx=965.0, cy=545.0, r=10.0)
    far = Ball(cx=200.0, cy=200.0, r=10.0)
    assert nearest_to_center([far, near], (960, 540)) is near


def test_nearest_to_center_empty_returns_none():
    assert nearest_to_center([], (960, 540)) is None


def test_error_vector():
    b = Ball(cx=1000.0, cy=500.0, r=10.0)
    assert error_vector(b, (960, 540)) == (40.0, -40.0)
