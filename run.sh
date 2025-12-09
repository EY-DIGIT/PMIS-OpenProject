#!/bin/bash
# OpenProject Server Startup Script for Linux/Mac/Git Bash
# Run with: ./run.sh or bash run.sh

echo "============================================================"
echo "Starting OpenProject FastAPI Server"
echo "============================================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to that directory
cd "$SCRIPT_DIR"

# Start the server
python start_server.py
