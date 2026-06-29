# overlay_debug (THROWAWAY DEV TOOL)

> ⚠️ **Delete this entire folder before final deployment.** It is a debugging
> visualization only. It imports from `aimplotter/` (read-only) and modifies
> **no** main files, so removing this folder leaves the project intact.

## What it shows

A transparent, always-on-top, click-through window drawn directly over the
game:

- A **green box** over every detected ball, labeled with its **track ID**.
- Coasting tracks (briefly lost, within the grace period) show **gray** and
  `(lost)`.
- A **yellow line** from the cursor to the locked ball, boxed in yellow and
  labeled `LOCK <id>`.

The track IDs let you watch the lock-on behavior: the locked ID stays put while
that ball is visible, and only moves to another when the locked one is hit or
disappears.

It is click-through, so it never steals mouse input from the game. It is purely
visual and sends nothing to the plotter.

**Aim Labs must run in windowed or borderless mode.** Exclusive fullscreen
cannot be drawn over by any external overlay. Windows only (uses tkinter +
ctypes).

## Run

From the `mm6000/` project root:

```bash
python overlay_debug/overlay.py
```

Press `q` to quit (works anywhere, via a global key listener).

## HSV tuner (test + calibrate detection)

Interactive trackbars to dial in `hsv_lower` / `hsv_upper` / `min_area_px`
for your monitor and Aim Labs blue. Shows detections and the binary mask
side by side.

```bash
python overlay_debug/tune_hsv.py            # live screen
python overlay_debug/tune_hsv.py --image shot.png   # static image
```

Keys: `f` freeze/unfreeze, `s` save snapshot + print config values, `q` quit.

Workflow: open Aim Labs, drag sliders until only the balls show white in the
mask (and each gets a green circle, with `balls: N` matching what you see),
press `s`, paste the printed three lines into `aimplotter/config.py`.
