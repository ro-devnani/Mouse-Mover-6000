# Direct Stepper Driver — Replace GRBL with Custom Firmware (Design)

**Date:** 2026-07-11
**Status:** Approved design, pre-implementation

## 1. Summary

Remove GRBL from the Arduino Uno. Use the CNC Shield V3 as a passive breakout
board and run custom firmware that drives the A4988 STEP/DIR pins directly and
actuates the SG90 click servo. The PC talks to the firmware over a simple
line-based serial protocol.

The existing Python control stack (screen capture → blue detection → nearest
target → PD controller → relative jog → servo click, plus drift corrector and
kill-switch) is unchanged in behaviour. Only the plotter **driver internals**
and a few `config.py` fields change, because the Python↔hardware seam keeps the
same shape it has today: send a line, wait for `ok`.

## 2. Motivation

GRBL adds a firmware layer whose CNC semantics (jog queue, laser/spindle modes,
homing, `$$` config) are overhead for this project and introduced real setup
snags — notably driving a hobby servo off the ~1 kHz spindle PWM pin. Owning the
firmware lets us drive the servo with the `Servo` library at the correct 50 Hz
and keep the motion model as simple as the task needs (relative jogs, no
homing, no endstops).

## 3. Architecture

Two halves connected by a serial line protocol. The seam is identical to the
current design, so the Python loop above the driver is untouched.

```
PC (Python)                              Arduino Uno + CNC Shield V3
-----------                              ---------------------------
StepperPlotter.jog(dx,dy)  --"J dx dy feed\n"-->  parse, mm->steps,
                                                  AccelStepper run, then
                           <------"ok\n"--------  ack
StepperPlotter.click()     --"S 60\n"--------->   servo.write(60), ack
                              (dwell)
                           --"S 90\n"--------->   servo.write(90), ack
StepperPlotter.safe_stop() --"!"------------->    abort motion (no ack)
```

### 3.1 Firmware — `firmware/mm6000/mm6000.ino`

- **CNC Shield V3 is a passive breakout.** Standard GRBL pin map:
  - X: STEP=D2, DIR=D5
  - Y: STEP=D3, DIR=D6
  - Driver ENABLE=D8 (active low; pulled LOW at boot to energize drivers)
  - Servo signal=D11
- **Libraries:** `AccelStepper` (one instance per axis) and `Servo`.
- **Compile-time constants (`#define`):** `STEPS_PER_MM_X`, `STEPS_PER_MM_Y`,
  `ACCEL` (steps/s²), `DEFAULT_SPEED` (steps/s fallback). `steps/mm` lives here,
  measured on the built machine and baked in; changing microstepping means a
  reflash.
- **Motion:** each axis is an `AccelStepper` in `DRIVER` mode. A move sets both
  axes' `maxSpeed` from the requested feed, calls `moveTo` (relative target in
  steps), then loops `run()` on both until both reach target. Acceleration is
  applied per axis. The two axes are not guaranteed to finish the same instant;
  for the ≤5 mm per-frame jogs the skew is negligible (accepted trade-off — the
  coordinated alternative, `MultiStepper`, cannot do acceleration).
- **Abort:** the run loop polls `Serial.available()` every iteration. If a `!`
  byte arrives mid-move, it stops both steppers immediately and exits the move.
  This keeps kill-switch latency low even though normal moves block.
- **Boot:** set ENABLE low, attach servo, move servo to release angle, print a
  ready banner. Then serve the command loop.

### 3.2 Serial protocol

- 115200 baud, `\n`-terminated ASCII lines. Every completed command replies
  `ok\n`. Unknown commands reply `err\n`.

| PC → Arduino | Meaning | Reply |
| :--- | :--- | :--- |
| `J <dx_mm> <dy_mm> <feed_mm_min>` | Relative move. Firmware converts mm→steps, sets max speed from feed, runs to completion. | `ok` after move done |
| `S <angle>` | Set servo to `<angle>` degrees (0–180). | `ok` |
| `!` (single byte, **no** newline) | Realtime abort — stop steppers now. | none |

Design intent: mirror the current "send line, wait for `ok`" handshake so
`StepperPlotter._send` is the same shape as today's `GRBLPlotter._send`.

### 3.3 Python — `aimplotter/plotter.py`

Rename `GRBLPlotter` → `StepperPlotter`. Identical public surface:

- `__init__(serial_obj, soft_limit_mm, bed_center_mm, press_angle,
  release_angle, click_dwell_s, feed_mm_min=3000, sleep_fn=time.sleep)`
- `position -> tuple[float, float]` — unchanged (tracked from accumulated jogs).
- `jog(dx_mm, dy_mm) -> bool` — keeps the existing soft-limit `_clamp` (the only
  travel guard; no endstops are wired). Sends `J <real_dx> <real_dy> <feed>\n`,
  waits for `ok`, updates tracked position, returns `False` if clamped.
- `click()` — sends `S <press_angle>\n`, sleeps `click_dwell_s`, sends
  `S <release_angle>\n`.
- `feed_hold()` / `safe_stop()` — write the raw `!` byte.

`_send` writes the line, then reads lines until `ok` (raising `RuntimeError` on
`err`), matching the current ok-handshake loop.

### 3.4 Config — `aimplotter/config.py`

- Remove `press_cmd`, `release_cmd`.
- Add `press_angle: int = 60`, `release_angle: int = 90` (tune to servo horn).
- `port`, `baud` (115200), soft limits, everything else unchanged.
- `steps/mm` is **not** in Python config — it lives in firmware.

### 3.5 Wiring — `main.py`, `calibrate.py`

Only the `StepperPlotter` constructor call changes: pass `config.press_angle` /
`config.release_angle` instead of the old M-code strings. Loop, controller,
drift, capture, kill-switch untouched.

## 4. Data Flow (unchanged above the driver)

`capture → detect_blue → nearest_to_center → PDController.step → StepperPlotter.jog`
per frame; on hitbox hit → `StepperPlotter.click`; on dead frames →
`DriftCorrector.tick → StepperPlotter.jog`. The GAIN (mm-per-pixel) calibration
via `calibrate.py` is unaffected — it still jogs a known mm and measures pixel
shift.

## 5. Error Handling & Safety

- **Soft-limit clamp** in `jog()` stays the sole travel guard (no endstops).
- **Kill switch:** `q` stops the Python loop; `finally` calls `safe_stop()` →
  `!`. Firmware aborts mid-move on `!`.
- **Serial errors:** `_send` raises `RuntimeError` on `err` reply; `main.py`
  swallows exceptions in the `finally` cleanup path as today.
- **Boot settle:** `main.py` keeps the ~2 s sleep after opening serial so the
  Uno finishes resetting before the first command.

## 6. Testing

- `tests/test_plotter.py` rewritten against a `FakeSerial` that acks `ok\n`:
  - `jog` sends a line starting `J ` with correct `X`/`Y`… → assert on the `J`
    payload and tracked position (adapt existing format assertions).
  - `jog` clamps to soft limits and returns `False` beyond travel (unchanged
    logic, unchanged assertion).
  - `click` sends `S <press_angle>` then `S <release_angle>`.
  - `safe_stop`/`feed_hold` write the raw `!` byte.
- All other unit tests (detector, targeting, controller, drift) and the
  integration test are unaffected — they never touch the serial protocol.
- Firmware is verified manually on hardware (jog a known distance, confirm servo
  press/release); no automated firmware test.

## 7. Files Touched

- Create: `firmware/mm6000/mm6000.ino`
- Edit: `aimplotter/plotter.py` (class rename + new protocol)
- Edit: `aimplotter/config.py` (angles replace M-codes)
- Edit: `aimplotter/main.py` (constructor args)
- Edit: `aimplotter/calibrate.py` (constructor args)
- Edit: `tests/test_plotter.py` (protocol assertions)

## 8. Out of Scope

- Homing / endstops (none wired).
- Coordinated same-instant multi-axis finish (accepted skew).
- Runtime-configurable steps/mm (reflash instead).
- Z-lift servo for true auto-recenter (future, as noted in prior design §6).
