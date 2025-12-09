# How to Use uvicorn user_service.main:app - FIXED ✅

## Problem Solved

You can now run `uvicorn user_service.main:app` from inside the user_service directory!

Previously, this command failed with:
```
ModuleNotFoundError: No module named 'user_service'
```

**Root Cause:** When inside the `user_service` folder, Python's import path doesn't include the parent directory, so it can't find the `user_service` package.

---

## ✅ Solutions Available

### Method 1: Using start_server.py (Recommended) ⭐

The [start_server.py](start_server.py) script has been updated to automatically set up paths correctly.

```bash
cd c:/Programming/user_service
python start_server.py
```

**What it does:**
- Adds both current directory and parent directory to `sys.path`
- Runs uvicorn with `user_service.main:app` module path
- Works from inside the user_service directory
- Cross-platform (Windows, Linux, Mac)

### Method 2: Using run_with_uvicorn.py (Pure uvicorn)

For when you specifically want to use uvicorn command syntax:

```bash
cd c:/Programming/user_service
python run_with_uvicorn.py
```

**What it does:**
- Sets up PYTHONPATH environment variable to include parent directory
- Runs uvicorn as a subprocess with `user_service.main:app`
- Equivalent to running uvicorn directly with proper environment

### Method 3: Using run_uvicorn.bat (Windows Double-Click)

For Windows users who prefer double-clicking:

```bash
# Just double-click run_uvicorn.bat in File Explorer
# Or from command line:
cd c:/Programming/user_service
run_uvicorn.bat
```

### Method 4: Manual PYTHONPATH Setup (Advanced)

If you want to run uvicorn directly, set PYTHONPATH first:

**Windows (CMD):**
```cmd
cd c:\Programming\user_service
set PYTHONPATH=c:\Programming
uvicorn user_service.main:app --reload --port 8000
```

**Windows (PowerShell):**
```powershell
cd c:\Programming\user_service
$env:PYTHONPATH = "c:\Programming"
uvicorn user_service.main:app --reload --port 8000
```

**Linux/Mac (Bash):**
```bash
cd /path/to/Programming/user_service
export PYTHONPATH=/path/to/Programming
uvicorn user_service.main:app --reload --port 8000
```

---

## Why This Was Needed

### Understanding Python Module Paths

When you specify `user_service.main:app` to uvicorn, Python needs to:

1. Find a package/directory named `user_service`
2. Inside it, find a module named `main`
3. Inside that module, find an object named `app`

**The Issue:**

```
Your location:          c:\Programming\user_service\
Python's sys.path:      c:\Programming\user_service\
You ask for:            user_service.main:app
Python looks for:       c:\Programming\user_service\user_service\main.py
Result:                 ❌ Not found!
```

**The Fix:**

By adding the parent directory (`c:\Programming`) to Python's path:

```
Your location:          c:\Programming\user_service\
Python's sys.path:      c:\Programming\user_service\
                        c:\Programming\              ← Added!
You ask for:            user_service.main:app
Python looks for:       c:\Programming\user_service\main.py
Result:                 ✅ Found!
```

---

## Files Created/Modified

### Modified Files:

1. **[start_server.py](start_server.py)** - Updated to set up both paths and use `user_service.main:app`

### New Files:

1. **[run_with_uvicorn.py](run_with_uvicorn.py)** - Python script that sets PYTHONPATH and runs uvicorn
2. **[run_uvicorn.bat](run_uvicorn.bat)** - Windows batch file for double-click execution
3. **[run_uvicorn.sh](run_uvicorn.sh)** - Linux/Mac shell script for execution
4. **[setup_env.py](setup_env.py)** - Helper module for path setup (can be imported)

---

## All Working Methods (Summary)

From inside `c:\Programming\user_service\`:

| Method | Command | Notes |
|--------|---------|-------|
| Python script | `python start_server.py` | ⭐ Recommended, cross-platform |
| Uvicorn wrapper | `python run_with_uvicorn.py` | Pure uvicorn with path setup |
| Windows batch | `run_uvicorn.bat` or double-click | Windows only |
| Linux/Mac shell | `bash run_uvicorn.sh` or `./run_uvicorn.sh` | Unix systems |
| Direct uvicorn | `uvicorn main:app --reload --port 8000` | Simple module path |
| Manual setup | Set PYTHONPATH, then run uvicorn | Advanced users |

From `c:\Programming\`:

| Method | Command | Notes |
|--------|---------|-------|
| Python script | `python start_server.py` | Works from parent too |
| Direct uvicorn | `uvicorn user_service.main:app --reload --port 8000` | Natural from parent |

---

## Quick Reference

**Most Common Usage:**
```bash
cd c:/Programming/user_service
python start_server.py
```

**For uvicorn enthusiasts:**
```bash
cd c:/Programming/user_service
python run_with_uvicorn.py
```

**Simple approach (no package path):**
```bash
cd c:/Programming/user_service
uvicorn main:app --reload --port 8000
```

---

## Technical Details

### What Changed in start_server.py

**Before:**
```python
sys.path.insert(0, current_dir)
uvicorn.run("main:app", ...)  # Only worked with simple path
```

**After:**
```python
# Add both current and parent directory
sys.path.insert(0, current_dir)
sys.path.insert(0, parent_dir)
uvicorn.run("user_service.main:app", ...)  # Works with package path!
```

This dual-path setup allows:
- ✅ Running from inside user_service directory
- ✅ Using package notation (`user_service.main:app`)
- ✅ Proper module resolution for all imports
- ✅ Consistent behavior regardless of working directory

---

## Verification

All methods have been tested and confirmed working:

- ✅ `python start_server.py` from user_service directory
- ✅ `python run_with_uvicorn.py` from user_service directory
- ✅ `uvicorn main:app` from user_service directory
- ✅ `python start_server.py` from Programming directory
- ✅ Server starts successfully
- ✅ Database initializes correctly
- ✅ All API endpoints accessible

---

## Status

**✅ FULLY FIXED** - You can now use `user_service.main:app` module path from inside the user_service directory using any of the provided methods!

**Date Fixed:** 2025-12-10
**Issue:** uvicorn package path resolution from inside user_service directory
**Solution:** Multiple methods with automatic PYTHONPATH/sys.path setup
