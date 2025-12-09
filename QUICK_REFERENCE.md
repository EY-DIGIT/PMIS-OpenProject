# Quick Reference - OpenProject Module

## 🚀 Getting Started (3 Steps)

### 1. Initialize Database
```bash
cd c:\Programming\user_service
python init_db_simple.py
```

### 2. Start Server
```bash
cd c:\Programming\user_service
python start_server.py
```
**Or simply double-click** `run.bat` in Windows!

### 3. Access API
- Swagger UI: http://localhost:8000/api/docs
- API Root: http://localhost:8000/

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | Current status, what's working |
| [HOW_TO_RUN.md](HOW_TO_RUN.md) | Detailed running instructions |
| [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) | Full API and model reference |
| [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) | Angular integration guide |
| [START_HERE.md](START_HERE.md) | Quick start guide |

---

## 🧪 Testing

### Test Database & Models (No Server)
```bash
python test_project_direct.py
```

### Test API (Server Required)
```bash
# Start server first
cd c:\Programming\user_service
python start_server.py

# Then open Swagger UI
http://localhost:8000/api/docs
```

---

## 🔑 Key API Endpoints

### Projects
```
GET    /api/v3/projects              # List projects
POST   /api/v3/projects              # Create project
GET    /api/v3/projects/{id}         # Get project
PATCH  /api/v3/projects/{id}         # Update project
DELETE /api/v3/projects/{id}         # Delete project
POST   /api/v3/projects/{id}/archive # Archive
```

### Memberships
```
GET    /api/v3/projects/{id}/memberships # List members
POST   /api/v3/projects/{id}/memberships # Add member
PATCH  /api/v3/memberships/{id}          # Update roles
DELETE /api/v3/memberships/{id}          # Remove member
```

---

## 🗄️ Database

**Tables Created:** 10
- projects, members, member_roles, roles, role_permissions
- enabled_modules, users, user_preferences, user_passwords, api_tokens

**Default Roles:** 3
- Project admin (9 permissions)
- Member (3 permissions)
- Reader (2 permissions)

**Database File:** `c:\Programming\user_service\openproject.db`

---

## 💻 Example Usage

### Create a Project (cURL)
```bash
curl -X POST "http://localhost:8000/api/v3/projects" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Project",
    "identifier": "my-project",
    "description": "A test project",
    "public": true
  }'
```

### List Projects (cURL)
```bash
curl http://localhost:8000/api/v3/projects
```

### Using Python Requests
```python
import requests

# Create project
response = requests.post(
    "http://localhost:8000/api/v3/projects",
    json={
        "name": "My Project",
        "identifier": "my-project",
        "public": True
    }
)
print(response.json())

# List projects
projects = requests.get("http://localhost:8000/api/v3/projects")
print(projects.json())
```

---

## 🎯 Project Structure

```
user_service/
├── models/              # SQLAlchemy models
│   ├── project.py      # Project model
│   ├── member.py       # Member, Role, MemberRole models
│   └── enabled_module.py
├── services/           # Business logic
│   ├── project_service.py
│   └── member_service.py
├── routers/            # API endpoints
│   ├── projects.py     # Project endpoints
│   └── members.py      # Membership endpoints
├── schemas/            # Pydantic validation
├── database.py         # Database setup
├── main.py            # FastAPI app
└── openproject.db     # SQLite database
```

---

## ✅ Status Checklist

- [x] Database initialized (10 tables)
- [x] Default roles seeded (3 roles)
- [x] Models working (all relationships)
- [x] Services operational (Project, Member)
- [x] API endpoints functional (13 endpoints)
- [x] Server starts successfully
- [x] Swagger UI available
- [x] Direct testing working
- [x] Documentation complete
- [x] Frontend guide provided

---

## 🔧 Troubleshooting

### Server won't start
- Check you're in correct directory: `c:\Programming`
- Command: `uvicorn user_service.main:app --port 8000`

### Database not found
- Run: `python init_db_simple.py`

### Import errors
- All import errors have been fixed with try/except fallbacks

### Port already in use
- Change port: `--port 8001`
- Or stop other server using port 8000

---

## 📞 Quick Commands

```bash
# Initialize database (first time only)
cd c:\Programming\user_service && python init_db_simple.py

# Test models directly (no server needed)
cd c:\Programming\user_service && python test_project_direct.py

# Start server (recommended - works from inside folder)
cd c:\Programming\user_service && python start_server.py

# Or just double-click run.bat in Windows
```

---

**Project Status:** ✅ FULLY OPERATIONAL

All components tested and working. Ready for development and frontend integration.
