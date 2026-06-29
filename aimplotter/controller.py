import math


class PDController:
    """Turns a pixel-error vector into a clamped relative mm move.

    Pure PD by default (ki=0); set ki>0 for full PID. State held between
    step() calls for derivative/integral terms; reset() between targets.
    """

    def __init__(self, gain, kp, ki, kd, max_move_mm):
        self.gain = gain
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.max_move_mm = max_move_mm
        self.reset()

    def reset(self) -> None:
        self._prev = None
        self._integral = [0.0, 0.0]

    def step(self, err_px) -> tuple[float, float]:
        out = [0.0, 0.0]
        for i in range(2):
            e = err_px[i]
            d = 0.0 if self._prev is None else (e - self._prev[i])
            self._integral[i] += e
            out[i] = self.gain * self.kp * e + self.kd * d + self.ki * self._integral[i]
        self._prev = (err_px[0], err_px[1])

        mag = math.hypot(out[0], out[1])
        if mag > self.max_move_mm and mag > 0:
            scale = self.max_move_mm / mag
            out[0] *= scale
            out[1] *= scale
        return (out[0], out[1])


def on_target(err_px, radius, tol) -> bool:
    return math.hypot(err_px[0], err_px[1]) <= (radius + tol)
