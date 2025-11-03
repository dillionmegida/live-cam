#!/bin/bash

# Change to the project directory
cd "$(dirname "$0")/.."

# Run the cleanup script
python3 -m scripts.cleanup_old_recordings

