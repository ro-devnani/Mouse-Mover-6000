import time


class VelocityPlotter:
    """Streams continuous velocity setpoints to the velocity firmware.

    Protocol: 'V <vx> <vy>\\n' sets per-axis mm/s and is fire-and-forget (the
    firmware does not ack it, so we never block reading). 'S <angle>\\n' drives
    the click servo and IS acked with 'ok'. '!' is a realtime abort.
    """

    def __init__(self, serial_obj, press_angle, release_angle, click_dwell_s,
                 sleep_fn=time.sleep):
        self.serial = serial_obj
        self.press_angle = press_angle
        self.release_angle = release_angle
        self.click_dwell_s = click_dwell_s
        self._sleep = sleep_fn

    def _send_acked(self, line: str) -> None:
        """Send a command and wait for the firmware 'ok' (used for 'S')."""
        self.serial.write(line.encode())
        for _ in range(100):
            resp = self.serial.readline()
            if not resp:
                break
            text = resp.decode(errors="replace").strip().lower()
            if text.startswith("ok"):
                break
            if text.startswith("err"):
                raise RuntimeError("firmware rejected: " + line.strip())

    def set_velocity(self, vx_mm_s, vy_mm_s) -> None:
        """Stream a velocity setpoint. Non-blocking: writes, never reads."""
        self.serial.write(f"V {vx_mm_s:.3f} {vy_mm_s:.3f}\n".encode())

    def click(self) -> None:
        self._send_acked(f"S {self.press_angle}\n")
        self._sleep(self.click_dwell_s)
        self._send_acked(f"S {self.release_angle}\n")

    def safe_stop(self) -> None:
        """Halt motion, release servo, then realtime abort."""
        self.set_velocity(0.0, 0.0)
        self._send_acked(f"S {self.release_angle}\n")
        self.serial.write(b"!")

    def feed_hold(self) -> None:
        self.serial.write(b"!")  # realtime, no ack
