import io  # BufferedIOBase parent for a simple output buffer
from threading import Condition, Thread  # Notify waiting clients; daemon stream thread
from datetime import datetime  # Timestamp overlay on frames
import numpy as np  # Byte buffer → ndarray for OpenCV decode
import cv2  # Image processing and JPEG encoding

import time  # FPS pacing

from .recorder import VideoRecorder  # Background segmented video recording


class StreamingOutput(io.BufferedIOBase):
    def __init__(self, picam2):
        self.frame = None  # Latest JPEG bytes published to clients
        self.condition = Condition()  # Signals when a new frame is available
        self.video_recorder = None  # Lazy-created recorder bound to picam2
        self.picam2 = picam2  # Shared camera instance

    def write(self, buf):
        # Attempt to decode buffer → BGR image for overlay; fallback to raw bytes
        frame_bytes = None
        nparr = np.frombuffer(buf, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is not None:
            # Draw timestamp with semi-transparent background for readability
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            font_color = (255, 255, 255)
            font_thickness = 2
            (text_width, text_height), _ = cv2.getTextSize(timestamp, font, font_scale, font_thickness)
            overlay = img.copy()
            cv2.rectangle(overlay, (10, 10), (20 + text_width, 20 + text_height), (0, 0, 0), -1)
            alpha = 0.6
            cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
            cv2.putText(img, timestamp, (15, 30), font, font_scale, font_color, font_thickness, cv2.LINE_AA)

            ret, jpeg = cv2.imencode('.jpg', img)  # Encode annotated frame to JPEG
            if ret:
                frame_bytes = jpeg.tobytes()

        # Fallback to original JPEG buffer when processing fails
        if frame_bytes is None:
            frame_bytes = bytes(buf)

        if self.video_recorder is None:
            # Lazy-create a recorder tied to the same camera
            self.video_recorder = VideoRecorder(self.picam2)
            self.video_recorder.start_recording()

        with self.condition:
            self.frame = frame_bytes  # Publish for MJPEG clients
            self.condition.notify_all()  # Wake any waiting consumers


def _stream_loop(picam2, output: StreamingOutput, fps: int = 10):
    interval = max(0.001, 1.0 / max(1, fps))  # FPS → sleep interval (clamped)
    while True:
        # Capture frame as RGB array, convert to BGR for OpenCV drawing
        frame = picam2.capture_array("main")
        if frame is None:
            continue
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  # RGB → BGR
        else:
            # Fallback: attempt direct use
            bgr = frame

        # Timestamp overlay (same style as write())
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        font_color = (255, 255, 255)
        font_thickness = 2
        (text_width, text_height), _ = cv2.getTextSize(timestamp, font, font_scale, font_thickness)
        overlay = bgr.copy()
        cv2.rectangle(overlay, (10, 10), (20 + text_width, 20 + text_height), (0, 0, 0), -1)
        alpha = 0.6
        cv2.addWeighted(overlay, alpha, bgr, 1 - alpha, 0, bgr)
        cv2.putText(bgr, timestamp, (15, 30), font, font_scale, font_color, font_thickness, cv2.LINE_AA)

        # Encode JPEG and publish
        ret, jpeg = cv2.imencode('.jpg', bgr)
        if ret:
            with output.condition:
                output.frame = jpeg.tobytes()  # Latest frame bytes
                output.condition.notify_all()  # Notify listeners
        # Sleep to control FPS
        time.sleep(interval)


def start_stream_thread(picam2, output: StreamingOutput, fps: int = 10) -> Thread:
    t = Thread(target=_stream_loop, args=(picam2, output, fps), daemon=True)  # Fire-and-forget daemon
    t.start()
    return t
