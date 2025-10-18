import io
import logging
import socketserver
from http import server
from threading import Condition, Timer
import cv2
import os
import numpy as np
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, JpegEncoder
from picamera2.outputs import FileOutput, FfmpegOutput
from datetime import datetime
from threading import Thread
import time
import psutil
import subprocess

PAGE = """
<html>
<head>
  <title>Live Cam</title>
  <script>
    function updateSystemInfo() {
      fetch('/system.json')
        .then(response => response.json())
        .then(data => {
          document.getElementById('cpu').textContent = data.cpu + '%';
          document.getElementById('temp').textContent = data.temp + '°C';
          document.getElementById('storage').textContent = data.storage;
          document.getElementById('memory').textContent = data.memory + '%';
        })
        .catch(err => console.log('Error fetching system info:', err));
    }
    // Update every 2 seconds
    setInterval(updateSystemInfo, 2000);
    // Initial update
    window.onload = updateSystemInfo;
  </script>
  <style>
    * { margin:0; padding:0; }
    body {
      font-family: Arial, sans-serif;
      background-color: #f0f0f0;
    }
    .container {
      display: grid;
      grid-template-areas: 
        "video stats"
        "controls controls";
      grid-template-columns: 2fr 1fr;
      gap: 20px;
      max-width: 1200px;
      margin: 20px auto;
      padding: 20px;
    }
    .video-section {
      grid-area: video;
      background: white;
      border-radius: 10px;
      padding: 15px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .stats-section {
      grid-area: stats;
      background: white;
      border-radius: 10px;
      padding: 15px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .stats-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 15px;
    }
    .stat-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 15px;
      background: #f8f9fa;
      border-radius: 8px;
      border: 1px solid #e9ecef;
    }
    .stat-label {
      font-size: 14px;
      color: #6c757d;
      margin-bottom: 5px;
    }
    .stat-value {
      font-size: 24px;
      font-weight: bold;
      color: #212529;
    }
    .progress-bar {
      width: 100%;
      height: 8px;
      background: #e9ecef;
      border-radius: 4px;
      overflow: hidden;
      margin-top: 5px;
    }
    .progress-fill {
      height: 100%;
      background: #0d6efd;
      width: var(--width);
      transition: width 0.3s ease;
    }
    .controls {
      grid-area: controls;
      background: white;
      border-radius: 10px;
      padding: 15px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    img {
      width: 100%;
      aspect-ratio: 16/9;
      border-radius: 8px;
      display: block;
    }
    @media (max-width: 768px) {
      .container {
        grid-template-areas: "video" "stats" "controls";
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="video-section">
      <h2>Live Camera Feed</h2>
      <img src="stream.mjpg" />
    </div>
    
    <div class="stats-section">
      <h2>System Status</h2>
      <div class="stats-grid">
        <div class="stat-item">
          <div class="stat-label">CPU Usage</div>
          <div class="stat-value" id="cpu">--%</div>
          <div class="progress-bar">
            <div class="progress-fill" style="--width: 0%"></div>
          </div>
        </div>
        
        <div class="stat-item">
          <div class="stat-label">CPU Temperature</div>
          <div class="stat-value" id="temp">--°C</div>
          <div class="progress-bar">
            <div class="progress-fill" style="--width: 0%"></div>
          </div>
        </div>
        
        <div class="stat-item">
          <div class="stat-label">Memory Usage</div>
          <div class="stat-value" id="memory">--%</div>
          <div class="progress-bar">
            <div class="progress-fill" style="--width: 0%"></div>
          </div>
        </div>
        
        <div class="stat-item">
          <div class="stat-label">Storage Used</div>
          <div class="stat-value" id="storage">--</div>
          <div class="progress-bar">
            <div class="progress-fill" style="--width: 0%"></div>
          </div>
        </div>
      </div>
    </div>
    
    <div class="controls">
      <h2>Controls</h2>
      <p>Camera is streaming at 10 FPS with timestamp overlay.</p>
      <p>Recordings are saved in 10-second segments to the 'recordings' directory.</p>
    </div>
  </div>
</body>
</html>
"""

class VideoRecorder:
    def __init__(self, picam2):
        self.picam2 = picam2
        self.recording = False
        self.output_dir = 'recordings'
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

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()
        self.video_recorder = None

    def write(self, buf):
        nparr = np.frombuffer(buf, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is not None:
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

        if self.video_recorder is None:
            self.video_recorder = VideoRecorder(picam2)
            self.video_recorder.start_recording()

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
        elif self.path == '/system.json':
            # Get system information
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Get disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            disk_usage_gb = disk.used / (1024**3)
            disk_total_gb = disk.total / (1024**3)
            disk_text = f"{disk_usage_gb:.1f}/{disk_total_gb:.1f} GB"
            
            # Get CPU temperature
            try:
                temp_result = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True)
                cpu_temp = float(temp_result.stdout.replace('temp=', '').replace('\'C\n', ''))
            except:
                cpu_temp = 0.0

            # Create JSON response
            system_info = {
                'cpu': round(cpu_usage, 1),
                'temp': round(cpu_temp, 1),
                'memory': round(memory_percent, 1),
                'storage': disk_text
            }
            
            import json
            content = json.dumps(system_info).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(content)
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

# Set manual White Balance off and custom gains
picam2.set_controls({
    "AwbMode": 0,
    "ColourGains": (1.0, 1.0),
    "FrameRate": 10
})

output = StreamingOutput()

# Start JPEG streaming for MJPEG
picam2.start_recording(JpegEncoder(q=70), FileOutput(output))

try:
    address = ('', 5000)
    server = StreamingServer(address, StreamingHandler)
    print("Serving at http://<Pi_IP_Address>:5000")
    server.serve_forever()
finally:
    if output.video_recorder:
        output.video_recorder.stop_recording()
    picam2.stop_recording()
