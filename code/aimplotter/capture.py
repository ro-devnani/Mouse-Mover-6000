import numpy as np
import mss


class ScreenCapture:
    """mss screen grabber, returns BGR frames."""
    def __init__(self, region):
        self.region = region
        self._sct = mss.mss()

    def grab(self):
        shot = self._sct.grab(self.region)
        frame = np.array(shot)              # BGRA
        return frame[:, :, :3]             # drop alpha to BGR

    def close(self) -> None:
        self._sct.close()


class DxCamCapture:
    """DirectX duplication grabber, faster than mss."""
    def __init__(self, region):
        import dxcam
        self._cam = dxcam.create(output_color="BGR")
        left = region.get("left", 0)
        top = region.get("top", 0)
        self._region = (left, top, left + region["width"],
                        top + region["height"])
        # Prime the first frame
        self._last = None
        for _ in range(20):
            f = self._cam.grab(region=self._region)
            if f is not None:
                self._last = f
                break

    def grab(self):
        # grab returns None when no new frame
        f = self._cam.grab(region=self._region)
        if f is None:
            return self._last
        self._last = f
        return f

    def close(self) -> None:
        try:
            self._cam.release()
        except Exception:
            pass


def _dxcam_available() -> bool:
    try:
        import dxcam  # noqa: F401
        return True
    except Exception:
        return False


def _choose_backend(backend, dxcam_available) -> str:
    """Pick capture backend, raise if dxcam forced but missing."""
    if backend == "mss":
        return "mss"
    if backend == "dxcam":
        if not dxcam_available:
            raise RuntimeError("dxcam requested but not installed")
        return "dxcam"
    return "dxcam" if dxcam_available else "mss"


def make_capture(config):
    """Build a capture backend from config, fall back to mss."""
    backend = getattr(config, "capture_backend", "auto")
    choice = _choose_backend(backend, _dxcam_available())
    if choice == "dxcam":
        try:
            return DxCamCapture(config.screen_region)
        except Exception as e:
            if backend == "dxcam":
                raise
            print(f"dxcam init failed, using mss: {e}")
            return ScreenCapture(config.screen_region)
    return ScreenCapture(config.screen_region)
