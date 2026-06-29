# overlay_debug (THROWAWAY DEV TOOL)

> ⚠️ **Delete this entire folder before final deployment.** It is a debugging
> visualization only. It imports from `aimplotter/` (read-only) and modifies
> **no** main files, so removing this folder leaves the project intact.

## What it shows

A live OpenCV window of the captured screen with the planned cursor path drawn
on top:

- **Crosshair** marked at screen center (where the in-game cursor sits).
- A line from the **crosshair → closest target** (the ball the cursor moves to
  first).
- A line from the **closest target → next target** (where the cursor goes
  after that).
- Each ball circled; closest/next labeled.

This is purely visual. It sends nothing to the plotter and does not move the
cursor.

## Run

From the `mm6000/` project root:

```bash
python overlay_debug/overlay.py
```

Press `q` (with the window focused) to quit.
