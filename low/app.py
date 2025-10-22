from picamera2 import Picamera2  # Main camera control interface
from .streaming import StreamingOutput, start_stream_thread  # Live MJPEG stream via capture thread
from .recorder import VideoRecorder  # H264 segment recorder (background thread)
from .handlers import make_handler  # HTTP request handler factory
from .server import StreamingServer  # Threaded HTTP server for streaming and APIs


def main(host: str = '', port: int = 5000, width: int = 800, height: int = 450, fps: int = 10):
    # Create camera instance (single camera device on Pi)
    picam2 = Picamera2()

    # Maintain 16:9 aspect ratio for the main stream
    ratio = 16 / 9
    width = int(ratio * height)

    # Configure the camera main stream: RGB888 ensures color frames (3 channels)
    picam2.configure(picam2.create_video_configuration(
        main={'size': (width, height), 'format': 'RGB888'}
    ))

    # Apply camera controls (manual WB, gains, FPS, grayscale via saturation)
    picam2.set_controls({
        "AwbMode": 0,              # Disable auto white balance for consistent output
        "ColourGains": (1.0, 1.0), # Neutral color gains
        "FrameRate": fps,          # Target frames per second
        "Saturation": 0.0,         # Force grayscale output (0.0 = gray, 1.0 = full color)
    })

    # Start camera and streaming thread (uses capture_array, not JPEG encoder)
    output = StreamingOutput(picam2)  # Shared buffer for MJPEG HTTP responses
    picam2.start()                    # Begin camera capture pipeline
    start_stream_thread(picam2, output, fps)  # Background thread publishes JPEG frames

    # Start H264 segment recorder explicitly (independent of the stream)
    recorder = VideoRecorder(picam2, segment_seconds=60)  # 1-minute segments by default
    recorder.start_recording()                             # Launch recording thread

    try:
        address = (host, port)                  # Bind host/port (0.0.0.0 for LAN access)
        handler_cls = make_handler(output)      # Build HTTP handler with access to stream buffer
        web_server = StreamingServer(address, handler_cls)  # Threaded server for concurrency
        print(f"Serving at http://<Pi_IP_Address>:{port}")  # Helpful runtime info
        web_server.serve_forever()              # Block here; handles requests until interrupted
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        # Graceful shutdown: stop recorder and camera
        try:
            recorder.stop_recording()  # Join background recording thread
        except Exception:
            pass
        picam2.stop()                 # Stop camera pipeline
        print("Server stopped.")


if __name__ == "__main__":
    main(host='0.0.0.0', port=5000)
