"""THROWAWAY on-top overlay. Delete folder before deployment.

Transparent always-on-top window over the game.
Boxes each detected ball, line cursor to nearest.
Read-only. Sends nothing, moves nothing.

Aim Labs must run windowed or borderless.
Exclusive fullscreen cannot be drawn over.

Run: python overlay_debug/overlay.py (press q to quit).
"""
import ctypes
import math
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CHROMA = "#010101"   # this color renders transparent


def _ordered_by_distance(balls, point):
    """Return balls sorted nearest-first to point."""
    return sorted(
        balls,
        key=lambda b: math.hypot(b.cx - point[0], b.cy - point[1]),
    )


def box_coords(ball, off_x=0, off_y=0):
    """Return x1, y1, x2, y2 box around a ball."""
    x = off_x + ball.cx
    y = off_y + ball.cy
    r = ball.r
    return (x - r, y - r, x + r, y + r)


def _make_click_through(root):
    # Layered transparent window passes clicks through
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    gwl_exstyle = -20
    ws_ex_layered = 0x00080000
    ws_ex_transparent = 0x00000020
    style = ctypes.windll.user32.GetWindowLongW(hwnd, gwl_exstyle)
    ctypes.windll.user32.SetWindowLongW(
        hwnd, gwl_exstyle, style | ws_ex_layered | ws_ex_transparent)


def main():
    from pynput import mouse, keyboard
    from aimplotter.config import Config
    from aimplotter.capture import make_capture
    from aimplotter.detector import detect_blue

    config = Config()
    region = config.screen_region
    off_x = region.get("left", 0)
    off_y = region.get("top", 0)
    cap = make_capture(config)
    pointer = mouse.Controller()

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{sw}x{sh}+0+0")
    root.config(bg=CHROMA)
    root.attributes("-transparentcolor", CHROMA)
    canvas = tk.Canvas(root, width=sw, height=sh, bg=CHROMA,
                       highlightthickness=0)
    canvas.pack()
    root.update_idletasks()
    _make_click_through(root)

    stop = {"q": False}

    def on_press(key):
        try:
            if key.char == config.kill_key:
                stop["q"] = True
        except AttributeError:
            pass

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    def tick():
        if stop["q"]:
            root.destroy()
            return
        frame = cap.grab()
        balls = []
        if frame is not None:
            balls = detect_blue(frame, config.hsv_lower, config.hsv_upper,
                                config.min_area_px)
        canvas.delete("all")

        # Box every detected target
        for b in balls:
            canvas.create_rectangle(*box_coords(b, off_x, off_y),
                                    outline="#00ff00", width=2)

        # Line from cursor to nearest target
        cur = pointer.position
        local = (cur[0] - off_x, cur[1] - off_y)
        ordered = _ordered_by_distance(balls, local)
        if ordered:
            n = ordered[0]
            canvas.create_line(cur[0], cur[1], off_x + n.cx, off_y + n.cy,
                               fill="#ffff00", width=2)
            canvas.create_rectangle(*box_coords(n, off_x, off_y),
                                    outline="#ffff00", width=3)

        root.after(15, tick)

    try:
        root.after(15, tick)
        root.mainloop()
    finally:
        cap.close()
        listener.stop()


if __name__ == "__main__":
    main()
