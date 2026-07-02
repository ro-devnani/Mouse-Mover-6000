# Closed-Loop Optical Aim Plotter Implementation Plan

**Goal:** Detect neon-blue balls on a 1080p fullscreen Aim Labs feed and drive a GRBL XY plotter (carrying a physical mouse) via a closed-loop PD visual servo so the screen-center crosshair lands on the nearest ball and clicks.

**Architecture:** A per-frame loop: capture screen → HSV-detect balls → pick nearest to center → PD controller turns pixel error into a clamped relative mm jog → GRBL serial driver moves the plotter → repeat until the crosshair is inside the ball's hitbox → servo click. A drift corrector reclaims plotter travel during no-target frames. Pure logic modules (detector, targeting, controller, drift) are hardware-free and unit-tested; the plotter driver is tested against a fake serial port.

**Tech Stack:** Python 3 · `opencv-python` · `numpy` · `mss` · `pyserial` · `pynput` · `pytest`

## Global Constraints

- Python 3.10+ (uses `X | None` typing, `match` optional).
- Target display: single 1920×1080 monitor; crosshair fixed at screen center `(960, 540)`.
- GRBL on Arduino Uno + CNC Shield v3, USB serial @ **115200** baud.
- Plotter moves are **relative** (`G91`) via GRBL jog (`$J=`); each line waits for `ok`.
- Click is firmware-agnostic: configurable `PRESS_CMD` / `RELEASE_CMD` strings (default `M3 S1000` / `M5`).
- All tunables live in `config.py`; no magic numbers in logic modules — pass config values in as parameters (keep logic modules pure).
- Distances in millimetres (mm); pixel errors in pixels (px). `GAIN` = mm per px.
- Steps/mm and exact work-area travel are user-set later; use placeholder defaults.
- Every logic module is hardware-free and importable without a serial port attached.

---

## File Structure

```
mm6000/
├── requirements.txt
├── aimplotter/
│   ├── __init__.py
│   ├── config.py          # Config dataclass, all tunables + defaults
│   ├── models.py          # Ball dataclass
│   ├── detector.py        # detect_blue()
│   ├── targeting.py       # nearest_to_center(), error_vector()
│   ├── controller.py      # PDController (PD/PID), on_target()
│   ├── plotter.py         # GRBLPlotter serial driver
│   ├── drift.py           # DriftCorrector
│   ├── capture.py         # ScreenCapture (mss)
│   ├── calibrate.py       # interactive GAIN measurement (script)
│   └── main.py            # loop wiring + kill-switch + dry-run
└── tests/
    ├── test_detector.py
    ├── test_targeting.py
    ├── test_controller.py
    ├── test_plotter.py
    ├── test_drift.py
    └── test_integration.py
```

---

### Task 1: Project scaffold, config, and Ball model

**Files:**
- Create: `requirements.txt`
- Create: `aimplotter/__init__.py`
- Create: `aimplotter/config.py`
- Create: `aimplotter/models.py`
- Test: `tests/test_targeting.py` (placeholder import test here; real tests in Task 3)

**Interfaces:**
- Produces: `Ball(cx: float, cy: float, r: float)` dataclass with `center -> tuple[float, float]`.
- Produces: `Config` dataclass with fields used by all later tasks (see code).

- [ ] **Step 1: Write `requirements.txt`**

```
opencv-python>=4.8
numpy>=1.24
mss>=9.0
pyserial>=3.5
pynput>=1.7
pytest>=7.4
```

- [ ] **Step 2: Write `aimplotter/__init__.py`** (empty file)

```python
```

- [ ] **Step 3: Write the failing test for the models**

`tests/test_targeting.py`:
```python
from aimplotter.models import Ball
from aimplotter.config import Config


def test_ball_center():
    b = Ball(cx=10.0, cy=20.0, r=5.0)
    assert b.center == (10.0, 20.0)


def test_config_defaults():
    c = Config()
    assert c.baud == 115200
    assert c.screen_center == (960, 540)
    assert c.ki == 0.0  # pure PD by default
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/test_targeting.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimplotter.models'`

- [ ] **Step 5: Write `aimplotter/models.py`**

```python
from dataclasses import dataclass


@dataclass
class Ball:
    cx: float
    cy: float
    r: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.cx, self.cy)
```

- [ ] **Step 6: Write `aimplotter/config.py`**

```python
from dataclasses import dataclass, field


@dataclass
class Config:
    # --- display ---
    screen_region: dict = field(
        default_factory=lambda: {"top": 0, "left": 0, "width": 1920, "height": 1080}
    )
    screen_center: tuple[int, int] = (960, 540)

    # --- detection (neon blue in HSV; OpenCV H is 0-179) ---
    hsv_lower: tuple[int, int, int] = (90, 120, 120)
    hsv_upper: tuple[int, int, int] = (120, 255, 255)
    min_area_px: float = 80.0

    # --- control ---
    gain: float = 0.03            # mm of plotter travel per px of error
    kp: float = 1.0               # multiplies gain
    ki: float = 0.0               # 0 = pure PD
    kd: float = 0.2
    max_move_mm: float = 5.0      # clamp per frame -> "glide"
    hitbox_tol_px: float = 6.0    # extra slack added to ball radius

    # --- plotter / serial ---
    port: str = "COM3"
    baud: int = 115200
    press_cmd: str = "M3 S1000"
    release_cmd: str = "M5"
    click_dwell_s: float = 0.04

    # --- soft limits (mm), bed center is origin reference ---
    soft_limit_mm: float = 100.0  # +/- travel from start in X and Y
    bed_center_mm: tuple[float, float] = (0.0, 0.0)

    # --- drift corrector ---
    drift_idle_frames: int = 8
    drift_step_mm: float = 1.0

    # --- safety ---
    kill_key: str = "q"
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_targeting.py -v`
Expected: PASS (2 passed)

- [ ] **Step 8: Commit**

```bash
git add requirements.txt aimplotter/__init__.py aimplotter/models.py aimplotter/config.py tests/test_targeting.py
git commit -m "feat: project scaffold, Config, and Ball model"
```

---

### Task 2: Blue-ball detector

**Files:**
- Create: `aimplotter/detector.py`
- Test: `tests/test_detector.py`

**Interfaces:**
- Consumes: `Ball` (Task 1).
- Produces: `detect_blue(frame, hsv_lower, hsv_upper, min_area) -> list[Ball]` where `frame` is an HxWx3 BGR `numpy.uint8` array; returns balls sorted by descending area.

- [ ] **Step 1: Write the failing test**

`tests/test_detector.py`:
```python
import numpy as np
import cv2
from aimplotter.detector import detect_blue
from aimplotter.config import Config

C = Config()


def _frame_with_blue_circle(cx, cy, r, size=(1080, 1920)):
    frame = np.zeros((size[0], size[1], 3), dtype=np.uint8)
    # neon blue in BGR is high B, low G/R
    cv2.circle(frame, (cx, cy), r, (255, 80, 0), -1)
    return frame


def test_detects_single_ball_center():
    frame = _frame_with_blue_circle(960, 540, 30)
    balls = detect_blue(frame, C.hsv_lower, C.hsv_upper, C.min_area_px)
    assert len(balls) == 1
    assert abs(balls[0].cx - 960) <= 3
    assert abs(balls[0].cy - 540) <= 3
    assert balls[0].r > 20


def test_ignores_small_noise():
    frame = _frame_with_blue_circle(100, 100, 2)
    balls = detect_blue(frame, C.hsv_lower, C.hsv_upper, C.min_area_px)
    assert balls == []


def test_detects_multiple_sorted_by_area():
    frame = _frame_with_blue_circle(300, 300, 20)
    cv2.circle(frame, (1500, 800), 40, (255, 80, 0), -1)
    balls = detect_blue(frame, C.hsv_lower, C.hsv_upper, C.min_area_px)
    assert len(balls) == 2
    assert balls[0].r >= balls[1].r  # largest first
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_detector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimplotter.detector'`

- [ ] **Step 3: Write `aimplotter/detector.py`**

```python
import cv2
import numpy as np
from aimplotter.models import Ball


def detect_blue(frame, hsv_lower, hsv_upper, min_area) -> list[Ball]:
    """Find neon-blue blobs in a BGR frame, return Balls sorted largest-first."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lower), np.array(hsv_upper))
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    balls: list[Ball] = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        (x, y), r = cv2.minEnclosingCircle(c)
        balls.append(Ball(cx=float(x), cy=float(y), r=float(r)))

    balls.sort(key=lambda b: b.r, reverse=True)
    return balls
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_detector.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add aimplotter/detector.py tests/test_detector.py
git commit -m "feat: HSV neon-blue ball detector"
```

---

### Task 3: Targeting

**Files:**
- Create: `aimplotter/targeting.py`
- Test: `tests/test_targeting.py` (extend)

**Interfaces:**
- Consumes: `Ball` (Task 1).
- Produces:
  - `nearest_to_center(balls, center) -> Ball | None`
  - `error_vector(ball, center) -> tuple[float, float]` returning `(dx, dy)` = ball − center.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_targeting.py`)

```python
from aimplotter.targeting import nearest_to_center, error_vector


def test_nearest_to_center_picks_closest():
    near = Ball(cx=965.0, cy=545.0, r=10.0)
    far = Ball(cx=200.0, cy=200.0, r=10.0)
    assert nearest_to_center([far, near], (960, 540)) is near


def test_nearest_to_center_empty_returns_none():
    assert nearest_to_center([], (960, 540)) is None


def test_error_vector():
    b = Ball(cx=1000.0, cy=500.0, r=10.0)
    assert error_vector(b, (960, 540)) == (40.0, -40.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_targeting.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimplotter.targeting'`

- [ ] **Step 3: Write `aimplotter/targeting.py`**

```python
import math
from aimplotter.models import Ball


def error_vector(ball: Ball, center) -> tuple[float, float]:
    return (ball.cx - center[0], ball.cy - center[1])


def nearest_to_center(balls, center) -> Ball | None:
    if not balls:
        return None
    return min(
        balls,
        key=lambda b: math.hypot(b.cx - center[0], b.cy - center[1]),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_targeting.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add aimplotter/targeting.py tests/test_targeting.py
git commit -m "feat: nearest-target selection and error vector"
```

---

### Task 4: PD/PID controller

**Files:**
- Create: `aimplotter/controller.py`
- Test: `tests/test_controller.py`

**Interfaces:**
- Produces:
  - `PDController(gain, kp, ki, kd, max_move_mm)` with `step(err_px) -> tuple[float, float]` (clamped mm move) and `reset()`.
  - `on_target(err_px, radius, tol) -> bool` — True when the crosshair is inside the hitbox.
- Consumes: config scalars (Task 1).

Note: `step` takes `err_px=(dx, dy)`; output mm has the **same sign** as error (move toward target). Magnitude clamped to `max_move_mm`. Derivative uses change in error between calls.

- [ ] **Step 1: Write the failing tests**

`tests/test_controller.py`:
```python
import math
from aimplotter.controller import PDController, on_target


def test_proportional_move_toward_target():
    c = PDController(gain=0.03, kp=1.0, ki=0.0, kd=0.0, max_move_mm=5.0)
    mx, my = c.step((100.0, -100.0))
    assert mx > 0 and my < 0                 # same direction as error
    assert math.isclose(mx, 3.0, abs_tol=1e-6)   # 100 * 0.03 * 1.0


def test_move_is_clamped():
    c = PDController(gain=1.0, kp=1.0, ki=0.0, kd=0.0, max_move_mm=5.0)
    mx, my = c.step((100.0, 0.0))
    assert math.isclose(math.hypot(mx, my), 5.0, abs_tol=1e-6)


def test_derivative_damps_on_growing_error():
    c = PDController(gain=0.0, kp=0.0, ki=0.0, kd=0.5, max_move_mm=100.0)
    c.step((10.0, 0.0))            # prev err set
    mx, _ = c.step((30.0, 0.0))    # delta = 20 -> 0.5*20 = 10
    assert math.isclose(mx, 10.0, abs_tol=1e-6)


def test_reset_clears_state():
    c = PDController(gain=0.0, kp=0.0, ki=0.0, kd=0.5, max_move_mm=100.0)
    c.step((10.0, 0.0))
    c.reset()
    mx, _ = c.step((10.0, 0.0))    # treated as first sample, delta=0
    assert math.isclose(mx, 0.0, abs_tol=1e-6)


def test_on_target_inside_hitbox():
    assert on_target((3.0, 0.0), radius=10.0, tol=2.0) is True
    assert on_target((20.0, 0.0), radius=10.0, tol=2.0) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_controller.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimplotter.controller'`

- [ ] **Step 3: Write `aimplotter/controller.py`**

```python
import math


class PDController:
    """Turns a pixel-error vector into a clamped relative mm move.

    Pure PD by default (ki=0); set ki>0 for full PID. State held between
    step() calls for derivative/integral terms; reset() between targets.
    """

    def __init__(self, gain, kp, ki, kd, max_move_mm):
        self.gain = gain
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.max_move_mm = max_move_mm
        self.reset()

    def reset(self) -> None:
        self._prev = None
        self._integral = [0.0, 0.0]

    def step(self, err_px) -> tuple[float, float]:
        out = [0.0, 0.0]
        for i in range(2):
            e = err_px[i]
            d = 0.0 if self._prev is None else (e - self._prev[i])
            self._integral[i] += e
            term = self.kp * e + self.kd * d + self.ki * self._integral[i]
            out[i] = self.gain * term
        self._prev = (err_px[0], err_px[1])

        mag = math.hypot(out[0], out[1])
        if mag > self.max_move_mm and mag > 0:
            scale = self.max_move_mm / mag
            out[0] *= scale
            out[1] *= scale
        return (out[0], out[1])


def on_target(err_px, radius, tol) -> bool:
    return math.hypot(err_px[0], err_px[1]) <= (radius + tol)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_controller.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add aimplotter/controller.py tests/test_controller.py
git commit -m "feat: PD/PID controller and hitbox check"
```

---

### Task 5: GRBL serial plotter driver

**Files:**
- Create: `aimplotter/plotter.py`
- Test: `tests/test_plotter.py`

**Interfaces:**
- Produces: `GRBLPlotter(serial_obj, soft_limit_mm, bed_center_mm, press_cmd, release_cmd, click_dwell_s)` with:
  - `jog(dx_mm, dy_mm) -> bool` — sends `$J=G91 G21 X.. Y.. F..`, waits `ok`, updates tracked position, clamps to soft limits (returns `False` if clamped).
  - `click()` — sends press_cmd, dwell, release_cmd.
  - `feed_hold()` — sends `!`.
  - `position -> tuple[float, float]` — tracked absolute mm from start.
  - `sleep_fn` injectable (defaults to `time.sleep`) so tests don't actually wait.
- The serial object must expose `write(bytes)` and `readline() -> bytes`. Tests pass a `FakeSerial` that returns `b"ok\n"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_plotter.py`:
```python
from aimplotter.plotter import GRBLPlotter


class FakeSerial:
    def __init__(self):
        self.written = []
        self._lines = []

    def write(self, data):
        self.written.append(data.decode())
        self._lines.append(b"ok\n")  # GRBL acks every line

    def readline(self):
        return self._lines.pop(0) if self._lines else b"ok\n"


def _plotter():
    return GRBLPlotter(
        FakeSerial(), soft_limit_mm=10.0, bed_center_mm=(0.0, 0.0),
        press_cmd="M3 S1000", release_cmd="M5", click_dwell_s=0.0,
        sleep_fn=lambda s: None,
    )


def test_jog_sends_relative_gcode_and_tracks_position():
    p = _plotter()
    ok = p.jog(2.0, -1.5)
    assert ok is True
    assert p.position == (2.0, -1.5)
    sent = p.serial.written[-1]
    assert sent.startswith("$J=G91 G21")
    assert "X2.000" in sent and "Y-1.500" in sent


def test_jog_clamps_to_soft_limits():
    p = _plotter()
    ok = p.jog(50.0, 0.0)            # beyond +10 limit
    assert ok is False
    assert p.position[0] == 10.0     # clamped to limit


def test_click_sends_press_then_release():
    p = _plotter()
    p.click()
    assert "M3 S1000" in p.serial.written[-2]
    assert "M5" in p.serial.written[-1]


def test_feed_hold_sends_bang():
    p = _plotter()
    p.feed_hold()
    assert p.serial.written[-1] == "!"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_plotter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimplotter.plotter'`

- [ ] **Step 3: Write `aimplotter/plotter.py`**

```python
import time


class GRBLPlotter:
    def __init__(self, serial_obj, soft_limit_mm, bed_center_mm,
                 press_cmd, release_cmd, click_dwell_s,
                 feed_mm_min=3000, sleep_fn=time.sleep):
        self.serial = serial_obj
        self.soft_limit_mm = soft_limit_mm
        self.center = bed_center_mm
        self.press_cmd = press_cmd
        self.release_cmd = release_cmd
        self.click_dwell_s = click_dwell_s
        self.feed_mm_min = feed_mm_min
        self._sleep = sleep_fn
        self._x, self._y = bed_center_mm

    @property
    def position(self) -> tuple[float, float]:
        return (self._x, self._y)

    def _send(self, line: str) -> None:
        self.serial.write(line.encode() if not line.endswith("\n")
                          else line.encode())
        self.serial.readline()  # wait for GRBL 'ok'

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
        line = (f"$J=G91 G21 X{real_dx:.3f} Y{real_dy:.3f} "
                f"F{self.feed_mm_min}\n")
        self._send(line)
        self._x, self._y = nx, ny
        return not (cx_clamped or cy_clamped)

    def click(self) -> None:
        self._send(self.press_cmd + "\n")
        self._sleep(self.click_dwell_s)
        self._send(self.release_cmd + "\n")

    def feed_hold(self) -> None:
        self.serial.write(b"!")  # realtime, no newline, no ok
```

Note: `feed_hold` writes the raw `!` byte (GRBL realtime command — no newline, no `ok`). The test asserts `written[-1] == "!"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_plotter.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add aimplotter/plotter.py tests/test_plotter.py
git commit -m "feat: GRBL serial plotter driver with soft limits and click"
```

---

### Task 6: Drift corrector

**Files:**
- Create: `aimplotter/drift.py`
- Test: `tests/test_drift.py`

**Interfaces:**
- Produces: `DriftCorrector(bed_center_mm, idle_frames, step_mm)` with:
  - `on_target_frame()` — call when a ball is being aimed at (resets idle counter).
  - `tick(plotter) -> bool` — call on a no-target frame; once idle counter ≥ idle_frames, jog the plotter one `step_mm` toward bed-center. Returns True if it issued a move.
- Consumes: `GRBLPlotter.position` and `.jog()` (Task 5).

- [ ] **Step 1: Write the failing tests**

`tests/test_drift.py`:
```python
from aimplotter.drift import DriftCorrector


class FakeP:
    def __init__(self, pos):
        self._pos = pos
        self.jogs = []

    @property
    def position(self):
        return self._pos

    def jog(self, dx, dy):
        self.jogs.append((dx, dy))
        self._pos = (self._pos[0] + dx, self._pos[1] + dy)
        return True


def test_does_not_move_before_idle_threshold():
    d = DriftCorrector(bed_center_mm=(0.0, 0.0), idle_frames=3, step_mm=1.0)
    p = FakeP((5.0, 0.0))
    assert d.tick(p) is False     # frame 1
    assert d.tick(p) is False     # frame 2
    assert p.jogs == []


def test_moves_toward_center_after_idle():
    d = DriftCorrector(bed_center_mm=(0.0, 0.0), idle_frames=2, step_mm=1.0)
    p = FakeP((5.0, -3.0))
    d.tick(p)                     # 1
    moved = d.tick(p)            # 2 -> threshold reached
    assert moved is True
    dx, dy = p.jogs[-1]
    assert dx < 0 and dy > 0      # toward center from (+5,-3)


def test_on_target_frame_resets_idle():
    d = DriftCorrector(bed_center_mm=(0.0, 0.0), idle_frames=2, step_mm=1.0)
    p = FakeP((5.0, 0.0))
    d.tick(p)
    d.on_target_frame()
    assert d.tick(p) is False     # counter was reset


def test_does_not_overshoot_center():
    d = DriftCorrector(bed_center_mm=(0.0, 0.0), idle_frames=1, step_mm=10.0)
    p = FakeP((3.0, 0.0))
    d.tick(p)
    assert abs(p.position[0]) <= 3.0   # never crosses past center
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_drift.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimplotter.drift'`

- [ ] **Step 3: Write `aimplotter/drift.py`**

```python
class DriftCorrector:
    def __init__(self, bed_center_mm, idle_frames, step_mm):
        self.center = bed_center_mm
        self.idle_frames = idle_frames
        self.step_mm = step_mm
        self._idle = 0

    def on_target_frame(self) -> None:
        self._idle = 0

    def _toward_center(self, pos_axis, center_axis) -> float:
        delta = center_axis - pos_axis
        if abs(delta) <= self.step_mm:
            return delta               # land exactly, no overshoot
        return self.step_mm if delta > 0 else -self.step_mm

    def tick(self, plotter) -> bool:
        self._idle += 1
        if self._idle < self.idle_frames:
            return False
        x, y = plotter.position
        dx = self._toward_center(x, self.center[0])
        dy = self._toward_center(y, self.center[1])
        if dx == 0.0 and dy == 0.0:
            return False
        plotter.jog(dx, dy)
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_drift.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add aimplotter/drift.py tests/test_drift.py
git commit -m "feat: drift corrector reclaims travel during dead time"
```

---

### Task 7: Screen capture

**Files:**
- Create: `aimplotter/capture.py`

**Interfaces:**
- Produces: `ScreenCapture(region)` with `grab() -> numpy.uint8 BGR HxWx3` and `close()`.
- Consumes: `Config.screen_region` (Task 1).

No unit test (thin wrapper over `mss` + OS screen; covered indirectly by the integration test's injected frame source). Verify manually in Step 2.

- [ ] **Step 1: Write `aimplotter/capture.py`**

```python
import numpy as np
import mss


class ScreenCapture:
    def __init__(self, region):
        self.region = region
        self._sct = mss.mss()

    def grab(self):
        shot = self._sct.grab(self.region)
        frame = np.array(shot)              # BGRA
        return frame[:, :, :3]             # drop alpha -> BGR

    def close(self) -> None:
        self._sct.close()
```

- [ ] **Step 2: Manual smoke check**

Run:
```bash
python -c "from aimplotter.capture import ScreenCapture; from aimplotter.config import Config; c=ScreenCapture(Config().screen_region); f=c.grab(); print(f.shape, f.dtype); c.close()"
```
Expected: prints `(1080, 1920, 3) uint8` (or your actual resolution).

- [ ] **Step 3: Commit**

```bash
git add aimplotter/capture.py
git commit -m "feat: mss screen capture"
```

---

### Task 8: Main loop, kill-switch, dry-run, and integration test

**Files:**
- Create: `aimplotter/main.py`
- Test: `tests/test_integration.py`

**Interfaces:**
- Consumes: every module above.
- Produces: `run_loop(frame_source, plotter, controller, drift, config, should_stop)` — one testable function driving the loop; returns a list of action strings (`"jog"`, `"click"`, `"drift"`, `"idle"`) for assertion. `frame_source()` returns a BGR frame or `None` to end. `should_stop()` returns bool (kill-switch).
- Produces: `main(argv)` CLI entry: parses `--no-serial` (dry-run prints G-code), opens serial/capture, installs `pynput` kill-key listener, calls `run_loop`.

- [ ] **Step 1: Write the failing integration test**

`tests/test_integration.py`:
```python
import numpy as np
import cv2
from aimplotter.main import run_loop
from aimplotter.controller import PDController
from aimplotter.drift import DriftCorrector
from aimplotter.config import Config


class FakeP:
    def __init__(self):
        self._pos = (0.0, 0.0)
        self.clicks = 0
        self.jogs = 0

    @property
    def position(self):
        return self._pos

    def jog(self, dx, dy):
        self._pos = (self._pos[0] + dx, self._pos[1] + dy)
        self.jogs += 1
        return True

    def click(self):
        self.clicks += 1


def _frame(cx, cy, r=25):
    f = np.zeros((1080, 1920, 3), dtype=np.uint8)
    if cx is not None:
        cv2.circle(f, (cx, cy), r, (255, 80, 0), -1)
    return f


def test_loop_jogs_then_clicks_then_drifts():
    C = Config()
    # frame 1: ball far from center -> jog; frame 2: ball ON center -> click;
    # frames 3-... : no ball -> drift after idle threshold
    frames = [_frame(1200, 700), _frame(960, 540)]
    frames += [_frame(None, None)] * (C.drift_idle_frames + 1)
    it = iter(frames)

    def source():
        return next(it, None)

    p = FakeP()
    ctrl = PDController(C.gain, C.kp, C.ki, C.kd, C.max_move_mm)
    drift = DriftCorrector(C.bed_center_mm, C.drift_idle_frames, C.drift_step_mm)

    actions = run_loop(source, p, ctrl, drift, C, should_stop=lambda: False)

    assert "jog" in actions
    assert "click" in actions
    assert "drift" in actions
    assert p.clicks >= 1


def test_loop_stops_on_kill_switch():
    C = Config()
    p = FakeP()
    ctrl = PDController(C.gain, C.kp, C.ki, C.kd, C.max_move_mm)
    drift = DriftCorrector(C.bed_center_mm, C.drift_idle_frames, C.drift_step_mm)
    actions = run_loop(lambda: _frame(1200, 700), p, ctrl, drift, C,
                       should_stop=lambda: True)
    assert actions == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_integration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'aimplotter.main'`

- [ ] **Step 3: Write `aimplotter/main.py`**

```python
import argparse
import time

from aimplotter.config import Config
from aimplotter.detector import detect_blue
from aimplotter.targeting import nearest_to_center, error_vector
from aimplotter.controller import PDController, on_target
from aimplotter.drift import DriftCorrector


def run_loop(frame_source, plotter, controller, drift, config,
             should_stop) -> list[str]:
    """Drive one detect->aim->click loop. Returns action log for testing."""
    actions: list[str] = []
    while not should_stop():
        frame = frame_source()
        if frame is None:
            break
        balls = detect_blue(frame, config.hsv_lower, config.hsv_upper,
                            config.min_area_px)
        target = nearest_to_center(balls, config.screen_center)
        if target is None:
            if drift.tick(plotter):
                actions.append("drift")
            else:
                actions.append("idle")
            continue

        drift.on_target_frame()
        err = error_vector(target, config.screen_center)
        if on_target(err, target.r, config.hitbox_tol_px):
            plotter.click()
            controller.reset()
            actions.append("click")
        else:
            dx, dy = controller.step(err)
            plotter.jog(dx, dy)
            actions.append("jog")
    return actions


class _PrintPlotter:
    """Dry-run plotter: prints G-code instead of sending serial."""
    def __init__(self):
        self._pos = (0.0, 0.0)

    @property
    def position(self):
        return self._pos

    def jog(self, dx, dy):
        self._pos = (self._pos[0] + dx, self._pos[1] + dy)
        print(f"[dry-run] $J=G91 X{dx:.3f} Y{dy:.3f}")
        return True

    def click(self):
        print("[dry-run] CLICK")

    def feed_hold(self):
        print("[dry-run] FEED HOLD")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Optical aim plotter")
    parser.add_argument("--no-serial", action="store_true",
                        help="dry-run: print G-code instead of sending")
    args = parser.parse_args(argv)

    config = Config()
    controller = PDController(config.gain, config.kp, config.ki, config.kd,
                             config.max_move_mm)
    drift = DriftCorrector(config.bed_center_mm, config.drift_idle_frames,
                          config.drift_step_mm)

    # --- kill switch ---
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

    # --- capture ---
    from aimplotter.capture import ScreenCapture
    cap = ScreenCapture(config.screen_region)

    # --- plotter ---
    if args.no_serial:
        plotter = _PrintPlotter()
    else:
        import serial
        from aimplotter.plotter import GRBLPlotter
        ser = serial.Serial(config.port, config.baud, timeout=2)
        time.sleep(2)  # let GRBL boot
        plotter = GRBLPlotter(ser, config.soft_limit_mm, config.bed_center_mm,
                             config.press_cmd, config.release_cmd,
                             config.click_dwell_s)

    try:
        run_loop(cap.grab, plotter, controller, drift, config,
                 should_stop=lambda: stop_flag["stop"])
    finally:
        try:
            plotter.feed_hold()
        except Exception:
            pass
        cap.close()
        listener.stop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_integration.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -v`
Expected: all tests pass (detector, targeting, controller, plotter, drift, integration).

- [ ] **Step 6: Commit**

```bash
git add aimplotter/main.py tests/test_integration.py
git commit -m "feat: main loop, kill-switch, dry-run, integration test"
```

---

### Task 9: Calibration script

**Files:**
- Create: `aimplotter/calibrate.py`

**Interfaces:**
- Consumes: `ScreenCapture`, `GRBLPlotter`, `detect_blue`, `Config`.
- Produces: `measure_gain(capture, plotter, config, move_mm) -> float` — detect a ball, jog the plotter a known `move_mm` in X, re-detect, compute `gain = move_mm / pixels_moved`, print suggested `gain` for `config.py`.

No unit test (hardware + live screen interactive tool). Logic is a thin arithmetic wrapper; verified manually against the printed value.

- [ ] **Step 1: Write `aimplotter/calibrate.py`**

```python
import math
import time

from aimplotter.detector import detect_blue
from aimplotter.targeting import nearest_to_center


def measure_gain(capture, plotter, config, move_mm=5.0) -> float:
    """Jog a known distance, measure view shift in px, return mm-per-px."""
    f0 = capture.grab()
    b0 = nearest_to_center(
        detect_blue(f0, config.hsv_lower, config.hsv_upper, config.min_area_px),
        config.screen_center,
    )
    if b0 is None:
        raise RuntimeError("No ball visible — point at a target before calibrating.")

    plotter.jog(move_mm, 0.0)
    time.sleep(0.3)

    f1 = capture.grab()
    b1 = nearest_to_center(
        detect_blue(f1, config.hsv_lower, config.hsv_upper, config.min_area_px),
        config.screen_center,
    )
    if b1 is None:
        raise RuntimeError("Lost the ball after move — reduce move_mm.")

    px = math.hypot(b1.cx - b0.cx, b1.cy - b0.cy)
    if px < 1:
        raise RuntimeError("No measurable view shift — increase move_mm.")
    gain = move_mm / px
    print(f"Moved {move_mm} mm -> {px:.1f} px shift. "
          f"Suggested config.gain = {gain:.5f}")
    return gain


def main() -> None:
    import time as _t
    import serial
    from aimplotter.config import Config
    from aimplotter.capture import ScreenCapture
    from aimplotter.plotter import GRBLPlotter

    config = Config()
    cap = ScreenCapture(config.screen_region)
    ser = serial.Serial(config.port, config.baud, timeout=2)
    _t.sleep(2)
    plotter = GRBLPlotter(ser, config.soft_limit_mm, config.bed_center_mm,
                         config.press_cmd, config.release_cmd,
                         config.click_dwell_s)
    try:
        measure_gain(cap, plotter, config)
    finally:
        cap.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add aimplotter/calibrate.py
git commit -m "feat: interactive gain calibration script"
```

---

## Self-Review

**Spec coverage** (spec §1–§9 → tasks):
- §1 summary / §2 control model → Tasks 4, 8 (PD controller + loop). ✅
- §2 GAIN / calibration → Task 9. ✅
- §3 drift corrector → Task 6. ✅
- §4 components → every module mapped to a task (capture T7, detector T2, targeting T3, controller T4, plotter T5, drift T6, calibrate T9, config T1, main T8). ✅
- §5 safety / kill-switch / dry-run → Task 8 (`should_stop`, `feed_hold` in finally, `--no-serial`, `_PrintPlotter`). ✅
- §6 known constraint (soft limits) → Task 5 (`_clamp`, `jog` returns False). ✅
- §7 testing → tests in Tasks 2–6, 8. ✅
- §8 stack → `requirements.txt` Task 1. ✅
- §9 hardware assumptions / configurable click → Task 1 config + Task 5 `press_cmd`/`release_cmd`. ✅

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✅

**Type consistency:** `Ball(cx,cy,r)`/`.center` consistent across T1–T8; `detect_blue(frame, hsv_lower, hsv_upper, min_area)` signature identical in T2 usage and T8 call; `PDController(gain,kp,ki,kd,max_move_mm)` + `.step()`/`.reset()` consistent T4/T8; `GRBLPlotter` ctor args match T5 def and T8/T9 calls; `DriftCorrector(bed_center_mm,idle_frames,step_mm)` + `.tick()`/`.on_target_frame()` consistent T6/T8; `run_loop(frame_source, plotter, controller, drift, config, should_stop)` consistent T8 def/tests. ✅
