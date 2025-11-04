#!/usr/bin/env python3
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Import the RECORDINGS_DIR from the project's config
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from low.config import RECORDINGS_DIR

def delete_old_recordings(days_to_keep=7):
    """
    Delete recording directories that are older than the specified number of days.
    
    Args:
        days_to_keep (int): Number of days of recordings to keep
    """
    # Print header with timestamp
    now = datetime.now()
    print("\n" + "-" * 80)
    print(f"Running cleanup job on {now.strftime('%d-%m-%Y at %H:%M:%S')}")
    print("-" * 20)
    
    # Calculate the cutoff date (anything before this will be deleted)
    cutoff_date = now - timedelta(days=days_to_keep)
    print(f"\nCleaning up recordings older than {cutoff_date.strftime('%Y-%m-%d')}")
    
    # Ensure the recordings directory exists
    if not os.path.exists(RECORDINGS_DIR):
        print(f"Recordings directory not found: {RECORDINGS_DIR}")
        return
    
    # Get all date-named directories
    deleted_dirs = 0
    deleted_videos = 0
    total_freed = 0  # in bytes
    
    for entry in os.scandir(RECORDINGS_DIR):
        if not entry.is_dir():
            continue
            
        # Check if directory name matches YYYY-MM-DD format
        try:
            dir_date = datetime.strptime(entry.name, '%Y-%m-%d')
        except ValueError:
            continue  # Skip directories that don't match the date format
            
        # Check if the directory is older than the cutoff date
        if dir_date.date() < cutoff_date.date():
            try:
                # Calculate size before deletion
                dir_size = sum(f.stat().st_size for f in Path(entry.path).rglob('*') if f.is_file())
                
                # Remove the directory and all its contents
                # Count video files before deletion
                video_extensions = ('.mp4', '.avi', '.mov', '.mkv')
                video_count = sum(1 for f in Path(entry.path).rglob('*') 
                               if f.is_file() and f.suffix.lower() in video_extensions)
                
                shutil.rmtree(entry.path)
                print(f"Deleted {entry.path} (size: {dir_size / (1024*1024):.2f} MB, {video_count} videos)")
                
                deleted_dirs += 1
                deleted_videos += video_count
                total_freed += dir_size
                
            except Exception as e:
                print(f"Error deleting {entry.path}: {e}")
    
    # Print summary
    print(f"\nCleanup complete!")
    print(f"Deleted {deleted_dirs} directories")
    print(f"Deleted {deleted_videos} video files")
    print(f"Freed {total_freed / (1024*1024):.2f} MB of disk space")

if __name__ == "__main__":
    delete_old_recordings(days_to_keep=7)
