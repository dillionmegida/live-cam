from threading import Thread
from datetime import datetime
import os  # Filesystem paths and directory creation
import time  # Segment duration sleep
import shutil  # Disk space checks
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput

from .config import RECORDINGS_DIR


class VideoRecorder:
    def __init__(self, picam2, segment_seconds: int = 60):
        self.picam2 = picam2  # Shared PiCamera2 instance
        self.recording = False  # Flag to control background loop
        self.output_dir = RECORDINGS_DIR  # Target directory for MP4 segments
        os.makedirs(self.output_dir, exist_ok=True)  # Ensure output directory exists
        self.recording_thread = None  # Background daemon thread handle
        self.segment_seconds = int(segment_seconds)  # Fixed length per segment
        self.min_free_bytes = 1 * 1024 * 1024 * 1024  # 1GB free-space threshold

    def start_recording(self):
        if not self.recording:  # Prevent double-start
            self.recording = True
            self.recording_thread = Thread(target=self._record_segment)
            self.recording_thread.daemon = True  # Exit with main program
            self.recording_thread.start()

    def _record_segment(self):
        while self.recording:
            # Check free space before starting a new segment
            total, used, free = shutil.disk_usage(self.output_dir)
            if free < self.min_free_bytes:
                # Not enough space; stop recording loop immediately
                self.recording = False
                break

            # Build timestamped filename per segment
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(self.output_dir, f'recording_{timestamp}.mp4')

            # Configure encoder and file output
            encoder = H264Encoder()
            output = FfmpegOutput(output_file)

            # Start recording; write `.pts` sidecar (presentation timestamps)
            self.picam2.start_recording(encoder, output, pts=f"{output_file}.pts")

            time.sleep(self.segment_seconds)  # Record for fixed segment length

            self.picam2.stop_recording()  # End current segment

            # Clean up sidecar if present; keep only the MP4
            if os.path.exists(f"{output_file}.pts"):
                os.remove(f"{output_file}.pts")

    def stop_recording(self):
        self.recording = False  # Signal loop to exit
        if self.recording_thread:
            self.recording_thread.join()  # Wait for thread to finish
