# Troubleshooting Guide

## Error: ModuleNotFoundError: No module named 'user_service'

This error occurs when running uvicorn from the wrong directory.

### Solution 1: Use the app.py entry point (RECOMMENDED)

From **inside** the `user_service` directory:

```bash
cd user_service
uvicorn app:app --reload
```

Or use the startup scripts:
```bash
# Windows
START_SERVER.bat

# Linux/Mac
bash START_SERVER.sh
```

### Solution 2: Run from parent directory

From the **parent directory** (C:\Programming):

```bash
cd C:\Programming
uvicorn user_service.main:app --reload
```

### Solution 3: Use Python module syntax

From **inside** the `user_service` directory:

```bash
cd user_service
python -m uvicorn app:app --reload
```

### Solution 4: Use the run_server.py script

```bash
cd user_service
python run_server.py
```

---

## Error: ImportError with relative imports

If you see errors like `ImportError: attempted relative import beyond top-level package`:

### Solution: Check your working directory

Make sure you're in the correct directory:

```bash
# Should be in user_service directory
pwd  # Should show: .../user_service

# Or should be in parent directory
pwd  # Should show: .../Programming
```

---

## Error: No module named 'fastapi'

### Solution: Install dependencies

```bash
pip install -r requirements_api.txt
```

Or install individually:

```bash
pip install fastapi uvicorn sqlalchemy pydantic python-multipart "pydantic[email]"
```

---

## Error: Can't connect to database

### Solution 1: Check database file

The SQLite database is created automatically. Check if it exists:

```bash
ls openproject.db
```

### Solution 2: Initialize database manually

```bash
python -c "from user_service.database import init_db; init_db()"
```

Or from within user_service directory:

```bash
cd ..
python -c "from user_service.database import init_db; init_db()"
cd user_service
```

---

## Port Already in Use

### Error Message:
```
OSError: [Errno 48] Address already in use
```

### Solution: Use a different port

```bash
uvicorn app:app --reload --port 8001
```

Or kill the process using port 8000:

**Windows:**
```bash
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Linux/Mac:**
```bash
lsof -ti:8000 | xargs kill -9
```

---

## CORS Issues with Frontend

### Symptoms:
- Frontend can't connect to API
- CORS errors in browser console

### Solution: Update CORS settings

Edit [main.py](main.py:69) and add your frontend URL:

```python
allow_origins=[
    "http://localhost:4200",  # Angular dev server
    "http://localhost:3000",  # Your frontend
    "https://your-domain.com"
]
```

---

## Authentication Issues

### Error: 401 Unauthorized

#### Solution 1: Check authentication method

The API supports multiple auth methods:

**API Key:**
```bash
curl -u apikey:YOUR_API_KEY http://localhost:8000/api/v3/users/me
```

**Bearer Token:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v3/users/me
```

#### Solution 2: Login first

```bash
curl -X POST http://localhost:8000/api/v3/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

---

## Database Migration Issues

### Error: Table already exists

If you need to reset the database:

```bash
# Backup first!
cp openproject.db openproject.db.backup

# Delete and reinitialize
rm openproject.db
python -c "from user_service.database import init_db; init_db()"
```

---

## Import Errors in API Files

### Error: Cannot import name 'X' from 'user_service'

This usually means the module structure is incorrect.

### Solution: Verify __init__.py files

Check that these files exist:
- `user_service/__init__.py`
- `user_service/api/__init__.py`
- `user_service/models/__init__.py`
- `user_service/services/__init__.py`

---

## Running from Different Directories

### Summary of Methods

| Working Directory | Command |
|------------------|---------|
| `C:\Programming\user_service` | `uvicorn app:app --reload` |
| `C:\Programming\user_service` | `python run_server.py` |
| `C:\Programming\user_service` | `.\START_SERVER.bat` (Windows) |
| `C:\Programming\user_service` | `bash START_SERVER.sh` (Linux/Mac) |
| `C:\Programming` | `uvicorn user_service.main:app --reload` |

---

## Testing the Installation

### Quick Test

```bash
# Test 1: Check if server starts
uvicorn app:app --reload

# Test 2: Check API endpoint (in another terminal)
curl http://localhost:8000/health

# Expected output:
# {"status":"healthy","service":"OpenProject User Service","version":"1.0.0"}
```

### Test 3: Access documentation

Open in browser:
- http://localhost:8000/api/docs

You should see the interactive API documentation.

---

## Common Issues Checklist

- [ ] Are you in the correct directory?
- [ ] Have you installed all dependencies?
- [ ] Is the port available (not in use)?
- [ ] Does openproject.db exist or can be created?
- [ ] Are all __init__.py files present?
- [ ] Is Python 3.8+ installed?

---

## Debug Mode

To get more detailed error messages:

```bash
# Enable debug logging
uvicorn app:app --reload --log-level debug
```

Or set in code:

```python
# main.py
logging.basicConfig(level=logging.DEBUG)
```

---

## Getting Help

If you're still having issues:

1. Check the error message carefully
2. Verify your Python version: `python --version` (should be 3.8+)
3. Check installed packages: `pip list | grep fastapi`
4. Review the [API_README.md](API_README.md)
5. Check the example scripts work: `python example_api_usage.py`

---

## Quick Reset

If everything is broken, start fresh:

```bash
# 1. Go to user_service directory
cd user_service

# 2. Remove database
rm -f openproject.db

# 3. Reinstall dependencies
pip install -r requirements_api.txt

# 4. Use the startup script
# Windows:
START_SERVER.bat

# Linux/Mac:
bash START_SERVER.sh
```

---

## Environment-Specific Issues

### Windows

- Use backslashes in paths or forward slashes
- Make sure you're in a virtual environment if required
- Check Windows Firewall isn't blocking port 8000

### Linux/Mac

- May need `python3` instead of `python`
- May need `pip3` instead of `pip`
- Check file permissions: `chmod +x START_SERVER.sh`

### Virtual Environments

If using a virtual environment:

```bash
# Activate first
# Windows:
projenv\Scripts\activate

# Linux/Mac:
source projenv/bin/activate

# Then run the server
uvicorn app:app --reload
```

---

## Success Indicators

When everything is working correctly, you should see:

```
INFO:     Will watch for changes in these directories: ['C:\\Programming\\user_service']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using WatchFiles
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Initializing database...
INFO:     Database initialized successfully
INFO:     Application startup complete.
```

And you can access:
- http://localhost:8000 - Root endpoint
- http://localhost:8000/health - Health check
- http://localhost:8000/api/docs - Interactive API docs
