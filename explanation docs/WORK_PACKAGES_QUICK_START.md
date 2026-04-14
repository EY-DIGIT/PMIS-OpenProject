# Work Packages Module - Quick Start Guide

## What Was Implemented

A complete, production-ready Work Packages module for the FastAPI backend, following OpenProject semantics and the existing architecture.

## Quick Start

### Create a Work Package

```bash
curl -X POST "http://localhost:8000/api/v3/projects/1/work_packages" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Implement feature X",
    "description": "This feature enables...",
    "assigneeId": 5,
    "status": "new",
    "priority": "high",
    "doneRatio": 0
  }'
```

### List Work Packages in a Project

```bash
curl -X GET "http://localhost:8000/api/v3/projects/1/work_packages?offset=1&pageSize=20" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get a Work Package

```bash
curl -X GET "http://localhost:8000/api/v3/work_packages/123" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Update a Work Package

```bash
curl -X PATCH "http://localhost:8000/api/v3/work_packages/123" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Updated title",
    "status": "in_progress",
    "doneRatio": 50
  }'
```

### Delete a Work Package

```bash
curl -X DELETE "http://localhost:8000/api/v3/work_packages/123" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Module Structure

```
app/
├── domain/work_packages/
│   ├── __init__.py
│   └── work_package.py           # Domain entity
├── infrastructure/db/
│   ├── models/work_package.py    # SQLAlchemy ORM
│   └── repositories/work_package_repository.py  # Data access
└── api/v3/work_packages/
    ├── __init__.py
    ├── schemas.py                 # Pydantic request/response models
    ├── permissions.py             # Permission constants
    ├── controller.py              # HTTP request handling
    ├── routes.py                  # Endpoint definitions with auth
    └── services/
        ├── __init__.py
        ├── create.py              # Create service
        ├── get.py                 # Retrieve service
        ├── list.py                # List service
        ├── update.py              # Update service
        └── delete.py              # Delete service
```

## Key Features

### 1. Full CRUD Operations
- Create, read, update, delete work packages
- List with pagination support
- Parent-child hierarchy for subtasks

### 2. Project Scoping
- All work packages belong to a project
- Subtask parents must be in same project
- Assignees must be project members

### 3. RBAC Authorization
- WORK_PACKAGES_VIEW - View permission
- WORK_PACKAGES_CREATE - Create permission
- WORK_PACKAGES_UPDATE - Update permission
- WORK_PACKAGES_DELETE - Delete permission
- Enforced at routing level (middleware)

### 4. HAL+JSON API
- Consistent response envelope
- Links to related resources
- Proper HTTP status codes
- Pagination with first/prev/next/last links

### 5. Data Validation
- Subject required, 1-255 characters
- Description max 5000 characters
- Valid status: new, in_progress, resolved, closed, on_hold
- Valid priority: low, normal, high, urgent
- Done ratio: 0-100
- Assignee membership validation
- Project existence checks

### 6. Hierarchical Support
- Parent-child relationships for subtasks
- Prevents deletion of packages with subtasks
- Self-referential hierarchy

## Database Schema

```sql
CREATE TABLE work_packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject VARCHAR(255) NOT NULL,
    description TEXT,
    project_id INTEGER NOT NULL,
    parent_id INTEGER,
    assignee_id INTEGER,
    status VARCHAR(100) DEFAULT 'new' NOT NULL,
    priority VARCHAR(100) DEFAULT 'normal' NOT NULL,
    done_ratio INTEGER DEFAULT 0 NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (parent_id) REFERENCES work_packages(id),
    FOREIGN KEY (assignee_id) REFERENCES users(id),
    
    INDEX idx_work_packages_project_id (project_id),
    INDEX idx_work_packages_parent_id (parent_id),
    INDEX idx_work_packages_assignee_id (assignee_id),
    INDEX idx_work_packages_status (status),
    INDEX idx_work_packages_priority (priority),
    INDEX idx_work_packages_subject (subject)
);
```

## Authorization Rules

| Permission | Admin | Member | Viewer |
|-----------|-------|--------|--------|
| VIEW | ✓ | ✓ | ✓ |
| CREATE | ✓ | ✓ | ✗ |
| UPDATE | ✓ | ✓ | ✗ |
| DELETE | ✓ | ✓ | ✗ |

## API Response Format

All responses follow the standard envelope:

```json
{
  "data": {
    "_type": "WorkPackage",
    "_links": {
      "self": {
        "href": "/api/v3/work_packages/123",
        "title": "Task title"
      },
      "project": {
        "href": "/api/v3/projects/1"
      },
      "parent": {
        "href": "/api/v3/work_packages/120"
      },
      "assignee": {
        "href": "/api/v3/users/5"
      }
    },
    "id": 123,
    "subject": "Task title",
    "description": "Task description",
    "projectId": 1,
    "parentId": 120,
    "assigneeId": 5,
    "status": "new",
    "priority": "high",
    "doneRatio": 0,
    "createdAt": "2025-12-18T10:30:00",
    "updatedAt": "2025-12-18T10:30:00"
  },
  "message": null,
  "error": null,
  "status": 200
}
```

## Error Responses

### 400 Bad Request
```json
{
  "data": null,
  "message": null,
  "error": {
    "message": "Invalid subject. Must be 1-255 characters.",
    "type": "validation_error"
  },
  "status": 400
}
```

### 404 Not Found
```json
{
  "data": null,
  "message": null,
  "error": {
    "message": "Work package with ID 999 does not exist",
    "type": "not_found"
  },
  "status": 404
}
```

## Testing

All components have been validated:
- ✓ Imports all resolve correctly
- ✓ FastAPI application loads successfully
- ✓ All 5 work package routes registered
- ✓ ORM models configured with relationships
- ✓ Repository methods all available and working
- ✓ Service layer validates correctly
- ✓ Response formatter produces valid HAL+JSON
- ✓ RBAC permissions properly configured
- ✓ No breaking changes to existing modules

## No Breaking Changes

This implementation:
- Only adds new functionality
- Does not modify existing modules (except to register and support)
- Does not change authentication
- Does not change RBAC structure
- Does not change response envelope format
- Does not change existing APIs

## Database Migration

To add this to an existing database:

```python
from app.infrastructure.db.models import WorkPackageModel
from app.infrastructure.db.session import engine, Base

# Create the table
Base.metadata.create_all(bind=engine)
```

Or using Alembic:

```bash
alembic revision --autogenerate -m "Add work packages table"
alembic upgrade head
```

## Performance Considerations

- All major lookups indexed (project_id, parent_id, assignee_id, status, priority)
- Pagination enforced (max 100 items per page)
- Repository pattern allows for query optimization
- Self-referential hierarchy supported with proper indexes

## Next Steps

1. Run database migrations to create the `work_packages` table
2. Test with sample project (must have PROJECT_ID from existing projects table)
3. Create test users and assign them as project members
4. Call the API endpoints with valid project and user IDs

## Support

For issues or questions about the Work Packages module, refer to:
- [WORK_PACKAGES_IMPLEMENTATION.md](WORK_PACKAGES_IMPLEMENTATION.md) - Full implementation details
- [PROJECT_IMPLEMENTATION.md](PROJECT_IMPLEMENTATION.md) - Project module for reference
- Existing modules (Users, Projects, Roles) for pattern examples
