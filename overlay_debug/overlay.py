"""THROWAWAY debug overlay — delete the overlay_debug/ folder before deployment.

Draws the planned cursor path (crosshair -> closest target -> next target)
over a live screen capture. Read-only: imports from aimplotter but never
modifies it, sends nothing to the plotter, and does not move the cursor.

Run from the mm6000/ project root:  python overlay_debug/overlay.py
Press 'q' (window focused) to quit.
"""
import math
import os
import sys

import cv2

# Allow running as a plain script from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _ordered_by_distance(balls, center):
    """Return balls sorted nearest-first relative to center."""
    return sorted(
        balls,
        key=lambda b: math.hypot(b.cx - center[0], b.cy - center[1]),
    )


def _draw(frame, balls, center):
    cx, cy = int(center[0]), int(center[1])

    # crosshair
    cv2.drawMarker(frame, (cx, cy), (255, 255, 255),
                   markerType=cv2.MARKER_CROSS, markerSize=24, thickness=2)

    ordered = _ordered_by_distance(balls, center)

    # circle every detected ball
    for b in ordered:
        cv2.circle(frame, (int(b.cx), int(b.cy)), int(b.r), (0, 255, 0), 2)

    # crosshair -> closest
    if ordered:
        c = ordered[0]
        cv2.line(frame, (cx, cy), (int(c.cx), int(c.cy)), (0, 255, 255), 2)
        cv2.putText(frame, "closest", (int(c.cx) + 8, int(c.cy) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    # closest -> next
    if len(ordered) >= 2:
        c, n = ordered[0], ordered[1]
        cv2.line(frame, (int(c.cx), int(c.cy)), (int(n.cx), int(n.cy)),
                 (0, 128, 255), 2)
        cv2.putText(frame, "next", (int(n.cx) + 8, int(n.cy) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 128, 255), 2)

    return frame


def main():
    # Imported here (not at module load) so the drawing helpers above stay
    # importable even before aimplotter.capture/detector are implemented.
    from aimplotter.capture import ScreenCapture
    from aimplotter.config import Config
    from aimplotter.detector import detect_blue

    config = Config()
    cap = ScreenCapture(config.screen_region)
    win = "aim overlay (debug) - press q to quit"
    try:
        while True:
            frame = cap.grab().copy()
            balls = detect_blue(frame, config.hsv_lower, config.hsv_upper,
                                config.min_area_px)
            _draw(frame, balls, config.screen_center)
            cv2.imshow(win, frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
