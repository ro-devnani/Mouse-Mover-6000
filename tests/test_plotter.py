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
