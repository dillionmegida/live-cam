import io
import logging
import socketserver
from http import server
from threading import Condition
import cv2
import numpy as np
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, JpegEncoder
from picamera2.outputs import FileOutput
from datetime import datetime

PAGE = """
<html>
<head><title>Live Cam</title></head>
<body>
<img src="stream.mjpg" />
<style>
  * { margin:0; padding:0; }
  img { width: 100%; aspect-ratio: 16/9; }
</style>
</body></html>
"""

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        # Decode JPEG buffer to an image
        nparr = np.frombuffer(buf, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is not None:
            # Get current time and format it
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Add timestamp to the image
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            font_color = (255, 255, 255)  # White text
            font_thickness = 2
            
            # Get text size to create a background rectangle
            (text_width, text_height), _ = cv2.getTextSize(timestamp, font, font_scale, font_thickness)
            
            # Add semi-transparent background for better text visibility
            overlay = img.copy()
            cv2.rectangle(overlay, (10, 10), (20 + text_width, 20 + text_height), (0, 0, 0), -1)
            alpha = 0.6  # Transparency factor
            cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
            
            # Add timestamp text
            cv2.putText(img, timestamp, (15, 30), font, font_scale, font_color, font_thickness, cv2.LINE_AA)

        # Convert image back to JPEG buffer
        ret, jpeg = cv2.imencode('.jpg', img)
        if ret:
            with self.condition:
                self.frame = jpeg.tobytes()
                self.condition.notify_all()

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning('Removed streaming client %s: %s', self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

picam2 = Picamera2()

# Configure resolution
height = 450
ratio = 16 / 9
width = int(ratio * height)
picam2.configure(picam2.create_video_configuration(
  main={'size': (width, height), 'format': 'YUV420'})
)

# Set manual White Balance off and custom gains (adjust gains if needed)
picam2.set_controls({
    "AwbMode": 0,
    "ColourGains": (1.0, 1.0),
    "FrameRate": 10
})

output = StreamingOutput()

picam2.start_recording(JpegEncoder(q=70), FileOutput(output))

try:
    address = ('', 5000)
    server = StreamingServer(address, StreamingHandler)
    print("Serving at http://<Pi_IP_Address>:5000")
    server.serve_forever()
finally:
    picam2.stop_recording()
