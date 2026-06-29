import pytest
from aimplotter.capture import _choose_backend


def test_mss_forced():
    assert _choose_backend("mss", True) == "mss"
    assert _choose_backend("mss", False) == "mss"


def test_auto_prefers_dxcam_when_available():
    assert _choose_backend("auto", True) == "dxcam"


def test_auto_falls_back_to_mss():
    assert _choose_backend("auto", False) == "mss"


def test_dxcam_forced_available():
    assert _choose_backend("dxcam", True) == "dxcam"


def test_dxcam_forced_missing_raises():
    with pytest.raises(RuntimeError):
        _choose_backend("dxcam", False)
