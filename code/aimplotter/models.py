from dataclasses import dataclass


@dataclass
class Ball:
    cx: float
    cy: float
    r: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.cx, self.cy)
