import os
import re
from datetime import datetime
import shutil

# Configuration
RECORDINGS_DIR = 'recordings'  # Change this to your recordings directory path if different

def extract_date(filename):
    """Extract date from filename (format: 'recording_YYYYMMDD_HHMMSS.mp4')"""
    match = re.match(r'recording_(\d{4})(\d{2})(\d{2})_', filename)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"  # Format as YYYY-MM-DD for folder names
    return None

def organize_videos():
    if not os.path.exists(RECORDINGS_DIR):
        print(f"Error: Directory '{RECORDINGS_DIR}' not found.")
        return

    # Get all mp4 files
    files = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith('.mp4')]
    
    if not files:
        print("No MP4 files found in the directory.")
        return

    moved_count = 0
    for filename in files:
        date_str = extract_date(filename)
        if not date_str:
            print(f"Skipping file (invalid format): {filename}")
            continue

        # Create date directory if it doesn't exist
        date_dir = os.path.join(RECORDINGS_DIR, date_str)
        os.makedirs(date_dir, exist_ok=True)

        # Move file
        src = os.path.join(RECORDINGS_DIR, filename)
        dst = os.path.join(date_dir, filename)
        
        try:
            shutil.move(src, dst)
            print(f"Moved: {filename} -> {date_str}/")
            moved_count += 1
        except Exception as e:
            print(f"Error moving {filename}: {str(e)}")

    print(f"\nDone! Moved {moved_count} files into date-based folders.")

if __name__ == "__main__":
    organize_videos()