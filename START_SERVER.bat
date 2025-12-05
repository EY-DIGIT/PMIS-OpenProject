@echo off
echo ============================================================
echo OpenProject User Service - FastAPI Server
echo ============================================================
echo.
echo Starting server at http://localhost:8000
echo.
echo Interactive Docs: http://localhost:8000/api/docs
echo ReDoc: http://localhost:8000/api/redoc
echo.
echo Press CTRL+C to stop the server
echo ============================================================
echo.

REM Method 1: Run from within user_service directory
uvicorn app:app --reload --host 0.0.0.0 --port 8000

REM Alternative method (uncomment if above doesn't work):
REM cd ..
REM uvicorn user_service.main:app --reload --host 0.0.0.0 --port 8000
