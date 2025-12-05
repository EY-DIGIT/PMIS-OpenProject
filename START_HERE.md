# 🚀 OpenProject FastAPI Backend - START HERE

**Production-ready FastAPI backend with User & Project modules**

---

## ⚡ Quick Start (3 Commands)

```bash
# 1. Initialize database (creates tables + seeds 3 default roles)
python init_project_db.py

# 2. Start server
uvicorn main:app --reload --port 8000

# 3. Test API
# Browser: http://localhost:8000/api/docs
```

---

## ✅ What You Have

### Fully Implemented Modules

✅ **User Module** (15 endpoints)
- User CRUD, authentication, password management, locking

✅ **Project Module** (9 endpoints)
- Create, update, archive, copy projects with hierarchies

✅ **Membership Module** (5 endpoints)
- Add/remove members, role-based permissions

### Features
- 29 total API endpoints
- OpenProject API v3 compatible
- HAL+JSON response format
- Role-based access control (RBAC)
- 3 default roles, 9 permissions
- Nested set hierarchies
- Comprehensive tests

---

## 📚 Documentation

| File | Purpose |
|------|---------|
| **START_HERE.md** | ⭐ This file - Quick start |
| **COMPLETE_GUIDE.md** | Complete implementation & API reference |
| **FRONTEND_GUIDE.md** | Angular integration instructions |

---

## 🎯 Next Steps

### 1. Verify Installation

```bash
python verify_project_module.py
```

Expected: `5/5 checks passed`

### 2. Initialize Database

```bash
python init_project_db.py
```

Creates 6 tables + seeds 3 roles (Project admin, Member, Reader)

### 3. Start Server

```bash
uvicorn main:app --reload --port 8000
```

### 4. Test API

Visit: http://localhost:8000/api/docs

Try creating a project:
```json
POST /api/v3/projects
{
  "name": "My First Project",
  "identifier": "my-first-project",
  "public": false
}
```

---

## 🌐 Frontend Integration

### Connect Angular Frontend

1. **Start FastAPI backend**:
```bash
uvicorn main:app --reload --port 8000
```

2. **Configure Angular proxy** (`proxy.conf.json`):
```json
{
  "/api/v3": {
    "target": "http://localhost:8000",
    "secure": false,
    "changeOrigin": true
  }
}
```

3. **Update `angular.json`**:
```json
"serve": {
  "options": {
    "proxyConfig": "proxy.conf.json"
  }
}
```

4. **Start Angular**:
```bash
cd path/to/angular-frontend
npm start
```

5. **Access**: http://localhost:4200

**Full instructions**: See `FRONTEND_GUIDE.md`

---

## 📊 Quick Examples

### Create Project

```bash
curl -X POST "http://localhost:8000/api/v3/projects" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Project",
    "identifier": "my-project",
    "description": "Test project"
  }'
```

### List Projects

```bash
curl "http://localhost:8000/api/v3/projects?active=true"
```

### Add Member

```bash
curl -X POST "http://localhost:8000/api/v3/projects/1/memberships" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 2,
    "project_id": 1,
    "role_ids": [1]
  }'
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| No module errors | Run from `user_service` directory |
| No default roles | Run `python init_project_db.py` |
| Port in use | Use `--port 8001` |
| Database locked | Restart server |

---

## 🎉 You're Ready!

Everything is implemented and tested. Just run:

1. `python init_project_db.py` (one time)
2. `uvicorn main:app --reload --port 8000`
3. Open http://localhost:8000/api/docs

**For complete documentation, see `COMPLETE_GUIDE.md`**
