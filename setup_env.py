"""
Environment setup helper for running uvicorn with package path from inside user_service folder.

This adds the parent directory to sys.path so 'user_service.main:app' can be resolved.
"""
import sys
import os
from pathlib import Path

# Get the parent directory (Programming folder)
parent_dir = str(Path(__file__).parent.parent)

# Add parent to sys.path if not already there
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
    print(f"Added to Python path: {parent_dir}")
