"""HJK7500: TransLink departure board for the PICO-PI-IMX7's 5" screen."""

import argparse
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import departures
import gtfs_rt
import schedule as sched


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def load_env(path):
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class Data:
    """Schedule and real-time updates, refreshed in a background thread."""

    def __init__(self, api_key):
        self.api_key = api_key
        self.lock = threading.Lock()
        self.schedule = None
        self.updates = {}
        self.realtime_ok = None
        self.cache_json = config.CACHE_DIR / "schedule.json"
        self.cache_zip = config.CACHE_DIR / "google_transit.zip"

    def snapshot(self):
        with self.lock:
            return self.schedule, self.updates

    def refresh_schedule(self):
        current = self.schedule or sched.Schedule.load(self.cache_json, config.ROWS, config.TIMEZONE)
        if current and not current.is_stale(time.time(), config.SCHEDULE_MAX_AGE_S):
            with self.lock:
                self.schedule = current
            return
        try:
            log("downloading static GTFS")
            sched.download(config.STATIC_GTFS_URL, self.cache_zip)
            start = time.time()
            fresh = sched.Schedule(sched.build(self.cache_zip, config.ROWS), config.TIMEZONE)
            fresh.save(self.cache_json)
            log(f"schedule {fresh.data['feed_version']} built in {time.time() - start:.0f}s: "
                + ", ".join(str(len(r)) for r in fresh.data["rows"]) + " stop times")
            current = fresh
        except Exception as e:  # keep showing the old schedule if the refresh fails
            log(f"schedule refresh failed: {e!r}")
        with self.lock:
            self.schedule = current

    def refresh_realtime(self):
        schedule = self.schedule
        if schedule is None or not self.api_key:
            return
        try:
            start = time.time()
            buf = gtfs_rt.fetch(config.REALTIME_URL, self.api_key)
            wanted = departures.wanted_trip_ids(schedule, config.ROWS, time.time())
            updates = gtfs_rt.parse(buf, wanted)
            if self.realtime_ok is not True:
                log(f"real-time OK: {len(buf) // 1024} KB, {len(updates)} relevant trips, "
                    f"{time.time() - start:.1f}s")
            self.realtime_ok = True
        except Exception as e:
            if self.realtime_ok is not False:
                log(f"real-time unavailable, showing schedule only: {e!r}")
            self.realtime_ok = False
            updates = {}
        with self.lock:
            self.updates = updates

    def run(self, stop):
        next_schedule_check = 0
        while not stop.is_set():
            if time.time() >= next_schedule_check:
                self.refresh_schedule()
                next_schedule_check = time.time() + 3600
            self.refresh_realtime()
            # Wi-Fi is often still connecting at boot, so retry quickly until the first success.
            stop.wait(config.REALTIME_INTERVAL_S if self.realtime_ok else 5)


def row_label(row):
    # The font draws capitals as double-height glyphs; lowercase gives the
    # uniform single-height lettering used on real Luminator signs.
    return f"{row.route} {row.label}".lower()


def render(board, data):
    schedule, updates = data.snapshot()
    if schedule is None:
        board.message("Loading schedule")
        return
    now = time.time()
    # No RTC battery: after a power cut the clock starts years in the past
    # until ntpd steps it, and every row would read "--".
    if now < schedule.data["built_at"]:
        board.message("setting clock")
        return
    rows = departures.upcoming(schedule, updates, config.ROWS, now, config.DEPARTURES_PER_ROW)
    board.draw([
        (row_label(row), departures.format_times(times, now))
        for row, times in zip(config.ROWS, rows)
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windowed", action="store_true", help="800x480 window instead of full screen")
    parser.add_argument("--screenshot", type=Path, help="render once to a PNG and exit")
    args = parser.parse_args()

    load_env(config.APP_DIR / ".env")
    data = Data(os.environ.get("TRANSLINK_API_KEY", ""))
    if not data.api_key:
        log("TRANSLINK_API_KEY not set, showing schedule only")

    if args.screenshot:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import display  # after SDL_VIDEODRIVER is set

    labels = [row_label(r) for r in config.ROWS]
    board = display.Board(config.FONT_PATH, labels, fullscreen=not (args.windowed or args.screenshot),
                          fg=config.AMBER, bg=config.BLACK)

    if args.screenshot:
        data.refresh_schedule()
        data.refresh_realtime()
        render(board, data)
        board.save(args.screenshot)
        return

    import pygame

    stop = threading.Event()
    threading.Thread(target=data.run, args=(stop,), daemon=True).start()
    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q)
                ):
                    return
            render(board, data)
            time.sleep(5)
    finally:
        stop.set()


if __name__ == "__main__":
    main()
