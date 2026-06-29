import time


class GRBLPlotter:
    def __init__(self, serial_obj, soft_limit_mm, bed_center_mm,
                 press_cmd, release_cmd, click_dwell_s,
                 feed_mm_min=3000, sleep_fn=time.sleep):
        self.serial = serial_obj
        self.soft_limit_mm = soft_limit_mm
        self.center = bed_center_mm
        self.press_cmd = press_cmd
        self.release_cmd = release_cmd
        self.click_dwell_s = click_dwell_s
        self.feed_mm_min = feed_mm_min
        self._sleep = sleep_fn
        self._x, self._y = bed_center_mm

    @property
    def position(self) -> tuple[float, float]:
        return (self._x, self._y)

    def _send(self, line: str) -> None:
        """Send command, wait for ok."""
        self.serial.write(line.encode())
        for _ in range(100):
            resp = self.serial.readline()
            if not resp:
                break
            text = resp.decode(errors="replace").strip().lower()
            if text.startswith("ok"):
                break
            if text.startswith("error"):
                raise RuntimeError(resp.decode(errors="replace").strip())

    def _clamp(self, target, axis_center):
        lo = axis_center - self.soft_limit_mm
        hi = axis_center + self.soft_limit_mm
        if target < lo:
            return lo, True
        if target > hi:
            return hi, True
        return target, False

    def jog(self, dx_mm, dy_mm) -> bool:
        nx, cx_clamped = self._clamp(self._x + dx_mm, self.center[0])
        ny, cy_clamped = self._clamp(self._y + dy_mm, self.center[1])
        real_dx = nx - self._x
        real_dy = ny - self._y
        line = (f"$J=G91 G21 X{real_dx:.3f} Y{real_dy:.3f} "
                f"F{self.feed_mm_min}\n")
        self._send(line)
        self._x, self._y = nx, ny
        return not (cx_clamped or cy_clamped)

    def click(self) -> None:
        self._send(self.press_cmd + "\n")
        self._sleep(self.click_dwell_s)
        self._send(self.release_cmd + "\n")

    def safe_stop(self) -> None:
        """Release servo then halt."""
        self._send(self.release_cmd + "\n")
        self.serial.write(b"!")

    def feed_hold(self) -> None:
        self.serial.write(b"!")  # realtime, no response
