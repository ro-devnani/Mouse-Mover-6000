import math
import threading
import time

from aimplotter.detector import detect_blue
from aimplotter.targeting import nearest_to_center


def wait_for_enter(message: str) -> None:
    """Block until ENTER is pressed anywhere (global hook, no terminal focus).

    Uses pynput so the key registers even while a fullscreen game is focused.
    """
    from pynput import keyboard
    print(message, flush=True)
    done = threading.Event()

    def on_press(key):
        if key == keyboard.Key.enter:
            done.set()
            return False  # stop the listener

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    done.wait()
    listener.join()


def measure_gain(capture, plotter, config, move_mm=15.0,
                 prompt_fn=wait_for_enter) -> float:
    """Jog known distance, measure pixel shift.

    ENTER-bracketed: press ENTER to capture the target before the jog, the
    plotter jogs a known distance, press ENTER again to capture it after.
    """
    prompt_fn("Aim at a target, then press ENTER to capture START...")
    f0 = capture.grab()
    b0 = nearest_to_center(
        detect_blue(f0, config.hsv_lower, config.hsv_upper, config.min_area_px),
        config.screen_center,
    )
    if b0 is None:
        raise RuntimeError("No ball visible at START. Aim at a target and retry.")

    plotter.jog(move_mm, 0.0)
    time.sleep(0.3)

    prompt_fn("Jogged. When the target is visible again, press ENTER to capture END...")
    f1 = capture.grab()
    # Match the SAME target: after a small jog it barely moved, so the ball
    # nearest b0's old position is the same one. (nearest-to-center would grab
    # whichever target is now closest to center -- often a different ball.)
    b1 = nearest_to_center(
        detect_blue(f1, config.hsv_lower, config.hsv_upper, config.min_area_px),
        (b0.cx, b0.cy),
    )
    if b1 is None:
        raise RuntimeError("No ball visible at END. Retry.")

    px = math.hypot(b1.cx - b0.cx, b1.cy - b0.cy)
    if px < 1:
        raise RuntimeError("No measurable view shift. Increase move_mm.")
    gain = move_mm / px
    print(f"Moved {move_mm} mm -> {px:.1f} px shift. "
          f"Suggested config.gain = {gain:.5f}")
    plotter.jog(-move_mm, 0.0)  # return carriage to start
    return gain


def main() -> None:
    import time as _t
    import serial
    from aimplotter.config import Config
    from aimplotter.capture import ScreenCapture
    from aimplotter.plotter import StepperPlotter

    config = Config()
    cap = ScreenCapture(config.screen_region)
    ser = serial.Serial(config.port, config.baud, timeout=2)
    _t.sleep(2)                # let the Uno finish resetting
    ser.reset_input_buffer()   # discard the boot banner
    plotter = StepperPlotter(ser, config.soft_limit_mm, config.bed_center_mm,
                            config.press_angle, config.release_angle,
                            config.click_dwell_s)
    try:
        measure_gain(cap, plotter, config)
    finally:
        cap.close()


if __name__ == "__main__":
    main()
