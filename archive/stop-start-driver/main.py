import argparse
import time

from aimplotter.config import Config
from aimplotter.detector import detect_blue
from aimplotter.targeting import nearest_to_center, error_vector
from aimplotter.controller import PDController, on_target
from aimplotter.drift import DriftCorrector
from aimplotter.tracker import select_locked


def run_loop(frame_source, plotter, controller, drift, config,
             should_stop, tracker=None) -> list[str]:
    """Drive one detect->aim->click loop. Returns action log for testing."""
    actions: list[str] = []
    locked_id = None
    armed = True  # may we click? False = already hit, hold still
    while not should_stop():
        frame = frame_source()
        if frame is None:
            break
        balls = detect_blue(frame, config.hsv_lower, config.hsv_upper,
                            config.min_area_px)
        if tracker is not None:
            # Lock one target across frames
            tracks = tracker.update(balls)
            sel = select_locked(tracks, config.screen_center, locked_id)
            target = sel.ball if sel else None
            locked_id = sel.id if sel else None
        else:
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
            if armed:
                plotter.click()
                controller.reset()
                armed = False  # click once, then hold
                actions.append("click")
            else:
                actions.append("hold")  # already hit; sit still, no jog
        else:
            armed = True  # crosshair left the target -> re-arm
            dx, dy = controller.step(err)
            if config.invert_x:
                dx = -dx
            if config.invert_y:
                dy = -dy
            if config.debug:
                print(f"err=({err[0]:+.0f},{err[1]:+.0f}) "
                      f"move=({dx:+.2f},{dy:+.2f}) r={target.r:.0f}")
            ok = plotter.jog(dx, dy)
            if not ok:
                print("WARNING: soft limit reached")
            if config.move_settle_s:
                time.sleep(config.move_settle_s)  # let the view render before next grab
            actions.append("jog")
    return actions


class _PrintPlotter:
    """Dry-run plotter: prints the firmware command instead of sending serial."""
    def __init__(self):
        self._pos = (0.0, 0.0)

    @property
    def position(self):
        return self._pos

    def jog(self, dx, dy):
        self._pos = (self._pos[0] + dx, self._pos[1] + dy)
        print(f"[dry-run] J {dx:.3f} {dy:.3f}")
        return True

    def click(self):
        print("[dry-run] CLICK")

    def safe_stop(self):
        print("[dry-run] SAFE STOP")

    def feed_hold(self):
        print("[dry-run] FEED HOLD")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Optical aim plotter")
    parser.add_argument("--no-serial", action="store_true",
                        help="dry-run: print firmware commands instead of sending")
    args = parser.parse_args(argv)

    config = Config()
    controller = PDController(config.gain, config.kp, config.ki, config.kd,
                             config.max_move_mm)
    drift = DriftCorrector(config.bed_center_mm, config.drift_idle_frames,
                          config.drift_step_mm)
    from aimplotter.tracker import Tracker
    tracker = Tracker(config.track_match_dist_px, config.track_max_misses)

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
    from aimplotter.capture import make_capture
    cap = make_capture(config)

    # plotter
    if args.no_serial:
        plotter = _PrintPlotter()
    else:
        import serial
        from aimplotter.plotter import StepperPlotter
        ser = serial.Serial(config.port, config.baud, timeout=2)
        time.sleep(2)          # let the Uno finish resetting
        ser.reset_input_buffer()
        plotter = StepperPlotter(ser, config.soft_limit_mm, config.bed_center_mm,
                                config.press_angle, config.release_angle,
                                config.click_dwell_s)

    try:
        run_loop(cap.grab, plotter, controller, drift, config,
                 should_stop=lambda: stop_flag["stop"], tracker=tracker)
    finally:
        try:
            plotter.safe_stop()
        except Exception:
            pass
        cap.close()
        listener.stop()


if __name__ == "__main__":
    main()
