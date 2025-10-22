import logging  # Logging warnings/errors for streaming client disconnects, etc.
import os  # Filesystem operations for recordings listing/serving
import json  # Serialize responses like /system.json and /api/recordings
import time  # Compute uptime from boot time
import subprocess  # Query SoC temperature via vcgencmd on Raspberry Pi
from datetime import datetime  # Timestamp formatting and parsing
from http import server  # Base HTTP server classes

import psutil  # System metrics: CPU, memory, disk, boot time

from .templates import PAGE_INDEX, PAGE_RECORDINGS  # HTML templates served for UI pages
from .config import RECORDINGS_DIR


def make_handler(output):  # Factory to bind the shared StreamingOutput to the handler
    class StreamingHandler(server.BaseHTTPRequestHandler):  # Per-connection HTTP handler
        def do_GET(self):  # Handle all GET routes
            if self.path == '/':
                self.send_response(301)  # Redirect root to the main index page
                self.send_header('Location', '/index.html')
                self.end_headers()
            elif self.path == '/index.html':
                content = PAGE_INDEX.encode('utf-8')  # Render homepage HTML
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Content-Length', len(content))
                self.end_headers()
                self.wfile.write(content)
            elif self.path == '/recordings':
                content = PAGE_RECORDINGS.encode('utf-8')  # Render recordings page HTML
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Content-Length', len(content))
                self.end_headers()
                self.wfile.write(content)
            elif self.path == '/stream.mjpg':
                self.send_response(200)  # Begin MJPEG multipart HTTP response
                self.send_header('Age', 0)
                self.send_header('Cache-Control', 'no-cache, private')  # Prevent caching
                self.send_header('Pragma', 'no-cache')
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
                self.end_headers()
                try:
                    while True:
                        with output.condition:  # Wait for next frame published by streaming thread
                            output.condition.wait()
                            frame = output.frame
                        self.wfile.write(b'--FRAME\r\n')  # Boundary marker for MJPEG
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', len(frame))
                        self.end_headers()
                        self.wfile.write(frame)  # Write JPEG bytes
                        self.wfile.write(b'\r\n')  # End of part
                except Exception as e:
                    logging.warning('Removed streaming client %s: %s', self.client_address, str(e))  # Client disconnected
            elif self.path == '/system.json':
                # Get system information (CPU %, memory %, disk usage, temp, uptime)
                cpu_usage = psutil.cpu_percent(interval=1)  # Sample CPU usage over 1s
                memory = psutil.virtual_memory()  # Memory stats
                memory_percent = memory.percent
                
                # Get disk usage
                disk = psutil.disk_usage('/')  # Root filesystem usage
                disk_usage_percent = (disk.used / disk.total) * 100
                disk_usage_gb = disk.used / (1024**3)
                disk_total_gb = disk.total / (1024**3)
                disk_text = f"{disk_usage_gb:.1f}/{disk_total_gb:.1f} GB"  # Human-readable used/total
                
                # Get CPU temperature (Raspberry Pi specific; may fail on other systems)
                try:
                    temp_result = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True)
                    cpu_temp = float(temp_result.stdout.replace('temp=', '').replace("'C\n", ''))
                except Exception:
                    cpu_temp = 0.0  # Fallback if command unavailable

                # Uptime
                boot_time = psutil.boot_time()  # Epoch time when system booted
                uptime_seconds = int(time.time() - boot_time)
                days = uptime_seconds // 86400
                hours = (uptime_seconds % 86400) // 3600
                minutes = (uptime_seconds % 3600) // 60
                uptime_human = f"{days}d {hours}h {minutes}m" if days else (f"{hours}h {minutes}m" if hours else f"{minutes}m")

                system_info = {
                    'cpu': round(cpu_usage, 1),
                    'temp': round(cpu_temp, 1),
                    'memory': round(memory_percent, 1),
                    'storage': disk_text,
                    'storage_percent': round(disk_usage_percent, 1),
                    'uptime_seconds': uptime_seconds,
                    'uptime_human': uptime_human,
                }
                
                content = json.dumps(system_info).encode('utf-8')  # JSON payload
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-cache')  # Prevent client caching of metrics
                self.end_headers()
                self.wfile.write(content)
            elif self.path.startswith('/api/recordings'):
                # Return list of recordings (flat) and grouped by hourly windows per date
                videos = []  # Accumulate file metadata
                for filename in os.listdir(RECORDINGS_DIR):
                    if filename.endswith('.mp4'):
                        filepath = os.path.join(RECORDINGS_DIR, filename)  # Absolute file path
                        stat = os.stat(filepath)  # File stats (size, mtime)
                        dt = datetime.fromtimestamp(stat.st_mtime)  # Modification time → datetime
                        videos.append({
                            'name': filename,
                            'size': f"{stat.st_size / (1024*1024):.1f} MB",  # Human-readable size
                            'date': dt.strftime('%Y-%m-%d %H:%M:%S'),  # String date for UI and sorting
                        })
                # Sort by date, newest first
                videos.sort(key=lambda x: x['date'], reverse=True)

                # Group per date-hour window (e.g., 13:00–14:00 on 2025-10-19)
                from collections import defaultdict  # Local import to keep top-level clean
                grouped = defaultdict(list)  # label → list of videos
                for v in videos:
                    dt = datetime.strptime(v['date'], '%Y-%m-%d %H:%M:%S')  # Parse back to datetime
                    start_label = dt.strftime('%Y-%m-%d, %I %p')  # Hour window start, 12h clock
                    end_hour = (dt.hour + 1) % 24
                    # Build end label using same date; label only needs end hour text
                    end_label = datetime(dt.year, dt.month, dt.day, end_hour).strftime('%I %p')
                    label = f"{start_label} - {end_label}"  # e.g., 2025-10-19, 01 PM – 02 PM
                    grouped[label].append(v)

                # Order groups by latest datetime descending
                def group_sort_key(label: str):
                    # Extract the start window part: 'YYYY-MM-DD, HH AM/PM'
                    base = label.split('-')[0].strip()
                    return datetime.strptime(base, '%Y-%m-%d, %I %p')

                groups = [
                    {
                        'label': label,  # Hourly window label
                        'videos': sorted(items, key=lambda x: x['date'], reverse=True)  # Newest first
                    }
                    for label, items in sorted(grouped.items(), key=lambda kv: group_sort_key(kv[0]), reverse=True)
                ]

                content = json.dumps({'videos': videos, 'groups': groups}).encode('utf-8')  # Combined payload
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(content)
            elif self.path.startswith('/download/'):
                # Serve video file for download/inline playback
                filename = self.path[len('/download/'):]  # Extract filename from path
                filename = filename.split('?')[0]  # Remove any query parameters
                filepath = os.path.join(RECORDINGS_DIR, filename)  # Build absolute path
                
                if os.path.exists(filepath) and filepath.startswith(RECORDINGS_DIR):
                    # Get file size and send headers for streaming
                    file_size = os.path.getsize(filepath)
                    self.send_response(200)
                    self.send_header('Content-Type', 'video/mp4')
                    self.send_header('Content-Length', file_size)
                    self.send_header('Content-Disposition', f'inline; filename="{filename}"')
                    self.end_headers()
                    
                    # Stream the file in 1MB chunks
                    with open(filepath, 'rb') as f:
                        while True:
                            chunk = f.read(1024 * 1024)  # 1MB chunks
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                else:
                    self.send_error(404, 'File not found')  # Missing or outside expected directory
                    self.end_headers()
            else:
                self.send_error(404)  # Unknown route
                self.end_headers()

    return StreamingHandler  # Return the bound handler class to the server
