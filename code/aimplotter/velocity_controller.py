import math


class VelocityController:
    """Maps a target's pixel position to a per-axis velocity command (mm/s).

    v = kp_v * error_px + kff * gain * target_pixel_velocity

    The proportional term chases the error; the feedforward term matches the
    target's own frame-to-frame motion so a moving target is tracked with less
    lag. Output magnitude is clamped to max_speed_mm_s. Sign convention matches
    error_vector (target - center); axis inversion is the caller's job.
    """

    def __init__(self, kp_v, kff, gain, max_speed_mm_s):
        self.kp_v = kp_v
        self.kff = kff
        self.gain = gain            # mm per px, converts px/s -> mm/s
        self.max_speed_mm_s = max_speed_mm_s
        self.reset()

    def reset(self) -> None:
        self._prev_target = None

    def step(self, target_px, center, dt) -> tuple[float, float]:
        ex = target_px[0] - center[0]
        ey = target_px[1] - center[1]

        if self._prev_target is None or dt <= 0:
            tvx = tvy = 0.0
        else:
            tvx = (target_px[0] - self._prev_target[0]) / dt
            tvy = (target_px[1] - self._prev_target[1]) / dt
        self._prev_target = (target_px[0], target_px[1])

        vx = self.kp_v * ex + self.kff * self.gain * tvx
        vy = self.kp_v * ey + self.kff * self.gain * tvy

        mag = math.hypot(vx, vy)
        if mag > self.max_speed_mm_s and mag > 0:
            scale = self.max_speed_mm_s / mag
            vx *= scale
            vy *= scale
        return (vx, vy)
