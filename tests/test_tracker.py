from aimplotter.tracker import Tracker, select_locked
from aimplotter.models import Ball


def _tracker():
    return Tracker(max_match_dist=80.0, max_misses=3)


def test_new_detection_gets_id():
    t = _tracker()
    tracks = t.update([Ball(100, 100, 10)])
    assert len(tracks) == 1
    assert tracks[0].id == 0


def test_same_ball_keeps_id_across_frames():
    t = _tracker()
    t.update([Ball(100, 100, 10)])
    tracks = t.update([Ball(110, 105, 10)])  # small move, within gate
    assert len(tracks) == 1
    assert tracks[0].id == 0
    assert tracks[0].ball.cx == 110


def test_far_jump_gets_new_id():
    t = _tracker()
    t.update([Ball(100, 100, 10)])
    tracks = t.update([Ball(900, 900, 10)])  # beyond gate
    ids = sorted(tr.id for tr in tracks)
    # old track coasts (miss=1), new detection gets id 1
    assert 1 in ids


def test_lost_track_coasts_then_drops():
    t = _tracker()
    t.update([Ball(100, 100, 10)])
    for _ in range(3):
        t.update([])              # misses 1,2,3 -> still alive
    assert len(t.tracks) == 1
    t.update([])                  # miss 4 -> dropped
    assert t.tracks == []


def test_two_balls_keep_distinct_ids():
    t = _tracker()
    t.update([Ball(100, 100, 10), Ball(500, 500, 10)])
    tracks = t.update([Ball(105, 100, 10), Ball(505, 500, 10)])
    ids = sorted(tr.id for tr in tracks)
    assert ids == [0, 1]


def test_select_locked_keeps_lock_while_active():
    t = _tracker()
    tracks = t.update([Ball(100, 100, 10), Ball(120, 100, 10)])
    locked = tracks[0].id
    # ball 1 is nearer to point but lock must hold on ball 0
    sel = select_locked(t.update([Ball(101, 100, 10), Ball(120, 100, 10)]),
                        (120, 100), locked)
    assert sel.id == locked


def test_select_locked_reacquires_when_gone():
    t = _tracker()
    t.update([Ball(100, 100, 10)])
    # lock id 5 does not exist -> pick nearest visible
    sel = select_locked(t.tracks, (100, 100), 5)
    assert sel.id == 0


def test_select_locked_none_when_empty():
    assert select_locked([], (0, 0), None) is None


def test_select_locked_releases_coasting_track():
    t = _tracker()
    t.update([Ball(100, 100, 10)])      # id 0
    # id 0 missed this frame (coasts), a visible ball appears far away
    tracks = t.update([Ball(900, 900, 10)])  # id 1 visible, id 0 coasting
    sel = select_locked(tracks, (900, 900), 0)
    assert sel.id == 1                  # does not aim at coasting ghost
