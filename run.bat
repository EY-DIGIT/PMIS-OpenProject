@echo off
REM OpenProject Server Startup Script for Windows
REM Double-click this file or run: run.bat

echo ============================================================
echo Starting OpenProject FastAPI Server
echo ============================================================
echo.

cd /d %~dp0
python start_server.py

pause
