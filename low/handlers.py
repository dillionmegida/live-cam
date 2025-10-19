import logging
import os
import json
import time
import subprocess
from datetime import datetime
from http import server

import psutil

from .templates import PAGE_INDEX, PAGE_RECORDINGS
from .config import RECORDINGS_DIR


def make_handler(output):
    class StreamingHandler(server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.send_response(301)
                self.send_header('Location', '/index.html')
                self.end_headers()
            elif self.path == '/index.html':
                content = PAGE_INDEX.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Content-Length', len(content))
                self.end_headers()
                self.wfile.write(content)
            elif self.path == '/recordings':
                content = PAGE_RECORDINGS.encode('utf-8')
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
                    cpu_temp = float(temp_result.stdout.replace('temp=', '').replace("'C\n", ''))
                except Exception:
                    cpu_temp = 0.0

                # Uptime
                boot_time = psutil.boot_time()
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
                
                content = json.dumps(system_info).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(content)
            elif self.path.startswith('/api/recordings'):
                # Return list of recordings (flat) and also grouped by hourly windows per date
                videos = []
                for filename in os.listdir(RECORDINGS_DIR):
                    if filename.endswith('.mp4'):
                        filepath = os.path.join(RECORDINGS_DIR, filename)
                        stat = os.stat(filepath)
                        dt = datetime.fromtimestamp(stat.st_mtime)
                        videos.append({
                            'name': filename,
                            'size': f"{stat.st_size / (1024*1024):.1f} MB",
                            'date': dt.strftime('%Y-%m-%d %H:%M:%S'),
                        })
                # Sort by date, newest first
                videos.sort(key=lambda x: x['date'], reverse=True)

                # Group per date-hour window (e.g., 13:00–14:00 on 2025-10-19)
                from collections import defaultdict
                grouped = defaultdict(list)
                for v in videos:
                    dt = datetime.strptime(v['date'], '%Y-%m-%d %H:%M:%S')
                    start_label = dt.strftime('%Y-%m-%d, %I %p')  # e.g., 2025-10-19, 01 PM
                    end_hour = (dt.hour + 1) % 24
                    # Build end label using same date or next day; for label purposes just show hour
                    end_label = datetime(dt.year, dt.month, dt.day, end_hour).strftime('%I %p')
                    label = f"{start_label} – {end_label}"
                    grouped[label].append(v)

                # Order groups by latest datetime descending
                def group_sort_key(label: str):
                    # label like 'YYYY-MM-DD, HH AM/PM – HH AM/PM'
                    base = label.split('–')[0].strip()  # 'YYYY-MM-DD, HH AM/PM'
                    return datetime.strptime(base, '%Y-%m-%d, %I %p')

                groups = [
                    {
                        'label': label,
                        'videos': sorted(items, key=lambda x: x['date'], reverse=True)
                    }
                    for label, items in sorted(grouped.items(), key=lambda kv: group_sort_key(kv[0]), reverse=True)
                ]

                content = json.dumps({'videos': videos, 'groups': groups}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(content)
            elif self.path.startswith('/download/'):
                # Serve video file for download
                filename = self.path[len('/download/'):]
                filename = filename.split('?')[0]  # Remove query parameters
                filepath = os.path.join(RECORDINGS_DIR, filename)
                
                if os.path.exists(filepath) and filepath.startswith(RECORDINGS_DIR):
                    # Get file size
                    file_size = os.path.getsize(filepath)
                    # Send file response
                    self.send_response(200)
                    self.send_header('Content-Type', 'video/mp4')
                    self.send_header('Content-Length', file_size)
                    self.send_header('Content-Disposition', f'inline; filename="{filename}"')
                    self.end_headers()
                    
                    # Stream the file
                    with open(filepath, 'rb') as f:
                        while True:
                            chunk = f.read(1024 * 1024)  # 1MB chunks
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                else:
                    self.send_error(404, 'File not found')
                    self.end_headers()
            else:
                self.send_error(404)
                self.end_headers()

    return StreamingHandler
