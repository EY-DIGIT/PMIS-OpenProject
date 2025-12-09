"""
OpenProject FastAPI Server Startup Script

Run this from inside the user_service directory:
    python start_server.py

Or from anywhere using forward slashes:
    python c:/Programming/user_service/start_server.py

Or use uvicorn directly with package path (after running this script once):
    uvicorn user_service.main:app --reload --port 8000
"""
import sys
import os
from pathlib import Path

# Setup paths for both execution modes
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = str(Path(current_dir).parent)

# Add both current and parent directory to path
# This allows both 'main:app' and 'user_service.main:app' to work
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

if __name__ == "__main__":
    import uvicorn

    print("="*60)
    print("Starting OpenProject FastAPI Server")
    print("="*60)
    print("\nServer will be available at:")
    print("  - API Root: http://localhost:8000/")
    print("  - Swagger UI: http://localhost:8000/api/docs")
    print("  - ReDoc: http://localhost:8000/api/redoc")
    print("\nPress CTRL+C to stop the server")
    print("="*60)
    print()

    # Change to this directory to ensure proper module loading
    os.chdir(current_dir)

    # Start the server - use user_service.main:app to maintain package structure
    uvicorn.run(
        "user_service.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
