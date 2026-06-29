import math
import time

from aimplotter.detector import detect_blue
from aimplotter.targeting import nearest_to_center


def measure_gain(capture, plotter, config, move_mm=5.0) -> float:
    """Jog known distance, measure pixel shift."""
    f0 = capture.grab()
    b0 = nearest_to_center(
        detect_blue(f0, config.hsv_lower, config.hsv_upper, config.min_area_px),
        config.screen_center,
    )
    if b0 is None:
        raise RuntimeError("No ball visible. Point at target before calibrating.")

    plotter.jog(move_mm, 0.0)
    time.sleep(0.3)

    f1 = capture.grab()
    b1 = nearest_to_center(
        detect_blue(f1, config.hsv_lower, config.hsv_upper, config.min_area_px),
        config.screen_center,
    )
    if b1 is None:
        raise RuntimeError("Lost the ball after move. Reduce move_mm.")

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
    from aimplotter.plotter import GRBLPlotter

    config = Config()
    cap = ScreenCapture(config.screen_region)
    ser = serial.Serial(config.port, config.baud, timeout=2)
    _t.sleep(2)
    plotter = GRBLPlotter(ser, config.soft_limit_mm, config.bed_center_mm,
                         config.press_cmd, config.release_cmd,
                         config.click_dwell_s)
    try:
        measure_gain(cap, plotter, config)
    finally:
        cap.close()


if __name__ == "__main__":
    main()
