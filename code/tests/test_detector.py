import numpy as np
import cv2
from aimplotter.detector import detect_blue
from aimplotter.config import Config

C = Config()


def _frame_with_blue_circle(cx, cy, r, size=(1080, 1920)):
    frame = np.zeros((size[0], size[1], 3), dtype=np.uint8)
    # neon blue in BGR is high B, low G/R
    cv2.circle(frame, (cx, cy), r, (255, 80, 0), -1)
    return frame


def test_detects_single_ball_center():
    frame = _frame_with_blue_circle(960, 540, 30)
    balls = detect_blue(frame, C.hsv_lower, C.hsv_upper, C.min_area_px)
    assert len(balls) == 1
    assert abs(balls[0].cx - 960) <= 3
    assert abs(balls[0].cy - 540) <= 3
    assert balls[0].r > 20


def test_ignores_small_noise():
    frame = _frame_with_blue_circle(100, 100, 2)
    balls = detect_blue(frame, C.hsv_lower, C.hsv_upper, C.min_area_px)
    assert balls == []


def test_detects_multiple_sorted_by_area():
    frame = _frame_with_blue_circle(300, 300, 20)
    cv2.circle(frame, (1500, 800), 40, (255, 80, 0), -1)
    balls = detect_blue(frame, C.hsv_lower, C.hsv_upper, C.min_area_px)
    assert len(balls) == 2
    assert balls[0].r >= balls[1].r  # largest first
