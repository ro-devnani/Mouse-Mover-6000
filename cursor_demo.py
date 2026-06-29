"""Move the OS cursor to the nearest blue ball.

Software-only demo. No plotter, no clicking.
Picks the ball nearest the cursor and snaps to it.
Useful for testing detection on the desktop.
Does not aim inside fullscreen raw-input games.

Run:  python cursor_demo.py
Press 'q' to quit.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aimplotter.targeting import nearest_to_center


def target_position(balls, cursor_xy, region):
    """Return screen coords of nearest ball, or None."""
    ball = nearest_to_center(balls, cursor_xy)
    if ball is None:
        return None
    x = region.get("left", 0) + ball.cx
    y = region.get("top", 0) + ball.cy
    return (int(x), int(y))


def main():
    from pynput import mouse, keyboard
    from aimplotter.config import Config
    from aimplotter.capture import ScreenCapture
    from aimplotter.detector import detect_blue

    config = Config()
    cap = ScreenCapture(config.screen_region)
    pointer = mouse.Controller()

    stop = {"q": False}

    def on_press(key):
        try:
            if key.char == config.kill_key:
                stop["q"] = True
        except AttributeError:
            pass

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    print("Tracking nearest ball. Press q to quit.")
    try:
        while not stop["q"]:
            frame = cap.grab()
            balls = detect_blue(frame, config.hsv_lower, config.hsv_upper,
                                config.min_area_px)
            # Cursor relative to the captured region
            cur = pointer.position
            local = (cur[0] - config.screen_region.get("left", 0),
                     cur[1] - config.screen_region.get("top", 0))
            pos = target_position(balls, local, config.screen_region)
            if pos is not None:
                pointer.position = pos
            time.sleep(0.01)
    finally:
        cap.close()
        listener.stop()


if __name__ == "__main__":
    main()
