"""Measure gain (mm/px) using the velocity firmware, no firmware swap.

The old calibrate.py jogged a known DISTANCE (a 'J' move) the velocity
firmware doesn't understand. Here we instead command a known VELOCITY for a
known TIME -> distance = v * t mm, then measure the pixel shift of the same
target. gain = distance / px_shift.

Keep the calib velocity modest and the duration >> the firmware ramp
(ACCEL) so the accel/decel ramps are a negligible fraction of the travel.
"""
import math
import threading
import time

from aimplotter.detector import detect_blue
from aimplotter.targeting import nearest_to_center


def wait_for_enter(message: str) -> None:
    """Block until ENTER is pressed anywhere (global hook, no terminal focus)."""
    from pynput import keyboard
    print(message, flush=True)
    done = threading.Event()

    def on_press(key):
        if key == keyboard.Key.enter:
            done.set()
            return False

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    done.wait()
    listener.join()


def measure_gain_velocity(capture, plotter, config, calib_v_mm_s=20.0,
                          move_s=1.0, settle_s=0.3,
                          prompt_fn=wait_for_enter, sleep_fn=time.sleep) -> float:
    """Command a known velocity for a known time, measure the view shift.

    ENTER-gated: aim at a target, press ENTER; the carriage drives +X at
    calib_v_mm_s for move_s seconds, stops, and the pixel shift is measured.
    Returns gain in mm/px. The carriage is driven back afterward.
    """
    prompt_fn("Aim at a target, then press ENTER to start the calibration move...")
    f0 = capture.grab()
    b0 = nearest_to_center(
        detect_blue(f0, config.hsv_lower, config.hsv_upper, config.min_area_px),
        config.screen_center,
    )
    if b0 is None:
        raise RuntimeError("No ball visible at START. Aim at a target and retry.")

    plotter.set_velocity(calib_v_mm_s, 0.0)
    sleep_fn(move_s)
    plotter.set_velocity(0.0, 0.0)
    sleep_fn(settle_s)                       # let the view settle before re-grab

    f1 = capture.grab()
    # Match the SAME target: it barely moved on screen, so the ball nearest
    # b0's old position is the same one.
    b1 = nearest_to_center(
        detect_blue(f1, config.hsv_lower, config.hsv_upper, config.min_area_px),
        (b0.cx, b0.cy),
    )
    if b1 is None:
        raise RuntimeError("No ball visible at END. Retry.")

    px = math.hypot(b1.cx - b0.cx, b1.cy - b0.cy)
    if px < 1:
        raise RuntimeError("No measurable view shift. Raise calib_v_mm_s or move_s.")

    dist_mm = calib_v_mm_s * move_s
    gain = dist_mm / px
    print(f"Moved ~{dist_mm:.1f} mm ({calib_v_mm_s} mm/s x {move_s}s) -> "
          f"{px:.1f} px shift. Suggested config.gain = {gain:.5f}")

    plotter.set_velocity(-calib_v_mm_s, 0.0)  # return the carriage
    sleep_fn(move_s)
    plotter.set_velocity(0.0, 0.0)
    return gain


def main() -> None:
    import serial
    from aimplotter.config import Config
    from aimplotter.capture import ScreenCapture
    from aimplotter.velocity_plotter import VelocityPlotter

    config = Config()
    cap = ScreenCapture(config.screen_region)
    ser = serial.Serial(config.port, config.baud, timeout=2)
    time.sleep(2)                # let the Uno finish resetting
    ser.reset_input_buffer()     # discard the boot banner
    plotter = VelocityPlotter(ser, config.press_angle, config.release_angle,
                              config.click_dwell_s)
    try:
        measure_gain_velocity(cap, plotter, config)
    finally:
        cap.close()


if __name__ == "__main__":
    main()
