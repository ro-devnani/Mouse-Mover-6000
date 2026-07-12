import argparse
import time

from aimplotter.config import Config
from aimplotter.detector import detect_blue
from aimplotter.targeting import nearest_to_center, error_vector
from aimplotter.controller import on_target
from aimplotter.velocity_controller import VelocityController
from aimplotter.tracker import select_locked


def run_velocity_loop(frame_source, plotter, controller, config,
                      should_stop, clock, tracker=None) -> list[str]:
    """Stream velocity setpoints in a detect->aim->click loop.

    No settle sleep and no per-move ack stall: every frame updates the
    velocity setpoint and the firmware keeps the steppers gliding. Returns an
    action log for testing.
    """
    actions: list[str] = []
    locked_id = None
    armed = True                 # may we click? False = already hit, hold still
    prev_t = clock()
    while not should_stop():
        frame = frame_source()
        if frame is None:
            break
        now = clock()
        dt = now - prev_t
        prev_t = now

        balls = detect_blue(frame, config.hsv_lower, config.hsv_upper,
                            config.min_area_px)
        if tracker is not None:
            tracks = tracker.update(balls)
            sel = select_locked(tracks, config.screen_center, locked_id)
            target = sel.ball if sel else None
            locked_id = sel.id if sel else None
        else:
            target = nearest_to_center(balls, config.screen_center)

        if target is None:
            plotter.set_velocity(0.0, 0.0)
            controller.reset()          # drop stale feedforward history
            actions.append("idle")
            continue

        err = error_vector(target, config.screen_center)
        if on_target(err, target.r, config.vel_deadzone_tol_px):
            plotter.set_velocity(0.0, 0.0)
            if armed:
                plotter.click()
                controller.reset()
                armed = False
                actions.append("click")
            else:
                actions.append("hold")
        else:
            armed = True                # crosshair left target -> re-arm
            vx, vy = controller.step(target.center, config.screen_center, dt)
            if config.invert_x:
                vx = -vx
            if config.invert_y:
                vy = -vy
            if config.debug:
                print(f"err=({err[0]:+.0f},{err[1]:+.0f}) "
                      f"vel=({vx:+.2f},{vy:+.2f}) r={target.r:.0f}")
            plotter.set_velocity(vx, vy)
            actions.append("vel")
    return actions


class _PrintVelocityPlotter:
    """Dry-run plotter: prints velocity commands instead of sending serial."""
    def set_velocity(self, vx, vy):
        print(f"[dry-run] V {vx:.3f} {vy:.3f}")

    def click(self):
        print("[dry-run] CLICK")

    def safe_stop(self):
        print("[dry-run] SAFE STOP")

    def feed_hold(self):
        print("[dry-run] FEED HOLD")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Optical aim plotter (velocity)")
    parser.add_argument("--no-serial", action="store_true",
                        help="dry-run: print velocity commands instead of sending")
    args = parser.parse_args(argv)

    config = Config()
    controller = VelocityController(config.kp_v, config.kff, config.gain,
                                    config.max_speed_mm_s)
    from aimplotter.tracker import Tracker
    tracker = Tracker(config.track_match_dist_px, config.track_max_misses)

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

    from aimplotter.capture import make_capture
    cap = make_capture(config)

    if args.no_serial:
        plotter = _PrintVelocityPlotter()
    else:
        import serial
        from aimplotter.velocity_plotter import VelocityPlotter
        ser = serial.Serial(config.port, config.baud, timeout=2)
        time.sleep(2)              # let the Uno finish resetting
        ser.reset_input_buffer()
        plotter = VelocityPlotter(ser, config.press_angle, config.release_angle,
                                  config.click_dwell_s)

    try:
        run_velocity_loop(cap.grab, plotter, controller, config,
                          should_stop=lambda: stop_flag["stop"],
                          clock=time.monotonic, tracker=tracker)
    finally:
        try:
            plotter.safe_stop()
        except Exception:
            pass
        cap.close()
        listener.stop()


if __name__ == "__main__":
    main()
