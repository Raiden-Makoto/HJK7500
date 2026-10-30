"""Combines the schedule with real-time updates into what each row shows."""

from gtfs_rt import STOP_NO_DATA, STOP_SKIPPED


def predict(scheduled_ts, stop_id, stop_seq, update):
    """Predicted departure time at this stop, or None if the bus won't stop."""
    if update is None:
        return scheduled_ts
    if update.canceled:
        return None

    prior = None
    for s in update.stops:
        here = s.seq == stop_seq if s.seq is not None else s.stop_id == stop_id
        if here:
            if s.relationship == STOP_SKIPPED:
                return None
            if s.relationship == STOP_NO_DATA:
                return scheduled_ts
            for when, delay in ((s.dep_time, s.dep_delay), (s.arr_time, s.arr_delay)):
                if when:
                    return when
                if delay is not None:
                    return scheduled_ts + delay
            break
        if s.seq is not None and s.seq < stop_seq:
            prior = s

    # Per GTFS-RT, an upstream stop's delay carries forward to later stops.
    if prior is not None:
        if prior.relationship == STOP_NO_DATA:
            return scheduled_ts
        delay = prior.dep_delay if prior.dep_delay is not None else prior.arr_delay
        if delay is not None:
            return scheduled_ts + delay
    if update.delay is not None:
        return scheduled_ts + update.delay
    return scheduled_ts


def wanted_trip_ids(schedule, rows, now):
    return {
        trip_id
        for i in range(len(rows))
        for _, trip_id, _, _, _ in schedule.departures(i, now)
    }


def upcoming(schedule, updates, rows, now, per_row):
    """For each row, the next `per_row` departure timestamps after its walk time."""
    result = []
    for i, row in enumerate(rows):
        earliest = now + row.walk_min * 60
        times = []
        for sched_ts, trip_id, stop_id, seq, service_date in schedule.departures(i, now):
            update = updates.get((trip_id, service_date)) or updates.get((trip_id, None))
            ts = predict(sched_ts, stop_id, seq, update)
            if ts is not None and ts >= earliest:
                times.append(ts)
        result.append(sorted(times)[:per_row])
    return result


def format_times(times, now):
    """'now, 16 min', '3, 19 min', '7 min', or '--'."""
    if not times:
        return "--"
    mins = [int((t - now) // 60) for t in times]
    parts = ["now" if m <= 0 else str(m) for m in mins]
    return ", ".join(parts) + ("" if parts[-1] == "now" else " min")
