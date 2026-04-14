# Work Packages - Developer Quick Reference

## File Locations

```
New Files:
- app/domain/work_packages/
- app/infrastructure/db/models/work_package.py
- app/infrastructure/db/repositories/work_package_repository.py
- app/api/v3/work_packages/

Modified Files:
- app/core/rbac.py                    (+4 permissions)
- app/core/response.py                (+1 formatter function)
- app/api/router.py                   (+2 router registrations)
- app/infrastructure/db/models/__init__.py
- app/infrastructure/db/repositories/project_member_repository.py
```

## Core Classes

### WorkPackage (Domain)
```python
from app.domain.work_packages.work_package import WorkPackage

wp = WorkPackage(
    id=1, subject="Task", description="Desc",
    project_id=1, parent_id=None, assignee_id=1,
    status="new", priority="high", done_ratio=0,
    created_at=datetime.now(), updated_at=datetime.now()
)
wp.to_dict()           # Convert to dict
wp.is_subtask()        # Check if has parent
wp.is_completed()      # Check if done_ratio >= 100
```

### WorkPackageModel (ORM)
```python
from app.infrastructure.db.models.work_package import WorkPackageModel

# Used internally by SQLAlchemy
# Fields: id, subject, description, project_id, parent_id, assignee_id,
#         status, priority, done_ratio, created_at, updated_at
# Relationships: project, parent, assignee
```

### WorkPackageRepository (Data Access)
```python
from app.infrastructure.db.repositories.work_package_repository import WorkPackageRepository
from app.infrastructure.db.session import SessionLocal

db = SessionLocal()
repo = WorkPackageRepository(db)

# Methods:
repo.create(subject, project_id, ...)           # Create
repo.get_by_id(wp_id)                          # Get by ID
repo.get_by_project_and_id(proj_id, wp_id)    # Get in project
repo.list_by_project(proj_id, offset, limit)   # List with pagination
repo.list_subtasks(parent_id)                  # Get all subtasks
repo.exists_by_id(wp_id)                       # Check exists
repo.exists_by_project_and_id(proj_id, wp_id) # Check in project
repo.update(wp_id, **fields)                   # Update
repo.delete(wp_id)                             # Delete
repo.project_exists(proj_id)                   # Verify project
repo.user_exists(user_id)                      # Verify user
```

### Services (Business Logic)
```python
from app.api.v3.work_packages.services import (
    create_work_package,
    get_work_package_by_id,
    get_work_package_by_project_and_id,
    list_work_packages_by_project,
    update_work_package,
    delete_work_package
)

# All return ServiceResult[T]
result = create_work_package(db, project_id, subject, ...)
if result.is_success():
    wp = result.data
else:
    error = result.error
```

### Schemas (Validation)
```python
from app.api.v3.work_packages.schemas import (
    WorkPackageCreateRequest,
    WorkPackageUpdateRequest,
    WorkPackageListQuery
)

# Create
req = WorkPackageCreateRequest(
    subject="...",
    description="...",
    parentId=None,
    assigneeId=5,
    status="new",
    priority="high",
    doneRatio=0
)

# Update (all fields optional)
req = WorkPackageUpdateRequest(
    subject="...",
    doneRatio=50
)

# List
query = WorkPackageListQuery(offset=1, pageSize=20, parentId=None)
```

### Controller (HTTP)
```python
from app.api.v3.work_packages.controller import WorkPackageController

# Used by routes
WorkPackageController.create_in_project(request, project_id, data, db)
WorkPackageController.get(request, wp_id, db)
WorkPackageController.get_in_project(request, project_id, wp_id, db)
WorkPackageController.list(request, project_id, query, db)
WorkPackageController.update(request, wp_id, data, db)
WorkPackageController.delete(request, wp_id, db)
```

## Routes & Permissions

```python
from app.api.v3.work_packages.permissions import (
    WORK_PACKAGES_VIEW,
    WORK_PACKAGES_CREATE,
    WORK_PACKAGES_UPDATE,
    WORK_PACKAGES_DELETE
)

# Routes automatically have permission checks via decorators
# @require_permission(WORK_PACKAGES_CREATE)
# @require_permission(WORK_PACKAGES_VIEW)
# etc.
```

## Response Format

Work package HAL+JSON responses are assembled in the Work Package controller. Controllers build the HAL payload
and return it via `BaseController.ok` / `BaseController.created`.

## Common Patterns

### Create a Work Package
```python
from app.api.v3.work_packages.services.create import create_work_package
from app.infrastructure.db.session import SessionLocal

db = SessionLocal()
result = create_work_package(
    db=db,
    project_id=1,
    subject="New task",
    description="Description",
    assignee_id=5,
    status="new",
    priority="normal",
    done_ratio=0
)

if result.is_success():
    print(f"Created: {result.data.subject}")
else:
    print(f"Error: {result.error}")
```

### Update a Work Package
```python
from app.api.v3.work_packages.services.update import update_work_package

result = update_work_package(
    db=db,
    work_package_id=123,
    status="in_progress",
    done_ratio=50
)
```

### List Work Packages
```python
from app.api.v3.work_packages.services.list import list_work_packages_by_project

result = list_work_packages_by_project(
    db=db,
    project_id=1,
    offset=1,
    limit=20,
    parent_id=None
)

if result.is_success():
    work_packages, total = result.data
    for wp in work_packages:
        print(f"{wp.subject} - {wp.status}")
```

## Database Schema

```sql
CREATE TABLE work_packages (
    id INTEGER PRIMARY KEY,
    subject VARCHAR(255) NOT NULL,
    description TEXT,
    project_id INTEGER NOT NULL,
    parent_id INTEGER,
    assignee_id INTEGER,
    status VARCHAR(100) DEFAULT 'new',
    priority VARCHAR(100) DEFAULT 'normal',
    done_ratio INTEGER DEFAULT 0,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (parent_id) REFERENCES work_packages(id),
    FOREIGN KEY (assignee_id) REFERENCES users(id)
);

CREATE INDEX idx_work_packages_project_id ON work_packages(project_id);
CREATE INDEX idx_work_packages_parent_id ON work_packages(parent_id);
CREATE INDEX idx_work_packages_assignee_id ON work_packages(assignee_id);
CREATE INDEX idx_work_packages_status ON work_packages(status);
CREATE INDEX idx_work_packages_priority ON work_packages(priority);
CREATE INDEX idx_work_packages_subject ON work_packages(subject);
```

## Validation Rules

| Field | Rules |
|-------|-------|
| subject | Required, 1-255 chars |
| description | Optional, max 5000 chars |
| project_id | Required, must exist |
| parent_id | Optional, must exist, same project |
| assignee_id | Optional, must exist, must be member |
| status | new, in_progress, resolved, closed, on_hold |
| priority | low, normal, high, urgent |
| done_ratio | 0-100 |

## Permissions

```python
from app.core.rbac import Permission, Role, ROLE_PERMISSIONS

Permission.WORK_PACKAGES_VIEW      # View
Permission.WORK_PACKAGES_CREATE    # Create
Permission.WORK_PACKAGES_UPDATE    # Update
Permission.WORK_PACKAGES_DELETE    # Delete

ROLE_PERMISSIONS[Role.ADMIN]       # All
ROLE_PERMISSIONS[Role.MEMBER]      # All
ROLE_PERMISSIONS[Role.VIEWER]      # VIEW only
ROLE_PERMISSIONS[Role.ANONYMOUS]   # None
```

## Testing Queries

```bash
# Create
curl -X POST "http://localhost:8000/api/v3/projects/1/work_packages" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subject": "Test", "status": "new", "priority": "normal", "doneRatio": 0}'

# List
curl -X GET "http://localhost:8000/api/v3/projects/1/work_packages?offset=1&pageSize=20" \
  -H "Authorization: Bearer TOKEN"

# Get
curl -X GET "http://localhost:8000/api/v3/work_packages/123" \
  -H "Authorization: Bearer TOKEN"

# Update
curl -X PATCH "http://localhost:8000/api/v3/work_packages/123" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"doneRatio": 50, "status": "in_progress"}'

# Delete
curl -X DELETE "http://localhost:8000/api/v3/work_packages/123" \
  -H "Authorization: Bearer TOKEN"
```

## Debugging

```python
# Check if module loads
from app.api.v3.work_packages import projects_router, work_packages_router

# Check app routes
from app.main import app
routes = [r.path for r in app.routes if 'work_packages' in r]
print(f"Found {len(routes)} work package routes")

# Check permissions
from app.core.rbac import Permission, ROLE_PERMISSIONS, Role
print(ROLE_PERMISSIONS[Role.MEMBER])

# Check models
from app.infrastructure.db.models import WorkPackageModel
print(WorkPackageModel.__table__.columns.keys())
```

## Error Types

- `validation_error` - Input validation failed
- `not_found` - Resource not found
- `already_exists` - Resource already exists
- `database_error` - Database operation failed
- (Others from existing modules)

## References

- Full docs: [WORK_PACKAGES_IMPLEMENTATION.md](WORK_PACKAGES_IMPLEMENTATION.md)
- Quick start: [WORK_PACKAGES_QUICK_START.md](WORK_PACKAGES_QUICK_START.md)
- Examples from: app/api/v3/projects/ (similar module)
