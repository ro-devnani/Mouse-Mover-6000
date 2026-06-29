"""THROWAWAY on-top overlay. Delete folder before deployment.

Transparent always-on-top window over the game.
Boxes each detected ball, line cursor to nearest.
Read-only. Sends nothing, moves nothing.

Aim Labs must run windowed or borderless.
Exclusive fullscreen cannot be drawn over.

Run: python overlay_debug/overlay.py (press q to quit).
"""
import ctypes
import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CHROMA = "#010101"   # this color renders transparent


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
    from aimplotter.tracker import Tracker, select_locked

    config = Config()
    region = config.screen_region
    off_x = region.get("left", 0)
    off_y = region.get("top", 0)
    cap = make_capture(config)
    pointer = mouse.Controller()
    tracker = Tracker(config.track_match_dist_px, config.track_max_misses)
    locked = {"id": None}
    backend = {"DxCamCapture": "dxcam", "ScreenCapture": "mss"}.get(
        type(cap).__name__, type(cap).__name__)
    hud = {"t": time.perf_counter(), "fps": 0.0}

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

        cur = pointer.position
        local = (cur[0] - off_x, cur[1] - off_y)
        tracks = tracker.update(balls)
        sel = select_locked(tracks, local, locked["id"])
        locked["id"] = sel.id if sel else None

        # Box and label every track
        for t in tracks:
            x1, y1, x2, y2 = box_coords(t.ball, off_x, off_y)
            seen = t.misses == 0
            color = "#00ff00" if seen else "#888888"  # gray when coasting
            canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2)
            label = f"id {t.id}" + ("" if seen else " (lost)")
            canvas.create_text(x1, y1 - 4, text=label, fill=color,
                               anchor="sw", font=("Consolas", 11))

        # Highlight the locked target, line from cursor
        if sel is not None:
            n = sel.ball
            canvas.create_line(cur[0], cur[1], off_x + n.cx, off_y + n.cy,
                               fill="#ffff00", width=2)
            x1, y1, x2, y2 = box_coords(n, off_x, off_y)
            canvas.create_rectangle(x1, y1, x2, y2, outline="#ffff00", width=3)
            canvas.create_text(x1, y1 - 4, text=f"LOCK {sel.id}",
                               fill="#ffff00", anchor="sw",
                               font=("Consolas", 11, "bold"))

        # HUD corner readout
        now = time.perf_counter()
        dt = now - hud["t"]
        hud["t"] = now
        if dt > 0:
            hud["fps"] = 0.9 * hud["fps"] + 0.1 * (1.0 / dt)
        seen = sum(1 for t in tracks if t.misses == 0)
        lock_txt = locked["id"] if locked["id"] is not None else "-"
        canvas.create_text(
            12, 12, anchor="nw", fill="#00ffff", font=("Consolas", 12),
            text=(f"fps {hud['fps']:4.0f}  cap {backend}\n"
                  f"targets {seen}  lock {lock_txt}"))

        root.after(15, tick)

    try:
        root.after(15, tick)
        root.mainloop()
    finally:
        cap.close()
        listener.stop()


if __name__ == "__main__":
    main()
