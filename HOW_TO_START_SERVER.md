# How to Start the Server - Complete Guide

## Quick Start (Pick One)

### Option 1: Python Script (Recommended) ⭐
```bash
cd c:/Programming/user_service
python start_server.py
```

### Option 2: Uvicorn with Package Path
```bash
cd c:/Programming/user_service
python run_with_uvicorn.py
```

### Option 3: Simple uvicorn (No Package Path)
```bash
cd c:/Programming/user_service
uvicorn main:app --reload --port 8000
```

### Option 4: Batch File (Windows Double-Click)
- Double-click [run.bat](run.bat) in File Explorer
- Or: `cd c:/Programming/user_service && run.bat`

---

## All Available Methods

| Method | Command | Works From | Module Path Used |
|--------|---------|------------|------------------|
| start_server.py | `python start_server.py` | Inside or outside | `user_service.main:app` |
| run_with_uvicorn.py | `python run_with_uvicorn.py` | Inside user_service | `user_service.main:app` |
| Direct uvicorn | `uvicorn main:app --reload --port 8000` | Inside user_service | `main:app` |
| Batch file | `run.bat` or double-click | Inside user_service | `main:app` |
| Shell script | `./run.sh` or `bash run.sh` | Inside user_service | `main:app` |
| From parent | `python start_server.py` | Programming folder | `user_service.main:app` |

---

## Server Access Points

Once started, access the server at:

- **API Root:** http://localhost:8000/
- **Swagger UI (Interactive Docs):** http://localhost:8000/api/docs
- **ReDoc (Alternative Docs):** http://localhost:8000/api/redoc
- **Health Check:** http://localhost:8000/health
- **API v3 Root:** http://localhost:8000/api/v3

---

## Understanding the Two Module Paths

### Method A: Package Path (`user_service.main:app`)

Used when Python needs to find the user_service package:

```bash
# From inside user_service - requires PYTHONPATH setup
python start_server.py           # ✅ Sets up paths automatically
python run_with_uvicorn.py       # ✅ Sets up PYTHONPATH

# From parent directory - works naturally
cd c:/Programming
uvicorn user_service.main:app --reload --port 8000  # ✅ Natural
```

### Method B: Simple Path (`main:app`)

Used when Python can directly find main.py:

```bash
# From inside user_service - works naturally
cd c:/Programming/user_service
uvicorn main:app --reload --port 8000    # ✅ Natural
run.bat                                   # ✅ Uses this method
```

---

## Troubleshooting

### Error: "ModuleNotFoundError: No module named 'user_service'"

**Cause:** Running `uvicorn user_service.main:app` from inside user_service without PYTHONPATH setup.

**Solutions:**
1. Use `python start_server.py` instead (recommended)
2. Use `python run_with_uvicorn.py` instead
3. Use `uvicorn main:app` (simple path) instead
4. Set PYTHONPATH manually: `set PYTHONPATH=c:\Programming` (Windows CMD)

### Error: "Port 8000 already in use"

**Cause:** Another server instance is already running.

**Solutions:**
1. Stop the existing server (CTRL+C in its terminal)
2. Or change the port by editing the script:
   ```python
   port=8000  # Change to port=8001 or another port
   ```

### Error: "Database not found" or "No module named 'db_models'"

**Cause:** Database not initialized or import path issues.

**Solutions:**
1. Initialize the database first:
   ```bash
   cd c:/Programming/user_service
   python init_db_simple.py
   ```
2. The import fixes in this session should have resolved path issues

---

## Files Reference

### Startup Scripts:
- **[start_server.py](start_server.py)** - Main startup script with path setup
- **[run_with_uvicorn.py](run_with_uvicorn.py)** - Uvicorn-specific wrapper
- **[run.bat](run.bat)** - Windows batch file
- **[run.sh](run.sh)** - Linux/Mac shell script
- **[run_uvicorn.bat](run_uvicorn.bat)** - Windows batch with package path
- **[run_uvicorn.sh](run_uvicorn.sh)** - Unix shell with package path

### Main Application Files:
- **[main.py](main.py)** - FastAPI application entry point
- **[database.py](database.py)** - Database configuration
- **[app.py](app.py)** - Alternative entry point (legacy)

### Documentation:
- **[UVICORN_FIXED.md](UVICORN_FIXED.md)** - Details on uvicorn package path fix
- **[SERVER_STARTUP_FIXED.md](SERVER_STARTUP_FIXED.md)** - Original import fixes
- **[RUN_SERVER.md](RUN_SERVER.md)** - Additional running instructions
- **[HOW_TO_RUN.md](HOW_TO_RUN.md)** - Original how-to guide

---

## What Was Fixed

### Issue 1: Import Errors
Fixed in [services/user_service.py](services/user_service.py) and [database.py](database.py):
- Changed fallback imports to use correct module paths
- Added try-except blocks for both relative and absolute imports

### Issue 2: Package Path Resolution
Fixed in [start_server.py](start_server.py):
- Added parent directory to sys.path
- Changed to use `user_service.main:app` consistently
- Created alternative methods for different preferences

---

## Recommendations

### For Development (Daily Use):
```bash
cd c:/Programming/user_service
python start_server.py
```
Simple, reliable, cross-platform.

### For Production:
Edit [start_server.py](start_server.py) to disable reload:
```python
uvicorn.run(
    "user_service.main:app",
    host="0.0.0.0",
    port=8000,
    reload=False,  # ← Change to False
    log_level="info"
)
```

### For Testing/Development with Auto-Reload:
All provided methods include `--reload` flag by default.

---

## Summary

✅ **All fixed and working!**

- Server starts from inside user_service directory
- Multiple methods available for different preferences
- Both `user_service.main:app` and `main:app` module paths work
- All import errors resolved
- Database initializes correctly
- API endpoints accessible

Choose the method that works best for your workflow!

---

**Last Updated:** 2025-12-10
**Status:** ✅ Fully functional
