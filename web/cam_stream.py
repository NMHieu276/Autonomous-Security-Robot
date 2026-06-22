#!/usr/bin/env python3
"""
cam_stream.py — MJPEG Streaming Server using rpicam-vid.

Runs independently of ROS 2. Captures frames from the IMX219 camera
via rpicam-vid, parses the MJPEG stream, and re-serves it over HTTP.

Optimised for:
  - Low latency (no frame buffer queue)
  - Memory safety (1 MB hard cap on internal buffer)
  - Auto-restart on camera crash

Access the stream at:  http://<pi-ip>:8080/stream.mjpg

Usage:
  python3 cam_stream.py

To run as a systemd service see docs/setup_guide.md § Camera service.
"""
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ── Configuration ────────────────────────────────────────────
WIDTH        = 640
HEIGHT       = 480
FPS          = 30
PORT         = 8080
BOUNDARY     = b'jpgboundary'
MAX_BUF_SIZE = 1_048_576   # 1 MB — hard limit to prevent memory leak


class CamStream:
    """Reads MJPEG frames from rpicam-vid and notifies waiting HTTP clients."""

    def __init__(self):
        self.frame     = b''
        self.condition = threading.Condition()
        self.proc      = self._start_rpicam()
        threading.Thread(target=self._read_frames, daemon=True).start()
        print(f'[CAM] rpicam-vid started at {WIDTH}x{HEIGHT}@{FPS}fps')

    def _start_rpicam(self) -> subprocess.Popen:
        return subprocess.Popen([
            'rpicam-vid', '-t', '0',
            '--width',     str(WIDTH),
            '--height',    str(HEIGHT),
            '--framerate', str(FPS),
            '--codec', 'mjpeg',
            '--nopreview',
            '-o', '-',
        ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def _read_frames(self):
        buf = b''
        while True:
            chunk = self.proc.stdout.read(4096)
            if not chunk:
                self._restart()
                buf = b''
                continue

            buf += chunk

            # Hard cap: drop buffer if it grows beyond 1 MB
            if len(buf) > MAX_BUF_SIZE:
                print('[CAM] Warning: buffer overflow — flushing.')
                buf = b''
                continue

            # Extract complete JPEG frames (SOI=FFD8 … EOI=FFD9)
            while True:
                start = buf.find(b'\xff\xd8')
                if start == -1:
                    break
                end = buf.find(b'\xff\xd9', start + 2)
                if end == -1:
                    break
                with self.condition:
                    self.frame = buf[start:end + 2]
                    self.condition.notify_all()
                buf = buf[end + 2:]

    def _restart(self):
        print('[CAM] rpicam-vid crashed — restarting in 2 s…')
        try:
            self.proc.kill()
        except Exception:
            pass
        time.sleep(2)
        self.proc = self._start_rpicam()
        print('[CAM] rpicam-vid restarted successfully.')

    def get_frame(self) -> bytes:
        """Block up to 1 second for the next JPEG frame."""
        with self.condition:
            self.condition.wait(timeout=1.0)
            return self.frame


cam = CamStream()


class StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split('?')[0] == '/stream.mjpg':
            self.send_response(200)
            self.send_header(
                'Content-Type',
                f'multipart/x-mixed-replace; boundary={BOUNDARY.decode()}'
            )
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                while True:
                    frame = cam.get_frame()
                    if frame:
                        self.wfile.write(b'--' + BOUNDARY + b'\r\n')
                        self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                        self.wfile.write(frame)
                        self.wfile.write(b'\r\n')
            except Exception:
                pass   # Client disconnected — clean exit
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass   # Suppress per-request access log noise


if __name__ == '__main__':
    print(f'[CAM] MJPEG server → http://0.0.0.0:{PORT}/stream.mjpg')
    try:
        ThreadingHTTPServer(('', PORT), StreamHandler).serve_forever()
    except KeyboardInterrupt:
        print('\n[CAM] Shutting down…')
        try:
            cam.proc.kill()
        except Exception:
            pass
