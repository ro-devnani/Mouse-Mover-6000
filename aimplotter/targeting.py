import math
from aimplotter.models import Ball


def error_vector(ball: Ball, center) -> tuple[float, float]:
    return (ball.cx - center[0], ball.cy - center[1])


def nearest_to_center(balls, center) -> Ball | None:
    if not balls:
        return None
    return min(
        balls,
        key=lambda b: math.hypot(b.cx - center[0], b.cy - center[1]),
    )
