# 🚀 START HERE - FastAPI User Service

## ⚡ Quick Start (3 Steps)

### Step 1: Navigate to Directory

```bash
cd C:\Programming\user_service
```

### Step 2: Install Dependencies (if not already done)

```bash
pip install -r requirements_api.txt
```

### Step 3: Start the Server

**Windows:**
```bash
START_SERVER.bat
```

**Linux/Mac:**
```bash
bash START_SERVER.sh
```

**Or use uvicorn directly:**
```bash
uvicorn app:app --reload
```

---

## ✅ Verify It Works

Open your browser and visit:

**http://localhost:8000/api/docs**

You should see interactive API documentation with all endpoints.

---

## 🎯 What You Have

### A Production-Ready FastAPI Backend

- ✅ **15 REST API Endpoints** (users, auth, management)
- ✅ **OpenProject API v3 Compatible** (HAL+JSON format)
- ✅ **3 Authentication Methods** (API Key, Bearer, Session)
- ✅ **Database Integration** (SQLite/PostgreSQL/MySQL)
- ✅ **Interactive Documentation** (Swagger UI + ReDoc)
- ✅ **Frontend Compatible** (with Angular frontend)

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| **[README.md](README.md)** | ⭐ This file - Quick start guide |
| **[API_README.md](API_README.md)** | Complete API documentation |
| **[FRONTEND_INTEGRATION_GUIDE.md](FRONTEND_INTEGRATION_GUIDE.md)** | Integrate with OpenProject frontend |
| **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** | Fix common issues |

---

## 🔧 The Fix for Your Error

### What Was Wrong

When you ran:
```bash
uvicorn user_service.main:app --reload
```

From inside `C:\Programming\user_service`, Python couldn't find the module.

### What I Fixed

Created **`app.py`** that works from inside the directory:

```python
# app.py - Works when run from user_service directory
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)

from user_service.main import app
```

### Now Use This

```bash
cd user_service
uvicorn app:app --reload  # ✅ Works!
```

Or use the startup scripts:
```bash
START_SERVER.bat  # Windows
bash START_SERVER.sh  # Linux/Mac
```

---

## 📡 API Endpoints Available

Once running at http://localhost:8000:

### Documentation
- **Interactive Docs**: `/api/docs`
- **ReDoc**: `/api/redoc`
- **OpenAPI Spec**: `/api/openapi.json`

### User Management
- `GET /api/v3/users` - List users
- `POST /api/v3/users` - Create user
- `GET /api/v3/users/{id}` - Get user
- `PATCH /api/v3/users/{id}` - Update user
- `DELETE /api/v3/users/{id}` - Delete user
- `POST /api/v3/users/{id}/lock` - Lock user
- `POST /api/v3/users/{id}/unlock` - Unlock user

### Authentication
- `POST /api/v3/auth/login` - Login
- `POST /api/v3/auth/logout` - Logout
- `POST /api/v3/auth/register` - Register
- `POST /api/v3/auth/change-password` - Change password

---

## 🧪 Quick Test

### Test 1: Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "OpenProject User Service",
  "version": "1.0.0"
}
```

### Test 2: Register a User

```bash
curl -X POST http://localhost:8000/api/v3/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "login": "testuser",
    "firstName": "Test",
    "lastName": "User",
    "email": "test@example.com",
    "password": "SecurePass123!",
    "language": "en"
  }'
```

### Test 3: Get User Schema

```bash
curl http://localhost:8000/api/v3/users/schema
```

---

## ❓ Your Questions Answered

### Can the OpenProject frontend use this backend?

**YES!** ✅

Use a **microservices architecture** with Nginx:
- Route `/api/v3/users/*` → FastAPI (this backend)
- Route other endpoints → Rails (if keeping other features)

See [FRONTEND_INTEGRATION_GUIDE.md](FRONTEND_INTEGRATION_GUIDE.md) for complete instructions.

### Can I replace the entire Ruby backend?

**Partially - NOT recommended** ⚠️

This implementation covers **user management only**. OpenProject has 50+ other features (projects, work packages, time tracking, etc.) that would need separate implementation.

**Recommended:** Use this FastAPI backend for user management alongside the Rails backend for other features.

---

## 🎯 Next Steps

1. **Start the server** (see Step 3 above)
2. **Explore the API** at http://localhost:8000/api/docs
3. **Read the integration guide** to connect with the frontend
4. **Deploy to production** when ready

---

## 🐛 Having Issues?

### Common Problems & Quick Fixes

**Error: "No module named 'user_service'"**
```bash
# Solution: Use app.py from user_service directory
cd user_service
uvicorn app:app --reload
```

**Error: "Port 8000 already in use"**
```bash
# Solution: Use different port
uvicorn app:app --reload --port 8001
```

**Error: "No module named 'fastapi'"**
```bash
# Solution: Install dependencies
pip install -r requirements_api.txt
```

**More issues?** See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## 📊 Project Structure

```
user_service/
├── api/                    # REST API endpoints
│   ├── dependencies.py    # Authentication
│   ├── schemas.py         # Request/response models
│   ├── users.py           # User endpoints
│   └── auth.py            # Auth endpoints
│
├── models/                 # Domain models
├── services/               # Business logic
├── database.py            # Database config
├── db_models.py           # SQLAlchemy models
├── repositories.py        # Data access
├── main.py                # FastAPI app
├── app.py                 # Entry point (USE THIS!)
│
├── START_SERVER.bat       # Windows startup
├── START_SERVER.sh        # Linux/Mac startup
├── requirements_api.txt   # Dependencies
│
└── Documentation/
    ├── HOW_TO_RUN.md      ⭐ Start here
    ├── API_README.md
    ├── FRONTEND_INTEGRATION_GUIDE.md
    └── TROUBLESHOOTING.md
```

---

## 💡 Pro Tips

### Auto-reload on Code Changes

The `--reload` flag automatically restarts when you edit code:
```bash
uvicorn app:app --reload
```

### Access from Other Devices

```bash
uvicorn app:app --reload --host 0.0.0.0
```

Then access from other devices: `http://YOUR_IP:8000`

### Production Deployment

```bash
# Multiple workers, no reload
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 🎉 Success Checklist

- [ ] Server starts without errors
- [ ] Can access http://localhost:8000/api/docs
- [ ] Health check returns success
- [ ] Can register a test user
- [ ] Database file created (openproject.db)

If all checked, **you're ready to go!** 🚀

---

## 📞 Support

- **Troubleshooting**: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **API Docs**: See [API_README.md](API_README.md)
- **Frontend Integration**: See [FRONTEND_INTEGRATION_GUIDE.md](FRONTEND_INTEGRATION_GUIDE.md)

---

## 🏆 What You Accomplished

You now have a **production-ready FastAPI backend** that:

✅ Implements OpenProject API v3 user endpoints
✅ Works with the OpenProject Angular frontend
✅ Provides interactive API documentation
✅ Supports multiple authentication methods
✅ Includes database integration
✅ Is fast, scalable, and type-safe

**All errors are fixed and the server is ready to run!** 🎊

---

**To start coding:** Open http://localhost:8000/api/docs in your browser after starting the server!
