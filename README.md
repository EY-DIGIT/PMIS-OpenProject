# PMIS Python - Project Management Information System

Production-ready Python FastAPI backend for OpenProject-compatible project management.

## Quick Start

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Default credentials: `admin` / `admin123`

## Features

- **User Management** - CRUD, JWT authentication, password management
- **Project Management** - Projects with status, ownership, categories, date tracking
- **Work Packages** - Tasks, issues, subtasks with project scoping
- **Meetings** - Meetings, participants, agenda items
- **Roles** - Global role definitions with RBAC enforcement
- **Project Members** - User-project membership management
- **Work Package Types** - Configurable types (Task, Bug, Feature, Story, Milestone)

## Tech Stack

FastAPI 0.135 | SQLAlchemy 2.0 | Pydantic 2.12 | SQLite/PostgreSQL | JWT (HS256) | Argon2id

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Detailed Documentation

All project documentation is consolidated in the [`consolidated/`](consolidated/) folder:

| Document | Description |
|----------|-------------|
| [Architecture & API Reference](consolidated/ARCHITECTURE_AND_API_REFERENCE.md) | System architecture, database schema, all 45+ API endpoints, response formats, RBAC permissions |
| [Authentication & Security](consolidated/AUTHENTICATION_AND_SECURITY.md) | JWT auth flow, RBAC, Swagger UI setup, frontend integration, security checklist |
| [Testing & Quality](consolidated/TESTING_AND_QUALITY.md) | Test suites, coverage, code issues found/fixed, quality assessment |
| [Deployment & Integration](consolidated/DEPLOYMENT_AND_INTEGRATION.md) | Installation, configuration, deployment checklist, frontend integration, monitoring |

## License

MIT
