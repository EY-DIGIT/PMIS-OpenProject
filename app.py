"""
Alternative entry point that works when run from within user_service directory.

Use this if you're running from inside the user_service folder.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import user_service
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now import the app
from user_service.main import app

# This allows running: uvicorn app:app --reload
# from within the user_service directory

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
