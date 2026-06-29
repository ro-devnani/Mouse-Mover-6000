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
