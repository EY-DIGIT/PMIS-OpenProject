@echo off
REM Run uvicorn with proper path setup from inside user_service directory
REM This allows using 'user_service.main:app' module path

setlocal

REM Get the parent directory and add it to PYTHONPATH
for %%I in ("%~dp0..") do set "PARENT_DIR=%%~fI"
set "PYTHONPATH=%PARENT_DIR%;%PYTHONPATH%"

echo ============================================================
echo OpenProject User Service - Starting with uvicorn
echo ============================================================
echo.
echo Using module path: user_service.main:app
echo Python path includes: %PARENT_DIR%
echo.
echo Server will be available at http://localhost:8000
echo Interactive Docs: http://localhost:8000/api/docs
echo.
echo Press CTRL+C to stop the server
echo ============================================================
echo.

uvicorn user_service.main:app --reload --host 0.0.0.0 --port 8000

endlocal
