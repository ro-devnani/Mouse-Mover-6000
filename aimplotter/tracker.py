"""Frame-to-frame ball tracking with stable IDs.

Greedy nearest matching, no extra deps.
Keeps lost tracks alive for a grace period.
Lets the loop lock one target instead of
re-picking nearest every frame.
"""
import math
from dataclasses import dataclass

from aimplotter.models import Ball


@dataclass
class Track:
    id: int
    ball: Ball
    misses: int = 0


class Tracker:
    def __init__(self, max_match_dist, max_misses):
        self.max_match_dist = max_match_dist
        self.max_misses = max_misses
        self._tracks = []
        self._next_id = 0

    @property
    def tracks(self):
        return list(self._tracks)

    def _new_track(self, ball) -> Track:
        t = Track(id=self._next_id, ball=ball)
        self._next_id += 1
        return t

    def update(self, balls) -> list:
        """Match detections to tracks, return active tracks."""
        # Candidate pairs within the gate
        pairs = []
        for ti, tr in enumerate(self._tracks):
            for di, b in enumerate(balls):
                d = math.hypot(tr.ball.cx - b.cx, tr.ball.cy - b.cy)
                if d <= self.max_match_dist:
                    pairs.append((d, ti, di))
        pairs.sort(key=lambda p: p[0])

        matched_t, matched_d = set(), set()
        for d, ti, di in pairs:
            if ti in matched_t or di in matched_d:
                continue
            matched_t.add(ti)
            matched_d.add(di)
            self._tracks[ti].ball = balls[di]
            self._tracks[ti].misses = 0

        survivors = []
        for ti, tr in enumerate(self._tracks):
            if ti not in matched_t:
                tr.misses += 1
            if tr.misses <= self.max_misses:
                survivors.append(tr)

        for di, b in enumerate(balls):
            if di not in matched_d:
                survivors.append(self._new_track(b))

        self._tracks = survivors
        return self.tracks


def select_locked(tracks, point, locked_id):
    """Hold lock if seen now, else nearest visible."""
    for t in tracks:
        if t.id == locked_id and t.misses == 0:
            return t
    visible = [t for t in tracks if t.misses == 0]
    if not visible:
        return None
    return min(
        visible,
        key=lambda t: math.hypot(t.ball.cx - point[0], t.ball.cy - point[1]),
    )
