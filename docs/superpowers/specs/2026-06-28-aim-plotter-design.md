# mm6000 — Closed-Loop Optical Aim Plotter (Design)

**Date:** 2026-06-28
**Status:** Approved design, pre-implementation

## 1. Summary

Detect neon-blue balls on a 1080p fullscreen Aim Labs feed and drive a GRBL XY
plotter — which carries a physical computer mouse — so the screen-center
crosshair lands on the nearest ball, then fire a servo to click. Because a mouse
produces *relative* input, the system is a **closed-loop proportional-derivative
(PD) visual servo**, not absolute positioning.

## 2. Control Model

The in-game crosshair is fixed at screen center; the view turns based on
accumulated mouse motion. There is no fixed map from plotter position to view
direction, so each frame the loop measures pixel error and commands a relative
move:

```
loop every frame:
  frame  = capture_screen()
  balls  = detect_blue(frame)                 # HSV threshold + contours
  if balls:
      target = nearest_to_center(balls)
      err_px = target.center - screen_center  # (dx, dy) pixels
      if |err_px| <= target.radius:           # crosshair inside hitbox
          click()                             # servo press/release
      else:
          move_mm = pd_control(err_px)        # px -> mm, clamped (glide)
          plotter.jog(move_mm)                # GRBL relative move
  else:
      drift_corrector.tick()                  # reclaim travel during dead time
```

### PD controller
`move = Kp·err + Kd·Δerr + Ki·∫err`, with `Ki = 0` by default (pure PD).
- `Kp` (proportional): main pull toward target; gain < 1 yields a smooth glide.
- `Kd` (derivative): brakes against overshoot on fast flicks.
- `Ki` (integral): available via config for full PID; off by default to avoid
  windup between discrete targets.
- Output is clamped to `MAX_MOVE_MM_PER_FRAME` (rate limit = the "glide").

### GAIN / calibration
`GAIN` = mm of plotter travel per pixel of view error — the number that closes
the loop. Folded into `Kp`. Seeded from a default; refined by `calibrate.py`,
which moves the plotter a known distance and measures the resulting view shift
in pixels.

## 3. Drift Corrector

The loop is relative and closed, so absolute view orientation is irrelevant —
only error-to-target matters. Frames with no ball visible (gaps between Aim Labs
spawns, and just after a click) are "dead time": moving the carriage then turns
the view harmlessly. So after `DRIFT_IDLE_FRAMES` consecutive no-target frames,
the drift corrector gently glides the carriage back toward bed-center (using the
absolute position tracked from accumulated jogs), reclaiming travel headroom.
Normal aiming resumes the moment a ball reappears. The soft-limit guard remains
the hard safety net for the no-lift constraint (see §6).

## 4. Components

Each module has one purpose and a clean interface.

- `capture.py` — fast screen grab via `mss`; returns a BGR frame. Region
  configurable (default full 1920×1080).
- `detector.py` — `detect_blue(frame) -> [Ball(cx, cy, r)]`. HSV range from
  config, morphological denoise, min-area filter.
- `targeting.py` — `nearest_to_center(balls, center) -> Ball`; pixel-error vector.
- `controller.py` — PD/PID math: `error_px -> clamped mm move`; hitbox click
  decision. Pure functions, no I/O.
- `plotter.py` — GRBL serial driver (`pyserial`): connect, `$J=` jog with
  ok-handshake, absolute-position tracking, soft-limit guard, click via
  configurable `PRESS_CMD` / `RELEASE_CMD`.
- `drift.py` — drift corrector (§3).
- `calibrate.py` — interactive pixel-per-mm gain measurement. Optional;
  defaults provided.
- `config.py` — all tunables (HSV range, Kp/Ki/Kd, GAIN, MAX_MOVE_MM_PER_FRAME,
  hitbox tolerance, port, baud=115200, click commands, soft limits, bed-center,
  DRIFT_IDLE_FRAMES, kill key).
- `main.py` — wires the loop; starts kill-switch listener.

## 5. Safety / Kill-Switch

- Global hotkey (default `Q`, via `pynput`) **and** corner-slam detection →
  instant halt: GRBL feed-hold (`!`), servo release, stop loop.
- Soft-limit guard: clamp + warn if a move would exceed configured travel.
- Dry-run mode (`--no-serial`): prints G-code instead of sending, for testing
  detection without hardware.

## 6. Known Constraint

A mouse fixed to a 2D plotter with no Z lift cannot be recentered without
turning the view, so net drift accumulates across many targets. Mitigations:
the drift corrector (§3) reclaims headroom during dead time; the soft-limit
guard pauses for manual re-center if a limit is still reached. Adding a Z servo
to lift the mouse later would enable true unconditional auto-recenter.

## 7. Testing

- Unit: `detector` against synthetic screenshots (blue circles on noise) —
  asserts centroids/radii within tolerance.
- Unit: `controller` math (error→mm, clamping, PD response, hitbox trigger) —
  pure, no hardware.
- Unit: `drift` position tracking and recenter direction.
- Integration: dry-run loop over a recorded clip, asserting the emitted G-code
  sequence.

## 8. Stack

Python 3 · `opencv-python` · `mss` · `numpy` · `pyserial` · `pynput`.
GRBL pre-flashed on the Arduino Uno + CNC Shield v3; servo on the spindle pin,
commanded over the same USB serial link.

## 9. Hardware Assumptions

- Controller: Arduino Uno + CNC Shield v3, GRBL, USB serial @ 115200.
- Click: servo connected to the Arduino, actuated by `PRESS_CMD`/`RELEASE_CMD`
  (default `M3 S1000` / `M5`).
- Steps/mm and exact work-area travel: placeholder defaults in config, to be
  set by the user later.
- Display: single 1080p monitor, Aim Labs fullscreen.
