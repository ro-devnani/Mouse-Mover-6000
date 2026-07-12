# Velocity-Based Smooth Movement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the choppy stop-start aim system with a continuous velocity-streaming system where the controller commands per-axis speed and the firmware runs steppers non-blocking, so motion glides instead of halting every frame.

**Architecture:** New parallel modules alongside the existing ones. A `VelocityController` maps pixel error (plus target-motion feedforward) to per-axis velocity in mm/s. A `VelocityPlotter` streams `V vx vy` commands fire-and-forget. A `velocity_main.run_velocity_loop` drives detect→aim→click with no settle sleep and no per-move ack stall. A new firmware sketch runs the steppers at a continuously slewed commanded speed with a safety watchdog and firmware-authoritative soft limits.

**Tech Stack:** Python 3, OpenCV/numpy (detection, reused), pyserial, pytest; Arduino C++ with AccelStepper + Servo.

## Global Constraints

- Existing files are **left untouched**: `controller.py`, `plotter.py`, `main.py`, `mm6000.ino`, `calibrate.py`, and their tests must still pass.
- All Python source lives under `code/aimplotter/`; all tests under `code/tests/`. Tests are run with the working directory `code/` so `import aimplotter.*` resolves (no pytest config file exists — match existing convention).
- New Python modules import from the existing package: `aimplotter.models.Ball`, `aimplotter.targeting.{error_vector,nearest_to_center}`, `aimplotter.detector.detect_blue`, `aimplotter.controller.on_target`, `aimplotter.tracker.{Tracker,select_locked}`.
- Firmware protocol for velocity: `V <vx_mm_s> <vy_mm_s>\n` is **fire-and-forget (no `ok` ack)**. `S <angle>\n` keeps its `ok` ack. `!` aborts (zeroes target velocity).
- Float wire format: 3 decimals (`f"{v:.3f}"`), matching the existing `J` command format.
- Firmware origin: stepper `currentPosition()` starts at 0 = bed center, matching the Python `bed_center_mm=(0,0)` reference. Soft limit in steps = `soft_limit_mm * STEPS_PER_MM`.
- Watchdog timeout: 200 ms. Firmware constant `WATCHDOG_MS = 200`; config mirror `vel_watchdog_ms = 200`.

---

### Task 1: Config velocity fields

**Files:**
- Modify: `code/aimplotter/config.py` (append fields to the `Config` dataclass)
- Test: `code/tests/test_config_velocity.py` (create)

**Interfaces:**
- Consumes: existing `Config` dataclass.
- Produces: new attributes on `Config`: `kp_v: float`, `kff: float`, `max_speed_mm_s: float`, `vel_watchdog_ms: int`, `vel_deadzone_tol_px: float`. (Reuses existing `gain`, `invert_x`, `invert_y`, `screen_center`, `hitbox_tol_px`, soft-limit/servo/serial fields.)

- [ ] **Step 1: Write the failing test**

Create `code/tests/test_config_velocity.py`:

```python
from aimplotter.config import Config


def test_velocity_defaults_present():
    c = Config()
    assert c.kp_v > 0
    assert c.kff >= 0
    assert c.max_speed_mm_s > 0
    assert c.vel_watchdog_ms == 200
    assert c.vel_deadzone_tol_px > 0


def test_velocity_fields_do_not_disturb_existing():
    c = Config()
    assert c.gain == 0.24          # existing stop-start knob untouched
    assert c.move_settle_s == 0.04
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code && python -m pytest tests/test_config_velocity.py -v`
Expected: FAIL — `AttributeError: 'Config' object has no attribute 'kp_v'`

- [ ] **Step 3: Add the fields**

In `code/aimplotter/config.py`, after the `# --- control ---` block (immediately before the `# --- plotter / serial ---` comment), insert:

```python
    # --- velocity control (smooth streaming system) ---
    kp_v: float = 0.05            # mm/s commanded speed per px of error
    kff: float = 0.5             # feedforward scale on target pixel motion
    max_speed_mm_s: float = 40.0  # velocity magnitude clamp
    vel_watchdog_ms: int = 200    # firmware halts if no V within this window
    vel_deadzone_tol_px: float = 6.0  # hold zone = ball radius + this
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code && python -m pytest tests/test_config_velocity.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add code/aimplotter/config.py code/tests/test_config_velocity.py
git commit -m "feat: add velocity-control config fields"
```

---

### Task 2: VelocityController

**Files:**
- Create: `code/aimplotter/velocity_controller.py`
- Test: `code/tests/test_velocity_controller.py`

**Interfaces:**
- Consumes: `Config.kp_v`, `Config.kff`, `Config.gain`, `Config.max_speed_mm_s`.
- Produces:
  - `class VelocityController(kp_v: float, kff: float, gain: float, max_speed_mm_s: float)`
  - `VelocityController.reset() -> None`
  - `VelocityController.step(target_px: tuple[float, float], center: tuple[float, float], dt: float) -> tuple[float, float]` — returns `(vx_mm_s, vy_mm_s)`.
  - The returned velocity uses the same sign convention as `error_vector` (target minus center); axis inversion is applied by the caller, not here.

- [ ] **Step 1: Write the failing test**

Create `code/tests/test_velocity_controller.py`:

```python
import math
from aimplotter.velocity_controller import VelocityController


def test_velocity_proportional_to_error():
    c = VelocityController(kp_v=0.05, kff=0.0, gain=0.2, max_speed_mm_s=100.0)
    vx, vy = c.step(target_px=(1060.0, 440.0), center=(960.0, 540.0), dt=0.03)
    # error = (+100, -100); kff=0 so pure P
    assert math.isclose(vx, 5.0, abs_tol=1e-6)   # 100 * 0.05
    assert math.isclose(vy, -5.0, abs_tol=1e-6)  # -100 * 0.05


def test_feedforward_adds_target_motion():
    c = VelocityController(kp_v=0.0, kff=1.0, gain=0.2, max_speed_mm_s=100.0)
    # first sample seeds prev; error term zero (kp_v=0), no prev motion yet
    v0 = c.step(target_px=(960.0, 540.0), center=(960.0, 540.0), dt=0.1)
    assert v0 == (0.0, 0.0)
    # target moved +30px in x over dt=0.1s -> 300 px/s; ff = kff*gain*300 = 60 mm/s
    vx, vy = c.step(target_px=(990.0, 540.0), center=(960.0, 540.0), dt=0.1)
    assert math.isclose(vx, 60.0, abs_tol=1e-6)
    assert math.isclose(vy, 0.0, abs_tol=1e-6)


def test_velocity_is_clamped():
    c = VelocityController(kp_v=1.0, kff=0.0, gain=0.2, max_speed_mm_s=5.0)
    vx, vy = c.step(target_px=(1060.0, 540.0), center=(960.0, 540.0), dt=0.03)
    assert math.isclose(math.hypot(vx, vy), 5.0, abs_tol=1e-6)


def test_reset_clears_feedforward_history():
    c = VelocityController(kp_v=0.0, kff=1.0, gain=0.2, max_speed_mm_s=100.0)
    c.step(target_px=(960.0, 540.0), center=(960.0, 540.0), dt=0.1)
    c.reset()
    # after reset the next sample is treated as first -> no feedforward
    vx, vy = c.step(target_px=(990.0, 540.0), center=(960.0, 540.0), dt=0.1)
    assert vx == 0.0 and vy == 0.0


def test_zero_or_negative_dt_skips_feedforward():
    c = VelocityController(kp_v=0.0, kff=1.0, gain=0.2, max_speed_mm_s=100.0)
    c.step(target_px=(960.0, 540.0), center=(960.0, 540.0), dt=0.1)
    vx, vy = c.step(target_px=(990.0, 540.0), center=(960.0, 540.0), dt=0.0)
    assert vx == 0.0 and vy == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code && python -m pytest tests/test_velocity_controller.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aimplotter.velocity_controller'`

- [ ] **Step 3: Write the implementation**

Create `code/aimplotter/velocity_controller.py`:

```python
import math


class VelocityController:
    """Maps a target's pixel position to a per-axis velocity command (mm/s).

    v = kp_v * error_px + kff * gain * target_pixel_velocity

    The proportional term chases the error; the feedforward term matches the
    target's own frame-to-frame motion so a moving target is tracked with less
    lag. Output magnitude is clamped to max_speed_mm_s. Sign convention matches
    error_vector (target - center); axis inversion is the caller's job.
    """

    def __init__(self, kp_v, kff, gain, max_speed_mm_s):
        self.kp_v = kp_v
        self.kff = kff
        self.gain = gain            # mm per px, converts px/s -> mm/s
        self.max_speed_mm_s = max_speed_mm_s
        self.reset()

    def reset(self) -> None:
        self._prev_target = None

    def step(self, target_px, center, dt) -> tuple[float, float]:
        ex = target_px[0] - center[0]
        ey = target_px[1] - center[1]

        if self._prev_target is None or dt <= 0:
            tvx = tvy = 0.0
        else:
            tvx = (target_px[0] - self._prev_target[0]) / dt
            tvy = (target_px[1] - self._prev_target[1]) / dt
        self._prev_target = (target_px[0], target_px[1])

        vx = self.kp_v * ex + self.kff * self.gain * tvx
        vy = self.kp_v * ey + self.kff * self.gain * tvy

        mag = math.hypot(vx, vy)
        if mag > self.max_speed_mm_s and mag > 0:
            scale = self.max_speed_mm_s / mag
            vx *= scale
            vy *= scale
        return (vx, vy)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code && python -m pytest tests/test_velocity_controller.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add code/aimplotter/velocity_controller.py code/tests/test_velocity_controller.py
git commit -m "feat: VelocityController maps error + feedforward to mm/s"
```

---

### Task 3: VelocityPlotter

**Files:**
- Create: `code/aimplotter/velocity_plotter.py`
- Test: `code/tests/test_velocity_plotter.py`

**Interfaces:**
- Consumes: a serial-like object with `write(bytes)` and `readline() -> bytes`; `Config` press/release/dwell/servo fields.
- Produces:
  - `class VelocityPlotter(serial_obj, press_angle, release_angle, click_dwell_s, sleep_fn=time.sleep)`
  - `VelocityPlotter.set_velocity(vx_mm_s: float, vy_mm_s: float) -> None` — writes `V vx vy\n`, **never reads** (non-blocking, no ack).
  - `VelocityPlotter.click() -> None` — `S press`, dwell, `S release`; each `S` waits for `ok`.
  - `VelocityPlotter.safe_stop() -> None` — `V 0 0`, `S release`, then `!`.
  - `VelocityPlotter.feed_hold() -> None` — writes `!`.

- [ ] **Step 1: Write the failing test**

Create `code/tests/test_velocity_plotter.py`:

```python
from aimplotter.velocity_plotter import VelocityPlotter


class FakeSerial:
    def __init__(self):
        self.written = []
        self.readline_calls = 0

    def write(self, data):
        self.written.append(data.decode())

    def readline(self):
        self.readline_calls += 1
        return b"ok\n"


def _plotter(ser):
    return VelocityPlotter(ser, press_angle=60, release_angle=90,
                           click_dwell_s=0.0, sleep_fn=lambda s: None)


def test_set_velocity_streams_v_command_without_reading():
    ser = FakeSerial()
    p = _plotter(ser)
    p.set_velocity(1.5, -2.0)
    assert ser.written[-1] == "V 1.500 -2.000\n"
    assert ser.readline_calls == 0        # fire-and-forget, no ack-wait


def test_click_sends_press_then_release_and_acks():
    ser = FakeSerial()
    p = _plotter(ser)
    p.click()
    assert ser.written[-2].strip() == "S 60"
    assert ser.written[-1].strip() == "S 90"
    assert ser.readline_calls >= 2        # each S waits for ok


def test_safe_stop_zeroes_velocity_releases_then_halts():
    ser = FakeSerial()
    p = _plotter(ser)
    p.safe_stop()
    assert ser.written[0] == "V 0.000 0.000\n"
    assert any(w.strip() == "S 90" for w in ser.written)
    assert ser.written[-1] == "!"


def test_feed_hold_sends_bang():
    ser = FakeSerial()
    p = _plotter(ser)
    p.feed_hold()
    assert ser.written[-1] == "!"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code && python -m pytest tests/test_velocity_plotter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aimplotter.velocity_plotter'`

- [ ] **Step 3: Write the implementation**

Create `code/aimplotter/velocity_plotter.py`:

```python
import time


class VelocityPlotter:
    """Streams continuous velocity setpoints to the velocity firmware.

    Protocol: 'V <vx> <vy>\\n' sets per-axis mm/s and is fire-and-forget (the
    firmware does not ack it, so we never block reading). 'S <angle>\\n' drives
    the click servo and IS acked with 'ok'. '!' is a realtime abort.
    """

    def __init__(self, serial_obj, press_angle, release_angle, click_dwell_s,
                 sleep_fn=time.sleep):
        self.serial = serial_obj
        self.press_angle = press_angle
        self.release_angle = release_angle
        self.click_dwell_s = click_dwell_s
        self._sleep = sleep_fn

    def _send_acked(self, line: str) -> None:
        """Send a command and wait for the firmware 'ok' (used for 'S')."""
        self.serial.write(line.encode())
        for _ in range(100):
            resp = self.serial.readline()
            if not resp:
                break
            text = resp.decode(errors="replace").strip().lower()
            if text.startswith("ok"):
                break
            if text.startswith("err"):
                raise RuntimeError("firmware rejected: " + line.strip())

    def set_velocity(self, vx_mm_s, vy_mm_s) -> None:
        """Stream a velocity setpoint. Non-blocking: writes, never reads."""
        self.serial.write(f"V {vx_mm_s:.3f} {vy_mm_s:.3f}\n".encode())

    def click(self) -> None:
        self._send_acked(f"S {self.press_angle}\n")
        self._sleep(self.click_dwell_s)
        self._send_acked(f"S {self.release_angle}\n")

    def safe_stop(self) -> None:
        """Halt motion, release servo, then realtime abort."""
        self.set_velocity(0.0, 0.0)
        self._send_acked(f"S {self.release_angle}\n")
        self.serial.write(b"!")

    def feed_hold(self) -> None:
        self.serial.write(b"!")  # realtime, no ack
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code && python -m pytest tests/test_velocity_plotter.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add code/aimplotter/velocity_plotter.py code/tests/test_velocity_plotter.py
git commit -m "feat: VelocityPlotter streams non-blocking V setpoints"
```

---

### Task 4: velocity_main run loop

**Files:**
- Create: `code/aimplotter/velocity_main.py`
- Test: `code/tests/test_velocity_integration.py`

**Interfaces:**
- Consumes: `VelocityController.step`, `VelocityController.reset`, a plotter with `set_velocity/click/safe_stop`, `detect_blue`, `nearest_to_center`, `error_vector`, `on_target`, `Tracker`/`select_locked` (optional), `Config`.
- Produces:
  - `run_velocity_loop(frame_source, plotter, controller, config, should_stop, clock, tracker=None) -> list[str]` — action log with entries drawn from `{"vel", "hold", "click", "idle"}`.
  - `clock` is a zero-arg callable returning seconds (default `time.monotonic` in `main`); used to compute `dt` between frames for feedforward.
  - `class _PrintVelocityPlotter` — dry-run plotter printing `V`/`CLICK`.
  - `main(argv=None) -> None` — wires capture, kill switch, serial, and the loop.

- [ ] **Step 1: Write the failing test**

Create `code/tests/test_velocity_integration.py`:

```python
import numpy as np
import cv2
from aimplotter.velocity_main import run_velocity_loop
from aimplotter.velocity_controller import VelocityController
from aimplotter.config import Config


class FakeVP:
    def __init__(self):
        self.velocities = []
        self.clicks = 0

    def set_velocity(self, vx, vy):
        self.velocities.append((vx, vy))

    def click(self):
        self.clicks += 1


def _frame(cx, cy, r=25):
    f = np.zeros((1080, 1920, 3), dtype=np.uint8)
    if cx is not None:
        cv2.circle(f, (cx, cy), r, (255, 80, 0), -1)
    return f


def _clock_from(seq):
    it = iter(seq)
    return lambda: next(it)


def test_loop_streams_velocity_then_clicks_then_idles():
    C = Config()
    # frame 1: ball off-center -> vel; frame 2: ball ON center -> click;
    # frame 3: no ball -> idle (velocity zeroed)
    frames = [_frame(1200, 700), _frame(960, 540), _frame(None, None)]
    it = iter(frames)

    def source():
        return next(it, None)

    p = FakeVP()
    ctrl = VelocityController(C.kp_v, C.kff, C.gain, C.max_speed_mm_s)
    clock = _clock_from([0.0, 0.03, 0.06, 0.09])

    actions = run_velocity_loop(source, p, ctrl, C,
                                should_stop=lambda: False, clock=clock)

    assert "vel" in actions
    assert "click" in actions
    assert "idle" in actions
    assert p.clicks >= 1
    assert p.velocities[-1] == (0.0, 0.0)   # idle zeroes velocity


def test_loop_stops_on_kill_switch():
    C = Config()
    p = FakeVP()
    ctrl = VelocityController(C.kp_v, C.kff, C.gain, C.max_speed_mm_s)
    actions = run_velocity_loop(lambda: _frame(1200, 700), p, ctrl, C,
                                should_stop=lambda: True,
                                clock=_clock_from([0.0, 0.03]))
    assert actions == []


def test_offcenter_frame_commands_nonzero_velocity():
    C = Config()
    frames = [_frame(1400, 540), _frame(None, None)]
    it = iter(frames)
    p = FakeVP()
    ctrl = VelocityController(C.kp_v, C.kff, C.gain, C.max_speed_mm_s)
    run_velocity_loop(lambda: next(it, None), p, ctrl, C,
                      should_stop=lambda: False,
                      clock=_clock_from([0.0, 0.03, 0.06]))
    vx, vy = p.velocities[0]
    assert vx != 0.0     # ball right of center -> nonzero x velocity
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd code && python -m pytest tests/test_velocity_integration.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aimplotter.velocity_main'`

- [ ] **Step 3: Write the implementation**

Create `code/aimplotter/velocity_main.py`:

```python
import argparse
import time

from aimplotter.config import Config
from aimplotter.detector import detect_blue
from aimplotter.targeting import nearest_to_center, error_vector
from aimplotter.controller import on_target
from aimplotter.velocity_controller import VelocityController
from aimplotter.tracker import select_locked


def run_velocity_loop(frame_source, plotter, controller, config,
                      should_stop, clock, tracker=None) -> list[str]:
    """Stream velocity setpoints in a detect->aim->click loop.

    No settle sleep and no per-move ack stall: every frame updates the
    velocity setpoint and the firmware keeps the steppers gliding. Returns an
    action log for testing.
    """
    actions: list[str] = []
    locked_id = None
    armed = True                 # may we click? False = already hit, hold still
    prev_t = clock()
    while not should_stop():
        frame = frame_source()
        if frame is None:
            break
        now = clock()
        dt = now - prev_t
        prev_t = now

        balls = detect_blue(frame, config.hsv_lower, config.hsv_upper,
                            config.min_area_px)
        if tracker is not None:
            tracks = tracker.update(balls)
            sel = select_locked(tracks, config.screen_center, locked_id)
            target = sel.ball if sel else None
            locked_id = sel.id if sel else None
        else:
            target = nearest_to_center(balls, config.screen_center)

        if target is None:
            plotter.set_velocity(0.0, 0.0)
            controller.reset()          # drop stale feedforward history
            actions.append("idle")
            continue

        err = error_vector(target, config.screen_center)
        if on_target(err, target.r, config.vel_deadzone_tol_px):
            plotter.set_velocity(0.0, 0.0)
            if armed:
                plotter.click()
                controller.reset()
                armed = False
                actions.append("click")
            else:
                actions.append("hold")
        else:
            armed = True                # crosshair left target -> re-arm
            vx, vy = controller.step(target.center, config.screen_center, dt)
            if config.invert_x:
                vx = -vx
            if config.invert_y:
                vy = -vy
            if config.debug:
                print(f"err=({err[0]:+.0f},{err[1]:+.0f}) "
                      f"vel=({vx:+.2f},{vy:+.2f}) r={target.r:.0f}")
            plotter.set_velocity(vx, vy)
            actions.append("vel")
    return actions


class _PrintVelocityPlotter:
    """Dry-run plotter: prints velocity commands instead of sending serial."""
    def set_velocity(self, vx, vy):
        print(f"[dry-run] V {vx:.3f} {vy:.3f}")

    def click(self):
        print("[dry-run] CLICK")

    def safe_stop(self):
        print("[dry-run] SAFE STOP")

    def feed_hold(self):
        print("[dry-run] FEED HOLD")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Optical aim plotter (velocity)")
    parser.add_argument("--no-serial", action="store_true",
                        help="dry-run: print velocity commands instead of sending")
    args = parser.parse_args(argv)

    config = Config()
    controller = VelocityController(config.kp_v, config.kff, config.gain,
                                    config.max_speed_mm_s)
    from aimplotter.tracker import Tracker
    tracker = Tracker(config.track_match_dist_px, config.track_max_misses)

    stop_flag = {"stop": False}
    from pynput import keyboard

    def on_press(key):
        try:
            if key.char == config.kill_key:
                stop_flag["stop"] = True
        except AttributeError:
            pass

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    from aimplotter.capture import make_capture
    cap = make_capture(config)

    if args.no_serial:
        plotter = _PrintVelocityPlotter()
    else:
        import serial
        from aimplotter.velocity_plotter import VelocityPlotter
        ser = serial.Serial(config.port, config.baud, timeout=2)
        time.sleep(2)              # let the Uno finish resetting
        ser.reset_input_buffer()
        plotter = VelocityPlotter(ser, config.press_angle, config.release_angle,
                                  config.click_dwell_s)

    try:
        run_velocity_loop(cap.grab, plotter, controller, config,
                          should_stop=lambda: stop_flag["stop"],
                          clock=time.monotonic, tracker=tracker)
    finally:
        try:
            plotter.safe_stop()
        except Exception:
            pass
        cap.close()
        listener.stop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd code && python -m pytest tests/test_velocity_integration.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full suite to confirm nothing regressed**

Run: `cd code && python -m pytest -v`
Expected: PASS (all existing tests + the new ones)

- [ ] **Step 6: Commit**

```bash
git add code/aimplotter/velocity_main.py code/tests/test_velocity_integration.py
git commit -m "feat: velocity_main streams setpoints with no settle stall"
```

---

### Task 5: Velocity firmware sketch

**Files:**
- Create: `code/firmware/mm6000_velocity/mm6000_velocity.ino`

**Interfaces:**
- Consumes: serial lines `V <vx_mm_s> <vy_mm_s>\n` (no ack), `S <angle>\n` (ack `ok`), `!` (abort). Must match `VelocityPlotter` exactly.
- Produces: continuous non-blocking stepper motion at a slewed commanded speed, watchdog halt, per-axis firmware soft limits.

> **Note:** This task is bench/hardware-tested, not unit-tested (no automated harness for Arduino here). Its deliverable is the sketch plus the manual verification checklist in Step 3. If `arduino-cli` is installed, Step 2 compiles it; otherwise skip Step 2 and rely on the IDE compile + bench test.

- [ ] **Step 1: Write the sketch**

Create `code/firmware/mm6000_velocity/mm6000_velocity.ino`:

```cpp
#include <AccelStepper.h>
#include <Servo.h>
#include <stdlib.h>   // strtod, atoi (avr-libc float sscanf is unsupported)

// --- CNC Shield V3 pin map (A4988 drivers) ---
#define X_STEP 2
#define X_DIR  5
#define Y_STEP 3
#define Y_DIR  6
#define ENABLE 8      // active LOW: energizes all drivers
#define SERVO_PIN 11

// --- machine constants (match mm6000.ino) ---
#define STEPS_PER_MM_X 5.0
#define STEPS_PER_MM_Y 5.0
#define ACCEL 2000.0            // steps/s^2: bounds how fast commanded speed slews
#define MAX_STEP_SPEED 4000.0   // steps/s hard cap per axis

// --- safety ---
#define WATCHDOG_MS 200         // no V within this -> ramp to zero
#define SOFT_LIMIT_MM 90.0      // +/- travel from startup origin
const long LIMIT_STEPS_X = (long)(SOFT_LIMIT_MM * STEPS_PER_MM_X);
const long LIMIT_STEPS_Y = (long)(SOFT_LIMIT_MM * STEPS_PER_MM_Y);

AccelStepper xAxis(AccelStepper::DRIVER, X_STEP, X_DIR);
AccelStepper yAxis(AccelStepper::DRIVER, Y_STEP, Y_DIR);
Servo clickServo;

char buf[48];
uint8_t len = 0;

float targetSpeedX = 0, targetSpeedY = 0;   // steps/s setpoint from last V
float currentSpeedX = 0, currentSpeedY = 0; // slewed actual command
unsigned long lastCmdMillis = 0;
unsigned long lastMicros = 0;

void setup() {
  pinMode(ENABLE, OUTPUT);
  digitalWrite(ENABLE, LOW);   // enable drivers
  xAxis.setMaxSpeed(MAX_STEP_SPEED);
  yAxis.setMaxSpeed(MAX_STEP_SPEED);
  xAxis.setCurrentPosition(0); // origin = bed center reference
  yAxis.setCurrentPosition(0);
  clickServo.attach(SERVO_PIN);
  clickServo.write(90);        // rest angle
  Serial.begin(115200);
  lastMicros = micros();
  lastCmdMillis = millis();
  Serial.println("mm6000v ready");
}

float clampSpeed(float s) {
  if (s > MAX_STEP_SPEED) return MAX_STEP_SPEED;
  if (s < -MAX_STEP_SPEED) return -MAX_STEP_SPEED;
  return s;
}

// Move currentSpeed toward targetSpeed, limited to maxDelta steps/s this tick.
float slew(float current, float target, float maxDelta) {
  if (target > current) {
    current += maxDelta;
    if (current > target) current = target;
  } else if (target < current) {
    current -= maxDelta;
    if (current < target) current = target;
  }
  return current;
}

void handleVelocity(char *args) {
  char *p = args;
  float vx = strtod(p, &p);
  float vy = strtod(p, &p);
  targetSpeedX = clampSpeed(vx * STEPS_PER_MM_X);
  targetSpeedY = clampSpeed(vy * STEPS_PER_MM_Y);
  lastCmdMillis = millis();
  // no ack: this is the streaming hot path
}

void handleServo(char *args) {
  int angle = atoi(args);
  if (angle < 0) angle = 0;
  if (angle > 180) angle = 180;
  clickServo.write(angle);
  Serial.println("ok");
}

void handleLine(char *line) {
  if (line[0] == 'V') {
    handleVelocity(line + 1);
  } else if (line[0] == 'S') {
    handleServo(line + 1);
  } else {
    Serial.println("err");
  }
}

void readSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '!') {              // realtime abort: stop commanding motion
      targetSpeedX = 0;
      targetSpeedY = 0;
      len = 0;                   // discard any partial line
      continue;
    }
    if (c == '\n') {
      buf[len] = '\0';
      if (len > 0) handleLine(buf);
      len = 0;
    } else if (len < sizeof(buf) - 1) {
      buf[len++] = c;
    }
  }
}

void loop() {
  readSerial();

  // watchdog: host went quiet -> command zero (slew still ramps it down)
  if (millis() - lastCmdMillis > WATCHDOG_MS) {
    targetSpeedX = 0;
    targetSpeedY = 0;
  }

  unsigned long now = micros();
  float dt = (now - lastMicros) / 1000000.0;
  lastMicros = now;
  if (dt <= 0) dt = 0.0001;
  float maxDelta = ACCEL * dt;   // steps/s of speed change allowed this tick

  currentSpeedX = slew(currentSpeedX, targetSpeedX, maxDelta);
  currentSpeedY = slew(currentSpeedY, targetSpeedY, maxDelta);

  // firmware-authoritative soft limits: if at edge and pushing further, stop axis
  long px = xAxis.currentPosition();
  if ((px <= -LIMIT_STEPS_X && currentSpeedX < 0) ||
      (px >=  LIMIT_STEPS_X && currentSpeedX > 0)) {
    currentSpeedX = 0;
  }
  long py = yAxis.currentPosition();
  if ((py <= -LIMIT_STEPS_Y && currentSpeedY < 0) ||
      (py >=  LIMIT_STEPS_Y && currentSpeedY > 0)) {
    currentSpeedY = 0;
  }

  xAxis.setSpeed(currentSpeedX);
  yAxis.setSpeed(currentSpeedY);
  xAxis.runSpeed();              // non-blocking: one step if due
  yAxis.runSpeed();
}
```

- [ ] **Step 2: Compile (if arduino-cli available)**

Run: `arduino-cli compile --fqbn arduino:avr:uno code/firmware/mm6000_velocity`
Expected: compiles clean. (If `arduino-cli` is not installed, compile in the Arduino IDE instead; this is a manual gate.)

- [ ] **Step 3: Bench-test checklist (manual, hardware)**

Verify on the rig:
- Sending `V 5 0\n` starts smooth continuous X motion; `V 0 0\n` ramps it to a stop (no abrupt halt).
- A setpoint jump (`V 5 0` then `V -5 0`) reverses smoothly through zero, not instantly (slew/ACCEL working).
- Stop streaming for >200 ms → motion ramps to zero on its own (watchdog).
- Drive an axis to the ± soft limit → that axis stops, the other still responds.
- `S 60\n` then `S 90\n` clicks and returns `ok`; `!` halts immediately.

- [ ] **Step 4: Commit**

```bash
git add code/firmware/mm6000_velocity/mm6000_velocity.ino
git commit -m "feat: velocity firmware with slew, watchdog, soft limits"
```

---

## Self-Review Notes

- **Spec coverage:** Firmware V/S/! + slew + watchdog + limits → Task 5. VelocityController P+feedforward+deadzone(caller)+clamp+reset → Task 2. VelocityPlotter set_velocity/click/safe_stop/feed_hold → Task 3. velocity_main loop, no settle/no block, click arming, dry-run → Task 4. Config fields → Task 1. Testing strategy → Tasks 2–4 unit/integration, Task 5 bench.
- **Deadzone location:** the spec allows the deadzone in the controller; this plan places it in the loop via the existing `on_target(err, radius, tol)` (reuse, DRY) with `vel_deadzone_tol_px`. Controller stays pure velocity math. Consistent across all tasks.
- **Type consistency:** `set_velocity(vx, vy)`, `controller.step(target_px, center, dt)`, `run_velocity_loop(..., clock, tracker=None)` used identically in impl and tests.
- **Left intact:** no existing file is modified except `config.py` (additive fields only).
```