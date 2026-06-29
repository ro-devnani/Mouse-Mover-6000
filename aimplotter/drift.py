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
