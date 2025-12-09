"""
Run server using uvicorn with proper PYTHONPATH setup.

This script allows you to use 'uvicorn user_service.main:app' from inside the user_service directory.

Usage:
    cd c:/Programming/user_service
    python run_with_uvicorn.py
"""
import sys
import os
import subprocess
from pathlib import Path

# Get directories
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = str(Path(current_dir).parent)

# Set up environment
env = os.environ.copy()
pythonpath = env.get('PYTHONPATH', '')
if pythonpath:
    env['PYTHONPATH'] = f"{parent_dir}{os.pathsep}{pythonpath}"
else:
    env['PYTHONPATH'] = parent_dir

print("=" * 60)
print("OpenProject User Service - uvicorn with package path")
print("=" * 60)
print(f"\nPYTHONPATH includes: {parent_dir}")
print("Using module path: user_service.main:app")
print("\nServer will be available at:")
print("  - API Root: http://localhost:8000/")
print("  - Swagger UI: http://localhost:8000/api/docs")
print("  - ReDoc: http://localhost:8000/api/redoc")
print("\nPress CTRL+C to stop the server")
print("=" * 60)
print()

# Change to the user_service directory
os.chdir(current_dir)

# Run uvicorn
try:
    subprocess.run(
        [
            sys.executable, "-m", "uvicorn",
            "user_service.main:app",
            "--reload",
            "--host", "0.0.0.0",
            "--port", "8000"
        ],
        env=env,
        check=True
    )
except KeyboardInterrupt:
    print("\n\nServer stopped by user")
except subprocess.CalledProcessError as e:
    print(f"\n\nError running uvicorn: {e}")
    sys.exit(1)
