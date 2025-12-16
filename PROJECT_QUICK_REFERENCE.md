# Project Module Quick Reference

## File Structure

```
app/
├── domain/projects/
│   ├── __init__.py
│   └── project.py                    # Domain entity
├── infrastructure/db/
│   ├── models/
│   │   └── project.py                # SQLAlchemy model
│   └── repositories/
│       └── project_repository.py      # Data access
├── api/v3/projects/
│   ├── __init__.py
│   ├── controller.py                 # Request handling
│   ├── routes.py                     # HTTP endpoints
│   ├── schemas.py                    # Request/response validation
│   ├── permissions.py                # Permission constants
│   └── services/
│       ├── __init__.py
│       ├── create.py                 # Creation logic
│       ├── get.py                    # Retrieval logic
│       ├── list.py                   # Listing/pagination
│       ├── update.py                 # Update logic
│       └── delete.py                 # Deletion logic
```

## Code Patterns

### Creating a Project (Service Layer)
```python
from app.api.v3.projects.services import create_project

result = create_project(
    db=db_session,
    identifier="my-project",
    name="My Project",
    description="Optional description",
    active=True,
    public=False,
    status_explanation="On track",
    parent_id=None
)

if result.is_success():
    project = result.data  # ServiceResult[Project]
else:
    error = result.error  # Error message
    error_type = result.error_type  # Error type
```

### Handling in Controller
```python
from app.core.base_controller import BaseController
from app.core.response import format_project_response

result = create_project(...)

if not result.is_success():
    error_payload = {
        "_type": "Error",
        "errorIdentifier": result.error_type,
        "message": result.error
    }
    return BaseController.error(error_payload, status=400)

project_dict = result.data.to_dict()
formatted = format_project_response(project_dict, "/api/v3")
return BaseController.created(data=formatted)
```

### Using in Routes
```python
from fastapi import APIRouter, Depends, Request
from .controller import ProjectController
from .permissions import PROJECTS_CREATE
from app.core.middleware.rbac import require_permission
from app.infrastructure.db.session import get_db

router = APIRouter(prefix="/projects")

@router.post(
    "",
    dependencies=[require_permission(PROJECTS_CREATE)],
    status_code=201
)
def create_project(
    request: Request,
    data: ProjectCreateRequest,
    db: Session = Depends(get_db)
):
    return ProjectController.create(request, data, db)
```

## Response Format

All Project API responses follow this envelope:

```json
{
  "data": {
    "_type": "Project",
    "_links": {
      "self": {"href": "/api/v3/projects/1", "title": "Project Name"}
    },
    "id": 1,
    "identifier": "my-project",
    "name": "My Project",
    "description": "Description",
    "active": true,
    "public": false,
    "statusExplanation": "On track",
    "createdAt": "2024-12-16T10:00:00",
    "updatedAt": "2024-12-16T10:00:00"
  },
  "message": null,
  "error": null,
  "status": 200
}
```

## Permission Levels

| Permission | Required Role | Use Case |
|-----------|---|----------|
| PROJECTS_CREATE | member+ | Create new projects |
| PROJECTS_READ | viewer+ | Read individual projects |
| PROJECTS_READ_ALL | admin | Read all projects |
| PROJECTS_UPDATE | member+ | Update project details |
| PROJECTS_UPDATE_ALL | admin | Update any project |
| PROJECTS_DELETE | admin | Delete projects |
| PROJECTS_DELETE_ALL | admin | Delete any project |

## Common Tasks

### Query Projects by Status
```python
from app.api.v3.projects.services import list_projects

result = list_projects(
    db=db,
    page=1,
    page_size=20,
    active=True,      # Only active projects
    public=None       # All visibility levels
)

projects = result.data.items  # List[Project]
total = result.data.total     # Total count
```

### Get Project by Identifier
```python
from app.api.v3.projects.services import get_project_by_identifier

result = get_project_by_identifier(db, "my-project")
if result.is_success():
    project = result.data
```

### Update Project
```python
from app.api.v3.projects.services import update_project

result = update_project(
    db=db,
    project_id=1,
    name="New Name",
    active=False
)
```

### Delete Project
```python
from app.api.v3.projects.services import delete_project

result = delete_project(db, project_id=1)
```

## Adding New Features

### 1. Add a New Service Function
Create `app/api/v3/projects/services/new_feature.py`:
```python
from app.shared.service_result import ServiceResult

def new_feature(db, param1: str) -> ServiceResult[ResultType]:
    """Description of the feature."""
    # Validate
    if not valid:
        return ServiceResult.fail(error="...", error_type="...")
    
    # Execute
    try:
        result = do_something(db, param1)
        return ServiceResult.ok(result)
    except Exception as e:
        return ServiceResult.fail(error=str(e), error_type="internal_error")
```

### 2. Add Route Handler
In `app/api/v3/projects/controller.py`:
```python
@staticmethod
def new_handler(request: Request, data: NewRequest, db: Session) -> JSONResponse:
    result = new_feature(db, data.param)
    
    if not result.is_success():
        return BaseController.error(error_payload, status=400)
    
    return BaseController.ok(data=result.data)
```

### 3. Add Route
In `app/api/v3/projects/routes.py`:
```python
@router.post(
    "/new-endpoint",
    dependencies=[require_permission(PROJECTS_READ)],
)
def new_endpoint(request: Request, data: NewRequest, db: Session = Depends(get_db)):
    return ProjectController.new_handler(request, data, db)
```

### 4. Add Schema
In `app/api/v3/projects/schemas.py`:
```python
class NewRequest(BaseModel):
    """Request schema for new feature."""
    param: str = Field(..., min_length=1)
```

## Testing Checklist

- [ ] App boots without errors: `python -c "from app.main import app"`
- [ ] Routes registered: Check `/api/v3/projects` endpoints exist
- [ ] RBAC enforced: Verify permission checks on routes
- [ ] Responses formatted: Validate HAL+JSON structure
- [ ] Database operations: Test CRUD in database
- [ ] Validation: Test invalid input handling
- [ ] Errors: Test error responses (404, 409, 422, etc.)
- [ ] Pagination: Test offset/pageSize parameters
- [ ] Filtering: Test active/public filters

## Troubleshooting

### Circular Import
- Check that session.py doesn't import models at module level
- Import models inside functions if needed

### Database Errors
- Ensure `init_db()` is called during app startup
- Check that ProjectModel is imported in session.init_db()

### Permission Denied
- Verify permission is defined in `app.core.rbac.Permission`
- Check ROLE_PERMISSIONS mapping includes the permission
- Confirm route has `dependencies=[require_permission(...)]`

### Validation Errors
- Check Pydantic model field types and validators
- Verify ConfigDict(populate_by_name=True) for alias support
- Test with valid JSON matching schema

## Documentation Links

- [OpenProject API v3 Docs](https://docs.openproject.org/api/)
- [HAL+JSON Spec](https://tools.ietf.org/html/draft-kelly-json-hal)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/14/orm/)
