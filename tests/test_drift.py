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
