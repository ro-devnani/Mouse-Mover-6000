# Velocity-Based Smooth Movement — Design

**Date:** 2026-07-11
**Status:** Approved (design), pending implementation plan
**Branch:** direct-stepper-driver

## Problem

The current aim system moves choppily. Each frame runs a full stop-start cycle:

1. `main.run_loop` computes a clamped **position** delta from the PD controller.
2. `StepperPlotter.jog()` sends `J dx dy feed`; firmware `runMove()` **blocks**,
   running both steppers to their targets and **decelerating to zero every jog**
   (AccelStepper accel/decel curve per move).
3. Python **blocks** waiting for the `ok` ack.
4. `time.sleep(move_settle_s)` lets the view render.
5. Re-capture, repeat.

Motion is therefore move → halt → settle → move → halt. The steppers never carry
momentum between frames, and the mandatory decel-to-zero + settle produces visible
choppiness.

## Goal

Replace discrete position moves with **continuous velocity streaming**. The
controller maps pixel error to a target **velocity** (mm/s) per axis. Firmware runs
the steppers continuously at the commanded speed, non-blocking; each frame only
updates the setpoint. Steppers glide and ramp smoothly toward each new velocity,
never halting between frames. No settle sleep, no blocking ack-wait on motion.

## Non-Goals

- Not replacing the existing stop-start system. It stays intact and runnable as a
  fallback (`controller.py`, `plotter.py`, `main.py`, `mm6000.ino`, `calibrate.py`
  are untouched).
- Not changing detection, tracking, capture, or drift subsystems — reused as-is.
- Not rewriting calibration. `calibrate.py` still measures mm/px gain, which informs
  velocity-tuning defaults but is not on the hot path.

## Architecture

New files, parallel to the existing ones:

```
aimplotter/
  velocity_controller.py     # pixel error -> per-axis velocity (mm/s)
  velocity_plotter.py        # streams V commands, non-blocking
  velocity_main.py           # detect -> aim -> click loop, no settle/no block
firmware/mm6000_velocity/
  mm6000_velocity.ino        # continuous velocity command + watchdog
config.py                    # + velocity section (shared file, new fields)
```

Data flow per frame:

```
capture.grab
  -> detect_blue -> pick target (tracker/nearest)
     target is None      -> set_velocity(0, 0)   (drift reuse deferred)
     error in deadzone    -> set_velocity(0, 0); click if armed
     otherwise            -> v = controller.step(target, dt); set_velocity(v)
```

## Component 1 — Firmware (`mm6000_velocity.ino`)

Same CNC Shield V3 pin map, servo, and `!` abort semantics as `mm6000.ino`.

**Protocol:**

| Command | Meaning | Ack |
|---|---|---|
| `V <vx_mm_s> <vy_mm_s>\n` | set target velocity per axis | **none** (fire-and-forget) |
| `S <angle>\n` | servo angle (click) | `ok` |
| `!` | abort: zero target velocity | none |

`V` intentionally does **not** ack. Streaming velocity at frame rate cannot afford a
blocking round-trip per update; the whole point is to remove the ack-wait stall.

**Control loop (non-blocking, tight):**

- Store `targetSpeedX`, `targetSpeedY` (steps/s), set by the last `V`.
- Each `loop()` iteration:
  1. Drain any available serial bytes into the line buffer; parse complete lines.
  2. **Slew** `currentSpeedX/Y` toward `targetSpeedX/Y`, limited to `ACCEL * dt`
     steps/s per tick. Bounded acceleration = smooth ramps, no velocity-step jerk
     even if the setpoint jumps.
  3. `setSpeed(currentSpeed)` then `runSpeed()` for each axis (constant-speed step
     generation; no AccelStepper decel-to-target because there is no target).
- `dt` measured from `micros()` between iterations.

**Watchdog:** if no `V` command has arrived within `WATCHDOG_MS` (~200 ms), force
`targetSpeed = 0` on both axes. The slew still applies, so the rig ramps down smoothly
rather than snapping. Protects against a dead/unplugged host leaving the rig running.

**Soft limits (authoritative in firmware):** track `currentPosition()` in steps.
Convert `soft_limit_mm` to steps at compile/config time. Before `runSpeed()`, if an
axis is at or beyond its ± limit **and** the commanded velocity points further out,
zero that axis's speed (that axis only; the other keeps moving). Firmware is the
final authority on limits; Python keeps an estimate only for logging.

## Component 2 — Velocity controller (`velocity_controller.py`)

Pure function of pixel error + target motion; holds minimal state for feedforward.

```
v_axis = kp_v * error_px[axis] + kff * target_velocity_px_s[axis]
```

- `error_px` = target center − screen center (same sign convention as current
  `error_vector`; invert_x / invert_y applied as today).
- `target_velocity_px_s` = (target pixel position − previous target pixel position)
  / dt. Feedforward term: keeps the crosshair with a moving target instead of always
  chasing from behind.
- **Deadzone:** if `hypot(error) <= radius + vel_deadzone_tol_px`, output `(0, 0)`
  and signal "on target" so the caller can hold and arm/fire the click.
- **Clamp:** limit `hypot(vx, vy)` to `max_speed_mm_s` (preserve direction).
- **State:** previous target pixel position + previous timestamp. `reset()` clears
  it (call when the locked target changes, so feedforward does not jump across a
  target switch). If no previous sample, feedforward is 0 for that frame.

Units: `kp_v` is mm/s of commanded speed per pixel of error. `kff` is dimensionless
scaling on target pixel velocity converted to mm/s via the calibrated mm/px gain
(so `kff = 1.0` means "match the target's apparent speed"). Default `kff` starts
conservative.

## Component 3 — Velocity plotter (`velocity_plotter.py`)

```
set_velocity(vx_mm_s, vy_mm_s) -> None   # sends "V vx vy\n", NO ack-wait
click() -> None                          # S press, dwell, S release (ack)
safe_stop() -> None                      # S release, then "!"
feed_hold() -> None                      # "!"
position (property) -> (x, y)            # estimate from integrated velocity*dt
```

- `set_velocity` writes and returns immediately — this is the streaming hot path.
- `click`/`safe_stop` reuse the acked `S` path from the existing plotter design.
- Position estimate is for debug/logging only; firmware enforces limits. Plotter may
  still pre-clamp the commanded velocity toward a limit as a courtesy, but is not the
  authority.

## Component 4 — Velocity main (`velocity_main.py`)

Mirrors `main.run_loop` structure minus the blocking bits:

- No `move_settle_s` sleep. No per-move ack stall. Loop cadence = capture cadence.
- Compute `dt` between frames (for controller feedforward + firmware watchdog health).
- Same kill-switch listener and `_PrintPlotter` dry-run (prints `V`/`CLICK`).
- On target-in-deadzone: `set_velocity(0, 0)`; `click()` if armed; then hold (no jog).
  Re-arm when the crosshair leaves the target, same as current `armed` logic.
- On no target: `set_velocity(0, 0)`. Drift reuse is optional and deferred; the
  velocity system's baseline is "stop when nothing to track."
- On teardown (`finally`): `set_velocity(0, 0)` then `safe_stop()`.

## Component 5 — Config additions

Append a velocity section to the existing `Config` dataclass (reusing detection,
capture, serial, soft-limit, servo fields). New fields:

| Field | Purpose | Starting default |
|---|---|---|
| `kp_v` | mm/s commanded per px error | tune (e.g. 0.05) |
| `kff` | feedforward scale on target motion | 0.5 |
| `max_speed_mm_s` | velocity magnitude clamp | e.g. 40 |
| `vel_watchdog_ms` | host-side note; firmware constant mirrors it | 200 |
| `vel_deadzone_tol_px` | hold zone = radius + this | 6.0 |

Existing stop-start fields (`gain`, `kp/ki/kd`, `max_move_mm`, `move_settle_s`) are
left untouched so the old system still runs.

## Error Handling & Safety

- **Firmware watchdog** ramps to zero if the host stops streaming — primary safety net.
- **`!` abort** and the kill-switch key remain wired through.
- **Soft limits** enforced in firmware (authoritative), estimated in Python.
- Malformed `V` line: firmware ignores (no target change) rather than faulting; the
  watchdog covers a persistent parse failure.

## Testing

- **Controller** — pure/unit testable: feed synthetic error + target-motion sequences,
  assert velocity output, deadzone zeroing, clamp magnitude, feedforward reset on
  target switch. No hardware.
- **Plotter** — inject a fake serial object; assert exact `V`/`S`/`!` bytes and that
  `set_velocity` does not block on a read.
- **Main loop** — reuse the existing `run_loop` test harness pattern (frame source
  callable + fake plotter), assert the action log: `vel`, `hold`, `click`, `idle`.
- **Firmware** — manual/bench: confirm continuous motion, smooth ramp on setpoint
  jumps, watchdog stop on host silence, per-axis limit clamp.

## Open Questions (resolve during planning)

- Exact starting values for `kp_v` / `kff` / `max_speed_mm_s` (bench-tune; spec gives
  conservative seeds).
- Whether to reuse `DriftCorrector` in velocity mode or keep "stop when idle" only.
```