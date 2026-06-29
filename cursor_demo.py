"""Move the OS cursor to the nearest blue ball, then click.

Software-only demo. No plotter hardware.
Glides toward the ball nearest the cursor.
Left-clicks when inside the ball hitbox.
Does not aim inside fullscreen raw-input games.

Run:  python cursor_demo.py
Press 'q' to quit.
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aimplotter.targeting import nearest_to_center
from aimplotter.controller import on_target

# Tuning for the glide
GLIDE_FACTOR = 0.35       # fraction of error per frame
MAX_STEP_PX = 60          # cap per frame
CLICK_COOLDOWN_S = 0.4    # min gap between clicks


def glide_step(cursor_xy, target_xy, factor, max_step):
    """Return next cursor position gliding toward target."""
    dx = target_xy[0] - cursor_xy[0]
    dy = target_xy[1] - cursor_xy[1]
    dist = math.hypot(dx, dy)
    if dist == 0:
        return (int(cursor_xy[0]), int(cursor_xy[1]))
    step = min(factor * dist, max_step)
    nx = cursor_xy[0] + dx / dist * step
    ny = cursor_xy[1] + dy / dist * step
    return (int(nx), int(ny))


def main():
    from pynput import mouse, keyboard
    from aimplotter.config import Config
    from aimplotter.capture import ScreenCapture
    from aimplotter.detector import detect_blue

    config = Config()
    region = config.screen_region
    off_x = region.get("left", 0)
    off_y = region.get("top", 0)

    cap = ScreenCapture(region)
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

    print("Gliding to nearest ball, clicking on hit. Press q to quit.")
    last_click = 0.0
    try:
        while not stop["q"]:
            frame = cap.grab()
            balls = detect_blue(frame, config.hsv_lower, config.hsv_upper,
                                config.min_area_px)
            cur = pointer.position
            local = (cur[0] - off_x, cur[1] - off_y)
            ball = nearest_to_center(balls, local)
            if ball is not None:
                target = (off_x + ball.cx, off_y + ball.cy)
                err = (target[0] - cur[0], target[1] - cur[1])
                if on_target(err, ball.r, config.hitbox_tol_px):
                    now = time.monotonic()
                    if now - last_click >= CLICK_COOLDOWN_S:
                        pointer.click(mouse.Button.left)
                        last_click = now
                else:
                    pointer.position = glide_step(cur, target, GLIDE_FACTOR,
                                                  MAX_STEP_PX)
            time.sleep(0.01)
    finally:
        cap.close()
        listener.stop()


if __name__ == "__main__":
    main()
