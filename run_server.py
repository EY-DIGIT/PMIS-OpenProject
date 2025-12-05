"""
Simple server startup script.
Run this from the user_service directory: python run_server.py
"""
import sys
import os

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

    uvicorn.run(
        "user_service.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
