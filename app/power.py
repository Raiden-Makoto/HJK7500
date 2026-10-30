"""Decides when the screen should be lit and drives the LCD backlight."""

import time


def screen_wanted(now, last_motion, camera_ok, awake_hours, wake_s, clock_ok=True):
    if not clock_ok:
        # Before ntpd fixes the clock the hour is meaningless; stay lit so
        # "setting clock" is visible.
        return True
    start, end = awake_hours
    if not start <= time.localtime(now).tm_hour < end:
        return False
    if not camera_ok:
        # Without a working camera nothing could ever wake it.
        return True
    return now - last_motion < wake_s


class Backlight:
    def __init__(self, path, log):
        self.path = path
        self.log = log
        self.on = None
        try:
            self.max = int((path / "max_brightness").read_text())
        except OSError:
            self.max = None

    def set(self, on):
        if on == self.on or self.max is None:
            return
        try:
            (self.path / "brightness").write_text(str(self.max if on else 0))
        except OSError as e:
            self.log(f"backlight: {e!r}")
        else:
            self.log(f"screen {'on' if on else 'off'}")
        self.on = on
