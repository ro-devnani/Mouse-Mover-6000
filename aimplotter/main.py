import argparse
import time

from aimplotter.config import Config
from aimplotter.detector import detect_blue
from aimplotter.targeting import nearest_to_center, error_vector
from aimplotter.controller import PDController, on_target
from aimplotter.drift import DriftCorrector


def run_loop(frame_source, plotter, controller, drift, config,
             should_stop) -> list[str]:
    """Drive one detect->aim->click loop. Returns action log for testing."""
    actions: list[str] = []
    while not should_stop():
        frame = frame_source()
        if frame is None:
            break
        balls = detect_blue(frame, config.hsv_lower, config.hsv_upper,
                            config.min_area_px)
        target = nearest_to_center(balls, config.screen_center)
        if target is None:
            if drift.tick(plotter):
                actions.append("drift")
            else:
                actions.append("idle")
            continue

        drift.on_target_frame()
        err = error_vector(target, config.screen_center)
        if on_target(err, target.r, config.hitbox_tol_px):
            plotter.click()
            controller.reset()
            actions.append("click")
        else:
            dx, dy = controller.step(err)
            plotter.jog(dx, dy)
            actions.append("jog")
    return actions


class _PrintPlotter:
    """Dry-run plotter: prints G-code instead of sending serial."""
    def __init__(self):
        self._pos = (0.0, 0.0)

    @property
    def position(self):
        return self._pos

    def jog(self, dx, dy):
        self._pos = (self._pos[0] + dx, self._pos[1] + dy)
        print(f"[dry-run] $J=G91 X{dx:.3f} Y{dy:.3f}")
        return True

    def click(self):
        print("[dry-run] CLICK")

    def feed_hold(self):
        print("[dry-run] FEED HOLD")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Optical aim plotter")
    parser.add_argument("--no-serial", action="store_true",
                        help="dry-run: print G-code instead of sending")
    args = parser.parse_args(argv)

    config = Config()
    controller = PDController(config.gain, config.kp, config.ki, config.kd,
                             config.max_move_mm)
    drift = DriftCorrector(config.bed_center_mm, config.drift_idle_frames,
                          config.drift_step_mm)

    # kill switch
    stop_flag = {"stop": False}
    from pynput import keyboard

    def on_press(key):
        try:
            if key.char == config.kill_key:
                stop_flag["stop"] = True
        except AttributeError:
            pass

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    # capture
    from aimplotter.capture import ScreenCapture
    cap = ScreenCapture(config.screen_region)

    # plotter
    if args.no_serial:
        plotter = _PrintPlotter()
    else:
        import serial
        from aimplotter.plotter import GRBLPlotter
        ser = serial.Serial(config.port, config.baud, timeout=2)
        time.sleep(2)
        plotter = GRBLPlotter(ser, config.soft_limit_mm, config.bed_center_mm,
                             config.press_cmd, config.release_cmd,
                             config.click_dwell_s)

    try:
        run_loop(cap.grab, plotter, controller, drift, config,
                 should_stop=lambda: stop_flag["stop"])
    finally:
        try:
            plotter.feed_hold()
        except Exception:
            pass
        cap.close()
        listener.stop()


if __name__ == "__main__":
    main()
