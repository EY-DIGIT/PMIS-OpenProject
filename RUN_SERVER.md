# How to Run the OpenProject Server

This guide shows you **3 easy ways** to start the server from inside the `user_service` folder.

---

## Prerequisites

Make sure you've initialized the database first (only needed once):

```bash
cd c:\Programming\user_service
python init_db_simple.py
```

---

## Method 1: Using Python Script (Cross-Platform) ⭐ Recommended

### From Inside the Project Folder

```bash
cd c:\Programming\user_service
python start_server.py
```

### From Anywhere

```bash
python c:\Programming\user_service\start_server.py
```

**Advantages:**
- ✅ Works on Windows, Linux, Mac
- ✅ Can be run from any directory
- ✅ Handles all path setup automatically
- ✅ Easy to share with team

---

## Method 2: Using Batch File (Windows Only)

### Double-Click

Simply **double-click** `run.bat` in File Explorer

### Or Run from Command Line

```bash
cd c:\Programming\user_service
run.bat
```

**Advantages:**
- ✅ Super easy - just double-click
- ✅ No need to type commands
- ✅ Great for non-technical users

---

## Method 3: Using Shell Script (Linux/Mac/Git Bash)

```bash
cd c:\Programming\user_service
bash run.sh
```

Or make it executable first:

```bash
chmod +x run.sh
./run.sh
```

---

## Method 4: Direct uvicorn Command (Advanced)

If you prefer the raw uvicorn command:

```bash
cd c:\Programming\user_service
uvicorn main:app --reload --port 8000
```

**Note:** This works because we're running from inside the folder where `main.py` is located.

---

## Verify Server is Running

Once started, you should see:

```
============================================================
Starting OpenProject FastAPI Server
============================================================

Server will be available at:
  - API Root: http://localhost:8000/
  - Swagger UI: http://localhost:8000/api/docs
  - ReDoc: http://localhost:8000/api/redoc

Press CTRL+C to stop the server
============================================================

INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

Then open your browser and visit:
- **Swagger UI**: http://localhost:8000/api/docs
- **API Root**: http://localhost:8000/

---

## Troubleshooting

### Problem: "ModuleNotFoundError"

**Solution:** Make sure you're running from the correct directory:

```bash
cd c:\Programming\user_service
python start_server.py
```

### Problem: "Port 8000 already in use"

**Solution:** Either:
1. Stop the existing server (find it and press CTRL+C)
2. Or use a different port by editing `start_server.py` and changing `port=8000` to `port=8001`

### Problem: "Database not found"

**Solution:** Initialize the database first:

```bash
cd c:\Programming\user_service
python init_db_simple.py
```

---

## Sharing Your Project

When sharing your code (e.g., on GitHub), include these files:

```
user_service/
├── start_server.py    ← Main startup script
├── run.bat            ← Windows double-click option
├── run.sh             ← Linux/Mac script
├── main.py            ← FastAPI application
├── init_db_simple.py  ← Database initialization
└── RUN_SERVER.md      ← This file
```

**Instructions for others:**

1. Clone/download the code
2. Install dependencies: `pip install -r requirements.txt`
3. Initialize database: `python init_db_simple.py`
4. Start server: `python start_server.py` or double-click `run.bat`

---

## Quick Reference

```bash
# Initialize database (first time only)
cd c:\Programming\user_service
python init_db_simple.py

# Start server (every time)
python start_server.py

# Stop server
Press CTRL+C

# Access API
http://localhost:8000/api/docs
```

---

## Different Environments

### Development (with auto-reload)
```bash
python start_server.py
```
The server automatically restarts when you change code files.

### Production (without auto-reload)
Edit `start_server.py` and change:
```python
reload=True,  # Change to False for production
```

---

## What start_server.py Does

The `start_server.py` script:
1. ✅ Sets up the correct Python path
2. ✅ Changes to the correct directory
3. ✅ Starts uvicorn with optimal settings
4. ✅ Shows helpful information
5. ✅ Works from any location

You can now **share your entire `user_service` folder** and others can run it easily!

---

**Status:** ✅ Ready to run from inside the project folder
**Last Updated:** 2025-12-06
