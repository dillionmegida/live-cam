from threading import Thread
from datetime import datetime
import os
import time
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput

from .config import RECORDINGS_DIR


class VideoRecorder:
    def __init__(self, picam2):
        self.picam2 = picam2
        self.recording = False
        self.output_dir = RECORDINGS_DIR
        os.makedirs(self.output_dir, exist_ok=True)
        self.recording_thread = None

    def start_recording(self):
        if not self.recording:
            self.recording = True
            self.recording_thread = Thread(target=self._record_segment)
            self.recording_thread.daemon = True
            self.recording_thread.start()

    def _record_segment(self):
        while self.recording:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(self.output_dir, f'recording_{timestamp}.mp4')
            encoder = H264Encoder()
            output = FfmpegOutput(output_file)
            self.picam2.start_recording(encoder, output, pts=f"{output_file}.pts")
            time.sleep(10)
            self.picam2.stop_recording()
            if os.path.exists(f"{output_file}.pts"):
                os.remove(f"{output_file}.pts")

    def stop_recording(self):
        self.recording = False
        if self.recording_thread:
            self.recording_thread.join()
