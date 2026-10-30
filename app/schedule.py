"""Scheduled departures for the configured rows, from TransLink's static GTFS."""

import csv
import datetime as dt
import io
import json
import shutil
import time
import urllib.request
import zipfile
from zoneinfo import ZoneInfo

CACHE_VERSION = 1


def _route_name(short_name):
    return short_name.lstrip("0") or short_name


def _gtfs_seconds(hms):
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def rows_key(rows):
    return [[r.route, r.stop_code, r.headsign] for r in rows]


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=300) as resp, open(part, "wb") as f:
        shutil.copyfileobj(resp, f)
    part.replace(dest)


def _table(z, name):
    f = io.TextIOWrapper(z.open(name), "utf-8-sig", newline="")
    reader = csv.reader(f)
    header = {h: i for i, h in enumerate(next(reader))}
    return header, reader


def build(zip_path, rows):
    """Extracts only what the configured rows need from the GTFS zip."""
    z = zipfile.ZipFile(zip_path)

    h, r = _table(z, "feed_info.txt")
    info = next(r)
    feed_version, feed_end = info[h["feed_version"]], info[h["feed_end_date"]]

    codes = {row.stop_code for row in rows}
    stop_ids = {}  # stop_id -> stop_code
    h, r = _table(z, "stops.txt")
    for rec in r:
        if rec[h["stop_code"]] in codes:
            stop_ids[rec[h["stop_id"]]] = rec[h["stop_code"]]

    names = {row.route for row in rows}
    route_ids = {}  # route_id -> route number
    h, r = _table(z, "routes.txt")
    for rec in r:
        name = _route_name(rec[h["route_short_name"]])
        if name in names:
            route_ids[rec[h["route_id"]]] = name

    trips = {}  # trip_id -> (route number, headsign, service_id)
    h, r = _table(z, "trips.txt")
    for rec in r:
        route = route_ids.get(rec[h["route_id"]])
        if route:
            trips[rec[h["trip_id"]]] = (route, rec[h["trip_headsign"]], rec[h["service_id"]])

    out_rows = [[] for _ in rows]
    used_services = set()
    h, r = _table(z, "stop_times.txt")
    i_trip, i_stop, i_dep, i_seq = h["trip_id"], h["stop_id"], h["departure_time"], h["stop_sequence"]
    for rec in r:
        code = stop_ids.get(rec[i_stop])
        if code is None:
            continue
        trip = trips.get(rec[i_trip])
        if trip is None:
            continue
        route, headsign, service = trip
        for idx, row in enumerate(rows):
            if row.stop_code == code and row.route == route and row.headsign in headsign:
                out_rows[idx].append(
                    [rec[i_trip], service, _gtfs_seconds(rec[i_dep]), int(rec[i_seq]), rec[i_stop]]
                )
                used_services.add(service)

    services = {}
    h, r = _table(z, "calendar.txt")
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for rec in r:
        sid = rec[h["service_id"]]
        if sid in used_services:
            services[sid] = [rec[h["start_date"]], rec[h["end_date"]]] + [rec[h[d]] == "1" for d in days]

    exceptions = {}
    h, r = _table(z, "calendar_dates.txt")
    for rec in r:
        sid = rec[h["service_id"]]
        if sid in used_services:
            exceptions.setdefault(sid, {})[rec[h["date"]]] = int(rec[h["exception_type"]])

    for trips_at_stop in out_rows:
        trips_at_stop.sort(key=lambda t: t[2])

    return {
        "version": CACHE_VERSION,
        "rows_key": rows_key(rows),
        "feed_version": feed_version,
        "feed_end": feed_end,
        "built_at": time.time(),
        "services": services,
        "exceptions": exceptions,
        "rows": out_rows,
    }


class Schedule:
    def __init__(self, data, tz):
        self.data = data
        self.tz = ZoneInfo(tz)

    @classmethod
    def load(cls, path, rows, tz):
        """Returns the cached schedule, or None if missing or built for other rows."""
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            return None
        if data.get("version") != CACHE_VERSION or data.get("rows_key") != rows_key(rows):
            return None
        return cls(data, tz)

    def save(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(self.data))
        tmp.replace(path)

    def is_stale(self, now, max_age_s):
        today = dt.datetime.fromtimestamp(now, self.tz).strftime("%Y%m%d")
        return now - self.data["built_at"] > max_age_s or self.data["feed_end"] < today

    def _runs_on(self, service_id, date_str, weekday):
        exception = self.data["exceptions"].get(service_id, {}).get(date_str)
        if exception is not None:
            return exception == 1
        cal = self.data["services"].get(service_id)
        return bool(cal) and cal[0] <= date_str <= cal[1] and cal[2 + weekday]

    def _service_day_start(self, day):
        # GTFS times count from noon minus 12h, which differs from midnight on DST days.
        noon = dt.datetime.combine(day, dt.time(12), self.tz)
        return noon.timestamp() - 12 * 3600

    def departures(self, row_index, now, before_s=90 * 60, after_s=4 * 3600):
        """Scheduled stops for one row near `now`.

        Yields (scheduled_ts, trip_id, stop_id, stop_sequence, service_date).
        """
        today = dt.datetime.fromtimestamp(now, self.tz).date()
        lo, hi = now - before_s, now + after_s
        for day in (today - dt.timedelta(days=1), today):
            date_str = day.strftime("%Y%m%d")
            base = self._service_day_start(day)
            for trip_id, service, secs, seq, stop_id in self.data["rows"][row_index]:
                ts = base + secs
                if lo <= ts <= hi and self._runs_on(service, date_str, day.weekday()):
                    yield ts, trip_id, stop_id, seq, date_str
