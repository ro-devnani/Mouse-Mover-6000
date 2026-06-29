"""THROWAWAY HSV tuner. Delete folder before deployment.

Interactive trackbars to calibrate ball detection.
Shows detections and mask side by side.
Read-only. Touches no main files.

Run (live screen):   python overlay_debug/tune_hsv.py
Run (static image):  python overlay_debug/tune_hsv.py --image shot.png

Keys (window focused):
  f  freeze / unfreeze the live frame
  s  save a snapshot frame and print config values
  q  quit
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WIN = "HSV tuner (q quit, f freeze, s save)"


def build_mask(frame, lower, upper):
    # Mirrors detector morphology
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(lower, np.uint8), np.array(upper, np.uint8))
    k = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    return mask


def _read_trackbars():
    g = lambda n: cv2.getTrackbarPos(n, WIN)
    lower = (g("H lo"), g("S lo"), g("V lo"))
    upper = (g("H hi"), g("S hi"), g("V hi"))
    return lower, upper, float(g("min area"))


def _make_trackbars(config):
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    lo, hi = config.hsv_lower, config.hsv_upper
    for name, val, mx in [
        ("H lo", lo[0], 179), ("S lo", lo[1], 255), ("V lo", lo[2], 255),
        ("H hi", hi[0], 179), ("S hi", hi[1], 255), ("V hi", hi[2], 255),
        ("min area", int(config.min_area_px), 4000),
    ]:
        cv2.createTrackbar(name, WIN, val, mx, lambda _v: None)


def _print_values(lower, upper, min_area):
    print("\n# paste into aimplotter/config.py")
    print(f"hsv_lower: tuple[int, int, int] = {lower}")
    print(f"hsv_upper: tuple[int, int, int] = {upper}")
    print(f"min_area_px: float = {min_area}\n")


def main():
    from aimplotter.config import Config
    from aimplotter.detector import detect_blue

    ap = argparse.ArgumentParser()
    ap.add_argument("--image", help="tune on a static image instead of screen")
    args = ap.parse_args()

    config = Config()
    _make_trackbars(config)

    cap = None
    static = None
    if args.image:
        static = cv2.imread(args.image)
        if static is None:
            raise SystemExit(f"could not read image: {args.image}")
    else:
        from aimplotter.capture import ScreenCapture
        cap = ScreenCapture(config.screen_region)

    frozen = None
    try:
        while True:
            if static is not None:
                frame = static.copy()
            elif frozen is not None:
                frame = frozen.copy()
            else:
                frame = cap.grab().copy()

            lower, upper, min_area = _read_trackbars()
            mask = build_mask(frame, lower, upper)
            balls = detect_blue(frame, lower, upper, min_area)
            for b in balls:
                cv2.circle(frame, (int(b.cx), int(b.cy)), int(b.r),
                           (0, 255, 0), 2)
            cv2.putText(frame, f"balls: {len(balls)}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

            mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            combo = np.hstack([frame, mask_bgr])
            cv2.imshow(WIN, combo)

            key = cv2.waitKey(30) & 0xFF
            if key == ord("q"):
                break
            if key == ord("f") and cap is not None:
                frozen = None if frozen is not None else cap.grab().copy()
            if key == ord("s"):
                cv2.imwrite("overlay_debug/tune_snapshot.png", frame)
                _print_values(lower, upper, min_area)
    finally:
        if cap is not None:
            cap.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
