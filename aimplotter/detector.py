import cv2
import numpy as np
from aimplotter.models import Ball


def detect_blue(frame, hsv_lower, hsv_upper, min_area) -> list[Ball]:
    """Find neon-blue blobs in a BGR frame, return Balls sorted largest-first."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lower), np.array(hsv_upper))
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    balls: list[Ball] = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        (x, y), r = cv2.minEnclosingCircle(c)
        balls.append(Ball(cx=float(x), cy=float(y), r=float(r)))

    balls.sort(key=lambda b: b.r, reverse=True)
    return balls
