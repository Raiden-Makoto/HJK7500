import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Row:
    route: str          # route number as printed on the bus, e.g. "15", "R4"
    label: str          # destination text shown after the route number
    stop_code: str      # 5-digit number on the bus stop sign
    walk_min: int = 0   # departures sooner than this many minutes are hidden
    headsign: str = ""  # if set, only trips whose headsign contains this


ROWS = [
    Row("15", "Olympic", "50996"),
    Row("15", "Marine", "50987"),
    Row("R4", "Joyce", "60349", walk_min=10),
    Row("9", "Boundary", "60535", walk_min=20, headsign="Boundary Loop"),
    Row("99", "Boundary", "60535", walk_min=20, headsign="Boundary Loop"),
]

DEPARTURES_PER_ROW = 2
TIMEZONE = "America/Vancouver"

STATIC_GTFS_URL = "https://gtfs-static.translink.ca/gtfs/google_transit.zip"
REALTIME_URL = "https://gtfsapi.translink.ca/v3/gtfsrealtime"
REALTIME_INTERVAL_S = 60
SCHEDULE_MAX_AGE_S = 24 * 3600

APP_DIR = Path(__file__).resolve().parent
FONT_PATH = APP_DIR.parent / "luminator-horizon" / "luminator-horizon-doublestack.otf"
CACHE_DIR = Path(os.environ.get("HJK7500_CACHE", Path.home() / ".cache" / "hjk7500"))

# Screen power: dark unless the camera saw motion in the last WAKE_S seconds,
# and always dark outside AWAKE_HOURS (local [start, end)).
AWAKE_HOURS = (8, 21)
WAKE_S = 5 * 60
BACKLIGHT_DIR = Path("/sys/class/backlight/backlight")

CAMERA_DEVICE = "/dev/video1"
CAMERA_SIZE = (640, 480)
CAMERA_FORMAT = "YUYV"
MOTION_PIXEL_DELTA = 25     # 0-255 brightness change for a pixel to count
MOTION_FRACTION = 0.04      # share of pixels that must change, two frames running

AMBER = (255, 170, 0)
BLACK = (0, 0, 0)
