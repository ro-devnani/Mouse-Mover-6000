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
