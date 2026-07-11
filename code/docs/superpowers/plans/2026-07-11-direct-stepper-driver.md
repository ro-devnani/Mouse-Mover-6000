# Direct Stepper Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace GRBL with custom Arduino firmware that drives the CNC Shield V3's A4988 STEP/DIR pins and click servo directly, controlled from Python over a simple line-based serial protocol.

**Architecture:** The Python↔hardware seam keeps its current shape — send an ASCII line, wait for `ok`. Only the plotter driver internals, a few `config.py` fields, and the (new) Arduino firmware change. Detection, targeting, PD controller, drift corrector, capture, and kill-switch are untouched.

**Tech Stack:** Python 3.10+ · `pyserial` · `pytest` (existing). Arduino C++ · `AccelStepper` · `Servo`.

## Global Constraints

- Python 3.10+ (existing codebase uses `X | None` typing).
- Serial link: USB @ **115200** baud, `\n`-terminated ASCII lines, every command acked `ok\n` (unknown → `err\n`); `!` is a single realtime byte with no newline and no ack.
- Moves are **relative** in millimetres; `steps/mm` lives in firmware `#define`s, not Python.
- No endstops/homing — the Python soft-limit `_clamp` is the sole travel guard.
- Plotter driver public surface is unchanged from `GRBLPlotter`: `jog(dx,dy)->bool`, `click()`, `feed_hold()`, `safe_stop()`, `position` property. Only the class name (`StepperPlotter`) and the bytes it emits change.
- CNC Shield V3 pin map: X.STEP=D2 X.DIR=D5, Y.STEP=D3 Y.DIR=D6, driver ENABLE=D8 (active low), servo=D11.

---

### Task 1: Config — servo angles replace M-code strings

**Files:**
- Modify: `aimplotter/config.py:29-30` (remove `press_cmd`/`release_cmd`)
- Test: covered by Task 3's plotter tests (config has no dedicated test file; the existing `test_targeting.py` config assertions don't touch these fields).

**Interfaces:**
- Produces: `Config.press_angle: int = 60`, `Config.release_angle: int = 90`. Removes `Config.press_cmd`, `Config.release_cmd`.

- [ ] **Step 1: Edit `aimplotter/config.py`**

Replace the two lines in the `--- plotter / serial ---` block:

```python
    press_cmd: str = "M3 S1000"
    release_cmd: str = "M5"
```

with:

```python
    press_angle: int = 60         # servo degrees when clicking
    release_angle: int = 90       # servo degrees at rest
```

Leave `port`, `baud`, `click_dwell_s`, and every other field unchanged.

- [ ] **Step 2: Verify nothing else imports the old fields**

Run: `grep -rn "press_cmd\|release_cmd" aimplotter tests`
Expected: only hits are in `plotter.py`, `main.py`, `calibrate.py`, `tests/test_plotter.py` — all rewritten in Tasks 3–5. No stray references elsewhere.

- [ ] **Step 3: Commit**

```bash
git add aimplotter/config.py
git commit -m "feat: config servo angles replace GRBL M-code strings"
```

---

### Task 2: Arduino firmware — direct stepper + servo driver

**Files:**
- Create: `firmware/mm6000/mm6000.ino`

**Interfaces:**
- Produces: a serial device speaking the protocol in Global Constraints:
  - `J <dx_mm> <dy_mm> <feed_mm_min>\n` → move, then `ok\n`
  - `S <angle>\n` → `servo.write(angle)`, then `ok\n`
  - `!` (one byte) → abort motion, no reply
  - unknown line → `err\n`
- Consumes: nothing from other tasks. `STEPS_PER_MM_X/Y` are measured on hardware and baked in (placeholder `80.0` until calibrated).

No automated test — verified manually on hardware in Step 3. This is a single self-contained deliverable (firmware sketch); it carries its own manual verification, so it is one task.

- [ ] **Step 1: Write `firmware/mm6000/mm6000.ino`**

```cpp
#include <AccelStepper.h>
#include <Servo.h>

// --- CNC Shield V3 pin map (A4988 drivers) ---
#define X_STEP 2
#define X_DIR  5
#define Y_STEP 3
#define Y_DIR  6
#define ENABLE 8      // active LOW: energizes all drivers
#define SERVO_PIN 11

// --- machine constants (measure steps/mm on the built rig, then set) ---
#define STEPS_PER_MM_X 80.0
#define STEPS_PER_MM_Y 80.0
#define ACCEL 2000.0            // steps/s^2
#define DEFAULT_SPEED 1000.0    // steps/s fallback if feed missing/zero

AccelStepper xAxis(AccelStepper::DRIVER, X_STEP, X_DIR);
AccelStepper yAxis(AccelStepper::DRIVER, Y_STEP, Y_DIR);
Servo clickServo;

char buf[48];
uint8_t len = 0;

void setup() {
  pinMode(ENABLE, OUTPUT);
  digitalWrite(ENABLE, LOW);   // enable drivers
  xAxis.setAcceleration(ACCEL);
  yAxis.setAcceleration(ACCEL);
  xAxis.setMaxSpeed(DEFAULT_SPEED);
  yAxis.setMaxSpeed(DEFAULT_SPEED);
  clickServo.attach(SERVO_PIN);
  clickServo.write(90);        // rest angle
  Serial.begin(115200);
  Serial.println("mm6000 ready");
}

// Run both axes to their targets. Returns early if a '!' arrives mid-move.
void runMove() {
  while (xAxis.distanceToGo() != 0 || yAxis.distanceToGo() != 0) {
    if (Serial.available() && Serial.peek() == '!') {
      Serial.read();           // consume the '!'
      xAxis.stop();
      yAxis.stop();
      xAxis.setCurrentPosition(xAxis.currentPosition());
      yAxis.setCurrentPosition(yAxis.currentPosition());
      return;
    }
    xAxis.run();
    yAxis.run();
  }
}

void handleJog(char *args) {
  float dx = 0, dy = 0, feed = 0;
  // args: "<dx_mm> <dy_mm> <feed_mm_min>"
  sscanf(args, "%f %f %f", &dx, &dy, &feed);
  float sx = feed > 0 ? (feed / 60.0) * STEPS_PER_MM_X : DEFAULT_SPEED;
  float sy = feed > 0 ? (feed / 60.0) * STEPS_PER_MM_Y : DEFAULT_SPEED;
  xAxis.setMaxSpeed(sx);
  yAxis.setMaxSpeed(sy);
  xAxis.move((long)lround(dx * STEPS_PER_MM_X));
  yAxis.move((long)lround(dy * STEPS_PER_MM_Y));
  runMove();
  Serial.println("ok");
}

void handleServo(char *args) {
  int angle = 90;
  sscanf(args, "%d", &angle);
  if (angle < 0) angle = 0;
  if (angle > 180) angle = 180;
  clickServo.write(angle);
  Serial.println("ok");
}

void handleLine(char *line) {
  if (line[0] == 'J') {
    handleJog(line + 1);
  } else if (line[0] == 'S') {
    handleServo(line + 1);
  } else {
    Serial.println("err");
  }
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '!') {            // realtime abort when idle: nothing to stop
      xAxis.stop();
      yAxis.stop();
      len = 0;                 // discard any partial line
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
```

- [ ] **Step 2: Compile-check**

Install `AccelStepper` via Arduino Library Manager, then verify the sketch compiles:

Run (Arduino CLI): `arduino-cli compile --fqbn arduino:avr:uno firmware/mm6000`
Expected: `Sketch uses ... bytes`, no errors. (Or use the IDE's Verify button.)

- [ ] **Step 3: Manual hardware smoke test**

Flash to the Uno. Open Serial Monitor @ 115200, line ending = Newline.
- Expect banner `mm6000 ready`.
- Send `J 10 0 3000` → X carriage moves ~10 mm, replies `ok`. (Exact mm depends on `STEPS_PER_MM_X`; correct the `#define` once measured.)
- Send `S 60` → servo presses, `ok`. Send `S 90` → releases, `ok`.
- Send `J 50 0 3000` then, mid-move, `!` → motion stops immediately.

- [ ] **Step 4: Commit**

```bash
git add firmware/mm6000/mm6000.ino
git commit -m "feat: Arduino direct stepper+servo firmware, serial protocol"
```

---

### Task 3: StepperPlotter driver + tests

**Files:**
- Modify: `aimplotter/plotter.py` (rename class, replace protocol)
- Test: `tests/test_plotter.py` (rewrite assertions)

**Interfaces:**
- Consumes: `Config.press_angle`, `Config.release_angle` (Task 1); the firmware protocol (Task 2).
- Produces: `StepperPlotter(serial_obj, soft_limit_mm, bed_center_mm, press_angle, release_angle, click_dwell_s, feed_mm_min=3000, sleep_fn=time.sleep)` with `jog(dx_mm, dy_mm) -> bool`, `click() -> None`, `feed_hold() -> None`, `safe_stop() -> None`, `position -> tuple[float, float]`.

- [ ] **Step 1: Rewrite the failing tests in `tests/test_plotter.py`**

Replace the whole file with:

```python
from aimplotter.plotter import StepperPlotter


class FakeSerial:
    def __init__(self):
        self.written = []
        self._lines = []

    def write(self, data):
        self.written.append(data.decode())
        self._lines.append(b"ok\n")  # firmware acks every line

    def readline(self):
        return self._lines.pop(0) if self._lines else b"ok\n"


def _plotter():
    return StepperPlotter(
        FakeSerial(), soft_limit_mm=10.0, bed_center_mm=(0.0, 0.0),
        press_angle=60, release_angle=90, click_dwell_s=0.0,
        sleep_fn=lambda s: None,
    )


def test_jog_sends_relative_move_and_tracks_position():
    p = _plotter()
    ok = p.jog(2.0, -1.5)
    assert ok is True
    assert p.position == (2.0, -1.5)
    sent = p.serial.written[-1]
    assert sent.startswith("J ")
    parts = sent.strip().split()
    assert parts[1] == "2.000" and parts[2] == "-1.500"
    assert parts[3] == "3000"          # default feed


def test_jog_clamps_to_soft_limits():
    p = _plotter()
    ok = p.jog(50.0, 0.0)              # beyond +10 limit
    assert ok is False
    assert p.position[0] == 10.0       # clamped to limit


def test_click_sends_press_then_release_angles():
    p = _plotter()
    p.click()
    assert p.serial.written[-2].strip() == "S 60"
    assert p.serial.written[-1].strip() == "S 90"


def test_feed_hold_sends_bang():
    p = _plotter()
    p.feed_hold()
    assert p.serial.written[-1] == "!"


def test_safe_stop_releases_then_halts():
    p = _plotter()
    p.safe_stop()
    assert any(w.strip() == "S 90" for w in p.serial.written)
    assert p.serial.written[-1] == "!"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_plotter.py -v`
Expected: FAIL with `ImportError: cannot import name 'StepperPlotter'`.

- [ ] **Step 3: Rewrite `aimplotter/plotter.py`**

Replace the whole file with:

```python
import time


class StepperPlotter:
    """Drives the custom Arduino firmware over serial.

    Protocol: 'J <dx> <dy> <feed>\\n' relative move, 'S <angle>\\n' servo,
    '!' realtime abort. Every non-'!' command is acked 'ok'.
    """

    def __init__(self, serial_obj, soft_limit_mm, bed_center_mm,
                 press_angle, release_angle, click_dwell_s,
                 feed_mm_min=3000, sleep_fn=time.sleep):
        self.serial = serial_obj
        self.soft_limit_mm = soft_limit_mm
        self.center = bed_center_mm
        self.press_angle = press_angle
        self.release_angle = release_angle
        self.click_dwell_s = click_dwell_s
        self.feed_mm_min = feed_mm_min
        self._sleep = sleep_fn
        self._x, self._y = bed_center_mm

    @property
    def position(self) -> tuple[float, float]:
        return (self._x, self._y)

    def _send(self, line: str) -> None:
        """Send a command, wait for 'ok'."""
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

    def _clamp(self, target, axis_center):
        lo = axis_center - self.soft_limit_mm
        hi = axis_center + self.soft_limit_mm
        if target < lo:
            return lo, True
        if target > hi:
            return hi, True
        return target, False

    def jog(self, dx_mm, dy_mm) -> bool:
        nx, cx_clamped = self._clamp(self._x + dx_mm, self.center[0])
        ny, cy_clamped = self._clamp(self._y + dy_mm, self.center[1])
        real_dx = nx - self._x
        real_dy = ny - self._y
        line = f"J {real_dx:.3f} {real_dy:.3f} {self.feed_mm_min}\n"
        self._send(line)
        self._x, self._y = nx, ny
        return not (cx_clamped or cy_clamped)

    def click(self) -> None:
        self._send(f"S {self.press_angle}\n")
        self._sleep(self.click_dwell_s)
        self._send(f"S {self.release_angle}\n")

    def safe_stop(self) -> None:
        """Release servo then abort motion."""
        self._send(f"S {self.release_angle}\n")
        self.serial.write(b"!")

    def feed_hold(self) -> None:
        self.serial.write(b"!")  # realtime, no ack
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_plotter.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add aimplotter/plotter.py tests/test_plotter.py
git commit -m "feat: StepperPlotter driver for custom firmware protocol"
```

---

### Task 4: Wire the new driver into main.py

**Files:**
- Modify: `aimplotter/main.py:114-121` (import + constructor)

**Interfaces:**
- Consumes: `StepperPlotter` (Task 3), `Config.press_angle`/`release_angle` (Task 1).
- Produces: no new interface; `run_loop` and `_PrintPlotter` unchanged.

- [ ] **Step 1: Edit the serial-plotter branch in `aimplotter/main.py`**

Find (in `main()`):

```python
        import serial
        from aimplotter.plotter import GRBLPlotter
        ser = serial.Serial(config.port, config.baud, timeout=2)
        time.sleep(2)
        ser.reset_input_buffer()
        plotter = GRBLPlotter(ser, config.soft_limit_mm, config.bed_center_mm,
                             config.press_cmd, config.release_cmd,
                             config.click_dwell_s)
```

Replace with:

```python
        import serial
        from aimplotter.plotter import StepperPlotter
        ser = serial.Serial(config.port, config.baud, timeout=2)
        time.sleep(2)          # let the Uno finish resetting
        ser.reset_input_buffer()
        plotter = StepperPlotter(ser, config.soft_limit_mm, config.bed_center_mm,
                                config.press_angle, config.release_angle,
                                config.click_dwell_s)
```

- [ ] **Step 2: Run the integration suite (proves wiring didn't break the loop)**

Run: `python -m pytest tests/test_integration.py -v`
Expected: PASS (2 passed) — the integration test uses a fake plotter, so it exercises `run_loop` independent of the serial branch.

- [ ] **Step 3: Dry-run smoke check (no hardware, no serial import path)**

Run: `python -c "import aimplotter.main"`
Expected: imports cleanly, no `AttributeError` for removed config fields.

- [ ] **Step 4: Commit**

```bash
git add aimplotter/main.py
git commit -m "feat: wire StepperPlotter into main loop"
```

---

### Task 5: Update calibrate.py

**Files:**
- Modify: `aimplotter/calibrate.py:44-52` (import + constructor)

**Interfaces:**
- Consumes: `StepperPlotter` (Task 3), `Config.press_angle`/`release_angle` (Task 1).
- Produces: no new interface; `measure_gain` unchanged.

- [ ] **Step 1: Edit the `main()` of `aimplotter/calibrate.py`**

Find:

```python
    from aimplotter.plotter import GRBLPlotter
```

Replace with:

```python
    from aimplotter.plotter import StepperPlotter
```

Then find:

```python
    plotter = GRBLPlotter(ser, config.soft_limit_mm, config.bed_center_mm,
                         config.press_cmd, config.release_cmd,
                         config.click_dwell_s)
```

Replace with:

```python
    plotter = StepperPlotter(ser, config.soft_limit_mm, config.bed_center_mm,
                            config.press_angle, config.release_angle,
                            config.click_dwell_s)
```

- [ ] **Step 2: Import smoke check**

Run: `python -c "import aimplotter.calibrate"`
Expected: imports cleanly, no reference to removed config fields.

- [ ] **Step 3: Commit**

```bash
git add aimplotter/calibrate.py
git commit -m "feat: calibrate.py uses StepperPlotter"
```

---

### Task 6: Full-suite regression + grep sweep

**Files:** none created; verification-only task gating the whole change.

- [ ] **Step 1: Confirm no GRBL references remain in Python**

Run: `grep -rn "GRBL\|press_cmd\|release_cmd\|\\$J=" aimplotter tests`
Expected: no matches. (The string `GRBL` may still appear in `docs/` — that's fine; only `aimplotter` and `tests` must be clean.)

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest -v`
Expected: all tests pass — detector, targeting, controller, plotter (rewritten), drift, integration.

- [ ] **Step 3: Commit (if the grep sweep required any doc/comment cleanup)**

```bash
git add -A
git commit -m "chore: remove residual GRBL references"
```

(If Step 1 was already clean and nothing changed, skip this commit.)

---

## Self-Review

**Spec coverage** (design §→task):
- §3.1 firmware → Task 2. ✅
- §3.2 serial protocol → Task 2 (firmware side) + Task 3 (`_send`/`jog`/`click`). ✅
- §3.3 StepperPlotter → Task 3. ✅
- §3.4 config angles → Task 1. ✅
- §3.5 main/calibrate wiring → Tasks 4, 5. ✅
- §5 safety (soft-clamp, `!` abort, `safe_stop`) → Task 3 (`_clamp`, `safe_stop`, `feed_hold`) + Task 2 (mid-move `!`). ✅
- §6 testing (rewritten `test_plotter.py`, untouched others) → Task 3 + Task 6. ✅
- §7 files touched → all six mapped. ✅

**Placeholder scan:** No TBD/TODO. `STEPS_PER_MM_X = 80.0` is a documented measured-on-hardware default with a correction step (Task 2 Step 3), not a placeholder gap. ✅

**Type consistency:** `StepperPlotter(serial_obj, soft_limit_mm, bed_center_mm, press_angle, release_angle, click_dwell_s, feed_mm_min=3000, sleep_fn=time.sleep)` identical across Task 3 def, Task 3 test, Task 4 call, Task 5 call. Protocol strings `J `/`S `/`!` identical between firmware (Task 2) and driver (Task 3) and test assertions (Task 3). Config `press_angle`/`release_angle` consistent Tasks 1/3/4/5. ✅
