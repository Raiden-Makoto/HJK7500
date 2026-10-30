"""Minimal GTFS-Realtime TripUpdates decoder.

Decodes only the fields the departure board needs, and skips trips it isn't
asked about without decoding them. This keeps parsing the region-wide feed
fast on the PICO's Cortex-A7 without depending on the protobuf package.
"""

import urllib.parse
import urllib.request
from dataclasses import dataclass, field

# TripDescriptor.ScheduleRelationship
TRIP_CANCELED = 3
TRIP_DELETED = 7
# StopTimeUpdate.ScheduleRelationship
STOP_SKIPPED = 1
STOP_NO_DATA = 2


@dataclass
class StopUpdate:
    seq: int = None
    stop_id: str = None
    arr_delay: int = None
    arr_time: int = None
    dep_delay: int = None
    dep_time: int = None
    relationship: int = 0


@dataclass
class TripUpdate:
    trip_id: str
    start_date: str = None
    canceled: bool = False
    delay: int = None
    stops: list = field(default_factory=list)


def _varint(buf, i):
    result = shift = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if b < 0x80:
            return result, i
        shift += 7


def _fields(buf, start, end):
    """Yields (field_number, value); length-delimited values are (start, end)."""
    i = start
    while i < end:
        key, i = _varint(buf, i)
        num, wire = key >> 3, key & 7
        if wire == 0:
            value, i = _varint(buf, i)
        elif wire == 2:
            n, i = _varint(buf, i)
            value = (i, i + n)
            i += n
        elif wire == 1:
            value, i = None, i + 8
        elif wire == 5:
            value, i = None, i + 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")
        yield num, value


def _signed(v):
    return v - (1 << 64) if v >= 1 << 63 else v


def _text(buf, span):
    return bytes(buf[span[0]:span[1]]).decode("utf-8")


def _event(buf, span):
    delay = when = None
    for num, v in _fields(buf, *span):
        if num == 1:
            delay = _signed(v)
        elif num == 2:
            when = _signed(v) or None
    return delay, when


def _stop_update(buf, span):
    s = StopUpdate()
    for num, v in _fields(buf, *span):
        if num == 1:
            s.seq = v
        elif num == 2:
            s.arr_delay, s.arr_time = _event(buf, v)
        elif num == 3:
            s.dep_delay, s.dep_time = _event(buf, v)
        elif num == 4:
            s.stop_id = _text(buf, v)
        elif num == 5:
            s.relationship = v
    return s


def _trip_update(buf, span, trip_ids):
    descriptor, stop_spans, delay = None, [], None
    for num, v in _fields(buf, *span):
        if num == 1:
            descriptor = v
        elif num == 2:
            stop_spans.append(v)
        elif num == 5:
            delay = _signed(v)
    if descriptor is None:
        return None

    trip_id, start_date, relationship = None, None, 0
    for num, v in _fields(buf, *descriptor):
        if num == 1:
            trip_id = _text(buf, v)
        elif num == 3:
            start_date = _text(buf, v)
        elif num == 4:
            relationship = v
    if trip_id is None or (trip_ids is not None and trip_id not in trip_ids):
        return None

    stops = [_stop_update(buf, s) for s in stop_spans]
    stops.sort(key=lambda s: -1 if s.seq is None else s.seq)
    return TripUpdate(
        trip_id=trip_id,
        start_date=start_date,
        canceled=relationship in (TRIP_CANCELED, TRIP_DELETED),
        delay=delay,
        stops=stops,
    )


def parse(buf, trip_ids=None):
    """Returns {(trip_id, start_date): TripUpdate} for the requested trips."""
    updates = {}
    for num, entity in _fields(buf, 0, len(buf)):
        if num != 2:
            continue
        for enum, v in _fields(buf, *entity):
            if enum == 3:
                tu = _trip_update(buf, v, trip_ids)
                if tu:
                    updates[(tu.trip_id, tu.start_date)] = tu
    return updates


def fetch(url, api_key, timeout=30):
    full = f"{url}?{urllib.parse.urlencode({'apikey': api_key})}"
    with urllib.request.urlopen(full, timeout=timeout) as resp:
        return resp.read()
