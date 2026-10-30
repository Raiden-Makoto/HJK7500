import datetime as dt
import sys
import time
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

import departures
import gtfs_rt
import motion
import power
from config import Row
from schedule import Schedule


def _varint(n):
    if n < 0:
        n += 1 << 64
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _field(num, value):
    if isinstance(value, int):
        return _varint(num << 3) + _varint(value)
    if isinstance(value, str):
        value = value.encode()
    return _varint(num << 3 | 2) + _varint(len(value)) + value


def _msg(*fields):
    return b"".join(_field(n, v) for n, v in fields if v is not None)


def _stop(seq=None, stop_id=None, dep_delay=None, dep_time=None, rel=None):
    dep = _msg((1, dep_delay), (2, dep_time)) if dep_delay is not None or dep_time is not None else None
    return _msg((1, seq), (3, dep), (4, stop_id), (5, rel))


def _feed(*trips):
    entities = []
    for i, (trip_id, start_date, rel, stops) in enumerate(trips):
        descriptor = _msg((1, trip_id), (3, start_date), (4, rel))
        tu = _msg((1, descriptor), *[(2, s) for s in stops])
        entities.append((2, _msg((1, str(i)), (3, tu))))
    return _msg((1, _msg((1, "2.0"), (3, 1700000000))), *entities)


class DecoderTest(unittest.TestCase):
    def test_parses_delays_cancellations_and_negative_values(self):
        buf = _feed(
            ("A", "20261029", None, [_stop(seq=5, dep_delay=120), _stop(seq=9, dep_delay=-60)]),
            ("B", None, gtfs_rt.TRIP_CANCELED, []),
            ("C", None, None, [_stop(seq=1, dep_time=1700000500)]),
        )
        updates = gtfs_rt.parse(buf)
        a = updates[("A", "20261029")]
        self.assertEqual([(s.seq, s.dep_delay) for s in a.stops], [(5, 120), (9, -60)])
        self.assertTrue(updates[("B", None)].canceled)
        self.assertEqual(updates[("C", None)].stops[0].dep_time, 1700000500)

    def test_skips_unrequested_trips(self):
        buf = _feed(("A", None, None, []), ("B", None, None, []))
        self.assertEqual(set(gtfs_rt.parse(buf, {"B"})), {("B", None)})


class PredictTest(unittest.TestCase):
    def update(self, *stops, canceled=False, delay=None):
        return gtfs_rt.TripUpdate("T", canceled=canceled, delay=delay, stops=list(stops))

    def test_no_update_uses_schedule(self):
        self.assertEqual(departures.predict(1000, "S", 7, None), 1000)

    def test_canceled_trip_is_dropped(self):
        self.assertIsNone(departures.predict(1000, "S", 7, self.update(canceled=True)))

    def test_exact_stop_time_wins(self):
        u = self.update(gtfs_rt.StopUpdate(seq=7, dep_time=1300))
        self.assertEqual(departures.predict(1000, "S", 7, u), 1300)

    def test_upstream_delay_propagates(self):
        u = self.update(gtfs_rt.StopUpdate(seq=3, dep_delay=240), gtfs_rt.StopUpdate(seq=12, dep_delay=0))
        self.assertEqual(departures.predict(1000, "S", 7, u), 1240)

    def test_skipped_stop_is_dropped(self):
        u = self.update(gtfs_rt.StopUpdate(seq=7, relationship=gtfs_rt.STOP_SKIPPED))
        self.assertIsNone(departures.predict(1000, "S", 7, u))

    def test_only_later_updates_means_schedule(self):
        u = self.update(gtfs_rt.StopUpdate(seq=9, dep_delay=300))
        self.assertEqual(departures.predict(1000, "S", 7, u), 1000)


class UpcomingTest(unittest.TestCase):
    tz = "America/Vancouver"

    def schedule(self, rows_data):
        data = {
            "feed_end": "20991231",
            "built_at": 0,
            "services": {"WK": ["20200101", "20991231"] + [True] * 7},
            "exceptions": {},
            "rows": rows_data,
        }
        return Schedule(data, self.tz)

    def at(self, hh, mm):
        return dt.datetime(2026, 10, 29, hh, mm, tzinfo=ZoneInfo(self.tz)).timestamp()

    def test_walk_time_hides_too_soon_departures(self):
        # Departures at 10:05, 10:13, 10:20, 10:40; now 10:03 with a 10 minute walk.
        secs = [10 * 3600 + m * 60 for m in (5, 13, 20, 40)]
        s = self.schedule([[[f"t{i}", "WK", x, 4, "S"] for i, x in enumerate(secs)]])
        rows = [Row("R4", "Joyce", "60349", walk_min=10)]
        now = self.at(10, 3)
        times = departures.upcoming(s, {}, rows, now, 2)[0]
        self.assertEqual(departures.format_times(times, now), "10, 17 min")

    def test_after_midnight_trips_from_previous_service_day(self):
        # 25:10 on Oct 28's service day is 01:10 on Oct 29.
        s = self.schedule([[["late", "WK", 25 * 3600 + 600, 1, "S"]]])
        now = self.at(1, 0)
        times = departures.upcoming(s, {}, [Row("15", "Marine", "50987")], now, 2)[0]
        self.assertEqual(departures.format_times(times, now), "10 min")

    def test_format(self):
        self.assertEqual(departures.format_times([], 0), "--")
        self.assertEqual(departures.format_times([30, 16 * 60 + 5], 0), "now, 16 min")


class ScreenWantedTest(unittest.TestCase):
    hours, wake = (8, 21), 300

    def at(self, hh, mm):
        return time.mktime((2026, 10, 30, hh, mm, 0, 0, 0, -1))

    def wanted(self, now, last_motion, camera_ok=True, clock_ok=True):
        return power.screen_wanted(now, last_motion, camera_ok, self.hours, self.wake, clock_ok)

    def test_motion_wakes_for_five_minutes(self):
        moved = self.at(12, 0)
        self.assertTrue(self.wanted(moved + 299, moved))
        self.assertFalse(self.wanted(moved + 301, moved))

    def test_dark_without_motion(self):
        self.assertFalse(self.wanted(self.at(12, 0), 0))

    def test_night_ignores_motion(self):
        for hh in (21, 23, 3, 7):
            now = self.at(hh, 30)
            self.assertFalse(self.wanted(now, now))

    def test_no_camera_stays_lit_by_day_only(self):
        self.assertTrue(self.wanted(self.at(8, 0), 0, camera_ok=False))
        self.assertFalse(self.wanted(self.at(22, 0), 0, camera_ok=False))

    def test_unset_clock_stays_lit(self):
        self.assertTrue(self.wanted(self.at(3, 0), 0, clock_ok=False))


class MotionDetectorTest(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(0)
        self.room = self.rng.integers(60, 120, (120, 160), dtype=np.uint8)
        self.d = motion.MotionDetector(pixel_delta=25, fraction=0.04)
        for _ in range(motion.WARMUP_FRAMES):
            self.d.feed(self.noisy(self.room))

    def noisy(self, frame):
        noise = self.rng.integers(-8, 9, frame.shape)
        return np.clip(frame.astype(int) + noise, 0, 255).astype(np.uint8)

    def test_still_room_is_not_motion(self):
        self.assertFalse(any(self.d.feed(self.noisy(self.room)) for _ in range(50)))

    def test_hand_needs_two_frames(self):
        hand = self.room.copy()
        hand[30:90, 50:90] = 230   # ~12% of the picture
        self.assertFalse(self.d.feed(self.noisy(hand)))
        self.assertTrue(self.d.feed(self.noisy(hand)))

    def test_small_change_is_ignored(self):
        speck = self.room.copy()
        speck[10:20, 10:20] = 230  # ~0.5% of the picture
        self.assertFalse(any(self.d.feed(self.noisy(speck)) for _ in range(5)))

    def test_moved_object_fades_into_background(self):
        moved = self.room.copy()
        moved[30:90, 50:90] = 230
        results = [self.d.feed(self.noisy(moved)) for _ in range(120)]
        self.assertTrue(results[1])
        self.assertFalse(any(results[-10:]))


if __name__ == "__main__":
    unittest.main()
