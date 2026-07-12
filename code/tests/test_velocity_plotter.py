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
