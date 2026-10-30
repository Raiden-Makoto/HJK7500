"""Wake-on-motion from the OV5640 camera.

Frames come from v4l2-ctl on a pipe; only the brightness (Y) channel is used,
shrunk to 160x120 and compared against a slowly updating picture of the room.
"""

import subprocess
import threading
import time

import numpy as np

SCALE = 4               # 640x480 -> 160x120
PROCESS_EVERY = 3       # of the sensor's ~15 fps, look at ~5
BACKGROUND_RATE = 0.05  # how fast the "normal room" picture absorbs changes
WARMUP_FRAMES = 10      # let auto-exposure settle before detecting


class MotionDetector:
    def __init__(self, pixel_delta, fraction):
        self.pixel_delta = pixel_delta
        self.fraction = fraction
        self.background = None
        self.frames = 0
        self.hits = 0

    def feed(self, luma):
        """luma: 2-D uint8 array. Returns True when this frame counts as motion."""
        frame = luma.astype(np.float32)
        self.frames += 1
        if self.background is None or self.frames <= WARMUP_FRAMES:
            self.background = frame
            return False
        changed = np.abs(frame - self.background) > self.pixel_delta
        self.background += BACKGROUND_RATE * (frame - self.background)
        # Two frames in a row filters out single-frame noise and flicker.
        self.hits = self.hits + 1 if changed.mean() > self.fraction else 0
        return self.hits >= 2


class Camera:
    """Runs the detector in a thread while `active()` is true."""

    def __init__(self, device, size, pixel_format, detector, active, log):
        self.device = device
        self.width, self.height = size
        self.pixel_format = pixel_format
        self.detector = detector
        self.active = active
        self.log = log
        self.ok = False
        self.last_motion = 0.0

    def run(self, stop):
        failed_before = False
        while not stop.is_set():
            if not self.active():
                stop.wait(10)
                continue
            try:
                self._stream(stop)
            except Exception as e:
                if self.ok or not failed_before:
                    self.log(f"camera unavailable: {e!r}")
                failed_before = True
            self.ok = False
            stop.wait(60)

    def _stream(self, stop):
        cmd = [
            "v4l2-ctl", "-d", self.device,
            f"--set-fmt-video=width={self.width},height={self.height},pixelformat={self.pixel_format}",
            "--stream-mmap", "--stream-to=-",
        ]
        frame_bytes = self.width * self.height * 2
        y_offset = 1 if self.pixel_format == "UYVY" else 0
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            n = 0
            while not stop.is_set() and self.active():
                buf = proc.stdout.read(frame_bytes)
                if len(buf) < frame_bytes:
                    err = proc.stderr.read().decode(errors="replace").strip()
                    raise RuntimeError(err.splitlines()[-1] if err else "stream ended")
                if not self.ok:
                    self.log("camera streaming")
                    self.ok = True
                n += 1
                if n % PROCESS_EVERY:
                    continue
                luma = np.frombuffer(buf, np.uint8)[y_offset::2].reshape(self.height, self.width)
                if self.detector.feed(luma[::SCALE, ::SCALE]):
                    self.last_motion = time.time()
        finally:
            proc.kill()
            proc.wait()
