# Archived: stop-start driver (reference only)

The original **position-based, move-and-settle** aim driver. Superseded by the
velocity-streaming system in `code/` (`aimplotter/velocity_*.py` +
`firmware/mm6000_velocity/`). Kept here for reference; **not** on the active
import path and not exercised by the test suite.

## What's here
- `firmware/mm6000/mm6000.ino` — Arduino firmware, blocking `J <dx> <dy> <feed>`
  jog protocol (accel/decel to a stop every move) + `S <angle>` servo + `!` abort.
- `plotter.py` — `StepperPlotter`, sends `J`/`S` and waits for `ok` each move.
- `main.py` — `run_loop`: detect → PD position step → jog → settle → repeat.
- `calibrate.py` — measures `gain` (mm/px) by jogging a known distance.
- `tests/` — the tests that covered the above.

## Why it was replaced
Every frame decelerated the steppers to zero, blocked on the serial ack, then
slept to let the view render — visibly choppy. The velocity system streams a
per-axis speed setpoint so the steppers glide continuously between frames.

## Running it again
Imports reference `aimplotter.*` (e.g. `from aimplotter.plotter import StepperPlotter`).
To run from this folder those imports must be repointed, or the files copied back
under `code/aimplotter/`. `calibrate.py` still works against this firmware and is
the way to measure `gain` (the velocity firmware only speaks `V`/`S`/`!`).
