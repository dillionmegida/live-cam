import time
from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

from .streaming import StreamingOutput, start_stream_thread
from .recorder import VideoRecorder
from .handlers import make_handler
from .server import StreamingServer


def main(host: str = '', port: int = 5000, width: int = 800, height: int = 450, fps: int = 10):
    picam2 = Picamera2()

    # Maintain 16:9
    ratio = 16 / 9
    width = int(ratio * height)

    picam2.configure(picam2.create_video_configuration(
        main={'size': (width, height), 'format': 'RGB888'}
    ))

    # Set manual White Balance off and custom gains
    picam2.set_controls({
        "AwbMode": 0,
        "ColourGains": (1.0, 1.0),
        "FrameRate": fps,
    })

    # Start camera and stream thread (no JPEG encoder) to avoid conflicts with H264 recordings
    output = StreamingOutput(picam2)
    picam2.start()
    start_stream_thread(picam2, output, fps)

    # Start H264 segment recorder explicitly (since write() isn't used for triggering anymore)
    recorder = VideoRecorder(picam2, segment_seconds=60)
    recorder.start_recording()

    try:
        address = (host, port)
        handler_cls = make_handler(output)
        web_server = StreamingServer(address, handler_cls)
        print(f"Serving at http://<Pi_IP_Address>:{port}")
        print("Press Ctrl+C to stop the server")
        web_server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        # Stop recorder cleanly
        try:
            recorder.stop_recording()
        except Exception:
            pass
        picam2.stop()
        print("Server stopped.")


if __name__ == "__main__":
    main(host='0.0.0.0', port=5000)
