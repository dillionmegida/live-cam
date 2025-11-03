import logging  # Logging warnings/errors for streaming client disconnects, etc.
import os  # Filesystem operations for recordings listing/serving
import json  # Serialize responses like /system.json and /api/recordings
import re  # Regular expressions for pattern matching
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
                # Parse query parameters
                from urllib.parse import parse_qs, urlparse, unquote
                query = parse_qs(urlparse(self.path).query)
                page = int(query.get('page', ['1'])[0]) - 1  # 0-based index
                target_date = query.get('date', [None])[0]
                per_page = 20
                
                # Get all video files with their metadata from all date subdirectories
                all_videos = []
                
                # If a specific date is provided, only look in that date's directory
                if target_date:
                    date_dir = os.path.join(RECORDINGS_DIR, target_date)
                    if os.path.exists(date_dir) and os.path.isdir(date_dir):
                        search_dirs = [(date_dir, target_date)]
                    else:
                        search_dirs = []
                else:
                    # If no date specified, search all directories
                    search_dirs = [(RECORDINGS_DIR, '')]
                    for root, dirs, _ in os.walk(RECORDINGS_DIR):
                        for dir_name in dirs:
                            if re.match(r'\d{4}-\d{2}-\d{2}$', dir_name):
                                search_dirs.append((os.path.join(root, dir_name), dir_name))
                
                # Process each directory
                for root, date_from_dir in search_dirs:
                    try:
                        files = os.listdir(root)
                    except (OSError, IOError):
                        continue
                        
                    for filename in files:
                        if not filename.endswith('.mp4'):
                            continue
                            
                        filepath = os.path.join(root, filename)
                        if not os.path.isfile(filepath):
                            continue
                            
                        try:
                            stat = os.stat(filepath)
                            dt = datetime.fromtimestamp(stat.st_mtime)
                            
                            # Use date from directory if available, otherwise from file mtime
                            display_date = date_from_dir if date_from_dir and re.match(r'\d{4}-\d{2}-\d{2}$', date_from_dir) else dt.strftime('%Y-%m-%d')
                            
                            # If we're filtering by date and this file doesn't match, skip it
                            if target_date and display_date != target_date:
                                continue
                            
                            # Store relative path for download links
                            rel_path = os.path.relpath(root, RECORDINGS_DIR)
                            rel_filepath = os.path.join(rel_path, filename) if rel_path != '.' else filename
                            
                            all_videos.append({
                                'name': filename,
                                'path': rel_filepath,  # Relative path for downloads
                                'size': f"{stat.st_size / (1024*1024):.1f} MB",
                                'date': dt.strftime('%Y-%m-%d %H:%M:%S'),
                                'date_group': display_date,
                                'timestamp': dt.timestamp()
                            })
                        except (OSError, IOError):
                            continue
                
                # Sort by timestamp (newest first)
                all_videos.sort(key=lambda x: x['timestamp'], reverse=True)
                
                # Clean up video objects before sending
                paginated_videos = all_videos[page * per_page:(page + 1) * per_page]
                for video in paginated_videos:
                    video.pop('timestamp', None)
                    video.pop('date_group', None)
                
                total_videos = len(all_videos)
                total_pages = (total_videos + per_page - 1) // per_page  # Ceiling division
                
                content = json.dumps({
                    'videos': paginated_videos,
                    'pagination': {
                        'current_page': page + 1,
                        'total_pages': total_pages,
                        'total_videos': total_videos,
                        'per_page': per_page
                    }
                }).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(content)
            elif self.path == '/api/oldest-date':
                # Find the oldest recording date
                oldest_date = None
                
                try:
                    for entry in os.scandir(RECORDINGS_DIR):
                        if entry.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}$', entry.name):
                            try:
                                dir_date = datetime.strptime(entry.name, '%Y-%m-%d').date()
                                if oldest_date is None or dir_date < oldest_date:
                                    oldest_date = dir_date
                            except ValueError:
                                continue
                    
                    response = {
                        'oldest_date': oldest_date.isoformat() if oldest_date else None
                    }
                    content = json.dumps(response).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(content)
                except Exception as e:
                    self.send_error(500, str(e))
                    
            elif self.path.startswith('/download'):
                # Serve video file for download/inline playback
                rel_path = self.path[len('/download/'):]  # Extract relative path from URL
                rel_path = rel_path.split('?')[0]  # Remove any query parameters
                rel_path = rel_path.replace('..', '')  # Prevent directory traversal
                filepath = os.path.join(RECORDINGS_DIR, rel_path)  # Build absolute path
                
                # Check if file exists and is within the RECORDINGS_DIR
                if os.path.exists(filepath) and os.path.abspath(filepath).startswith(os.path.abspath(RECORDINGS_DIR)):
                    # Get file size and send headers for streaming
                    file_size = os.path.getsize(filepath)
                    self.send_response(200)
                    self.send_header('Content-Type', 'video/mp4')
                    self.send_header('Content-Length', file_size)
                    self.send_header('Content-Disposition', f'inline; filename="{os.path.basename(rel_path)}"')
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
