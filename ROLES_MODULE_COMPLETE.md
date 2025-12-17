"""
# Roles Module - Complete Implementation

## Implementation Complete ✓

The OpenProject Roles module has been successfully ported to the Python FastAPI backend, 
following the exact architecture and conventions of the existing Users, Projects, and 
Project Members modules.

## Module Structure

```
app/
├── api/
│   └── v3/
│       └── roles/
│           ├── __init__.py              ← Module initialization
│           ├── routes.py                ← API endpoints (5 endpoints)
│           ├── controller.py            ← Request handling & response formatting
│           ├── schemas.py               ← Pydantic request/response models
│           ├── permissions.py           ← Permission constant exports
│           └── services/
│               ├── __init__.py
│               ├── create.py            ← Create role logic
│               ├── get.py               ← Get role by ID/name
│               ├── list.py              ← List roles with pagination
│               ├── update.py            ← Update role
│               └── delete.py            ← Delete role
├── domain/
│   └── roles/
│       ├── __init__.py
│       └── role.py                      ← Domain entity (dataclass)
├── infrastructure/
│   └── db/
│       ├── models/
│       │   └── role.py                  ← SQLAlchemy ORM model
│       └── repositories/
│           └── role_repository.py       ← Database CRUD operations
└── core/
    ├── response.py                      ← Updated with format_role_response()
    └── rbac.py                          ← Updated with ROLES_* permissions
```

## API Endpoints

### 1. List Roles
```
GET /api/v3/roles?offset=0&pageSize=20
Requires: ROLES_READ permission (admin only)
Returns: HAL+JSON collection with pagination
```

### 2. Get Role
```
GET /api/v3/roles/{role_id}
Requires: ROLES_READ permission (admin only)
Returns: HAL+JSON role object
```

### 3. Create Role
```
POST /api/v3/roles
Requires: ROLES_CREATE permission (admin only)
Body: {
    "name": "Editor",
    "permissions": ["projects:view", "projects:edit"],
    "builtin": false
}
Returns: HAL+JSON role object (201 Created)
```

### 4. Update Role
```
PATCH /api/v3/roles/{role_id}
Requires: ROLES_UPDATE permission (admin only)
Body: {
    "name": "Reviewer",
    "permissions": ["projects:view", "projects:comment"]
}
Returns: HAL+JSON role object
Note: Builtin roles cannot be modified
```

### 5. Delete Role
```
DELETE /api/v3/roles/{role_id}
Requires: ROLES_DELETE permission (admin only)
Returns: 204 No Content
Note: Builtin roles cannot be deleted
```

## Response Format (HAL+JSON)

### Single Role
```json
{
  "data": {
    "_type": "Role",
    "_links": {
      "self": {
        "href": "/api/v3/roles/1",
        "title": "Admin"
      }
    },
    "id": 1,
    "name": "Admin",
    "permissions": ["projects:view", "projects:edit"],
    "builtin": true,
    "createdAt": "2025-01-01T00:00:00",
    "updatedAt": "2025-01-01T00:00:00"
  },
  "message": null,
  "error": null,
  "status": 200
}
```

### Collection Response
```json
{
  "data": {
    "_type": "Collection",
    "_links": {
      "self": {"href": "/api/v3/roles?offset=0&pageSize=20"},
      "next": {"href": "/api/v3/roles?offset=1&pageSize=20"},
      "last": {"href": "/api/v3/roles?offset=2&pageSize=20"}
    },
    "total": 42,
    "count": 20,
    "pageSize": 20,
    "offset": 0,
    "_embedded": {
      "elements": [
        { /* role objects */ }
      ]
    }
  },
  "message": null,
  "error": null,
  "status": 200
}
```

## RBAC Integration

### New Permissions Added to core/rbac.py
- `ROLES_READ`: Read roles
- `ROLES_CREATE`: Create new roles
- `ROLES_UPDATE`: Update roles
- `ROLES_DELETE`: Delete roles

### Permission Mapping
| Role | ROLES_READ | ROLES_CREATE | ROLES_UPDATE | ROLES_DELETE |
|------|:----------:|:------------:|:------------:|:------------:|
| ADMIN | ✓ | ✓ | ✓ | ✓ |
| MEMBER | ✗ | ✗ | ✗ | ✗ |
| VIEWER | ✗ | ✗ | ✗ | ✗ |
| ANONYMOUS | ✗ | ✗ | ✗ | ✗ |

## Database Schema

### roles Table
```sql
CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) UNIQUE NOT NULL,
    permissions JSON NOT NULL DEFAULT '[]',
    builtin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_roles_name ON roles(name);
CREATE INDEX idx_roles_builtin ON roles(builtin);
```

## Domain Model

### Role Entity
```python
@dataclass
class Role:
    id: int
    name: str
    permissions: List[str]
    builtin: bool
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
```

## Service Layer Pattern

All services follow the same pattern:

```python
def operation(db: Session, ...) -> ServiceResult[ReturnType]:
    """
    Business logic with ServiceResult wrapper
    
    Returns:
        ServiceResult with success/failure status
    """
```

### Service Functions
1. **create_role()** - Create new role with validation
2. **get_role_by_id()** - Fetch single role
3. **get_role_by_name()** - Find role by name
4. **list_roles()** - List with pagination
5. **update_role()** - Update role (non-builtin only)
6. **delete_role()** - Delete role (non-builtin only)

## Error Handling

### Error Types
- `validation_error` (422): Invalid input
- `already_exists` (409): Duplicate name
- `not_found` (404): Role doesn't exist
- `forbidden` (403): Cannot modify/delete builtin roles
- `database_error` (400): Database operation failed

### Error Response Example
```json
{
  "data": null,
  "message": null,
  "error": {
    "_type": "Error",
    "errorIdentifier": "forbidden",
    "message": "Cannot modify builtin roles"
  },
  "status": 403
}
```

## Builtin Roles Protection

The module enforces strict rules for builtin roles:
- Cannot be modified (name or permissions)
- Cannot be deleted
- Default permissions are set at creation time

This ensures system integrity for roles that are core to the application.

## Integration with Project Members

The Roles module is completely compatible with the Project Members module:
- Roles can be assigned to project members
- Role permissions are evaluated at request time
- No breaking changes to existing APIs

## Testing

### Validation Test
Run: `python test_roles_validation.py`

Tests covered:
- ✓ Create role
- ✓ Get role by ID/name
- ✓ List roles with pagination
- ✓ Update role
- ✓ Delete role
- ✓ Builtin role protection (update)
- ✓ Builtin role protection (delete)
- ✓ Duplicate name validation
- ✓ Invalid input validation

All tests pass successfully.

## Architecture Compliance

✓ Clean separation of concerns:
  - Routes: HTTP layer only
  - Controller: Request handling & response formatting
  - Services: Business logic only
  - Repository: Database operations only
  - Domain: Data models only

✓ No code duplication - follows existing patterns exactly

✓ RBAC enforced at routing level only
  - No permission checks in services
  - No permission checks in repository

✓ ServiceResult pattern for error handling

✓ HAL+JSON response formatting via core/response.py

✓ Pydantic schemas for validation

✓ SQLAlchemy ORM with proper indexing

## Files Modified/Created

### New Files
- app/domain/roles/role.py
- app/domain/roles/__init__.py
- app/infrastructure/db/models/role.py
- app/infrastructure/db/repositories/role_repository.py
- app/api/v3/roles/__init__.py
- app/api/v3/roles/routes.py
- app/api/v3/roles/controller.py
- app/api/v3/roles/schemas.py
- app/api/v3/roles/permissions.py
- app/api/v3/roles/services/__init__.py
- app/api/v3/roles/services/create.py
- app/api/v3/roles/services/get.py
- app/api/v3/roles/services/list.py
- app/api/v3/roles/services/update.py
- app/api/v3/roles/services/delete.py

### Modified Files
- app/api/router.py (added roles router registration)
- app/core/rbac.py (added role permissions to Permission enum and ROLE_PERMISSIONS mapping)
- app/core/response.py (added format_role_response function and collection support)

## Production Readiness

✓ No TODOs or placeholders
✓ Comprehensive error handling
✓ Input validation
✓ Proper HTTP status codes
✓ Database indexes for performance
✓ Follows OpenProject API standards
✓ Fully integrated with existing modules
✓ All imports resolve correctly
✓ Application boots without errors
✓ RBAC middleware properly enforces access control

## Next Steps

The Roles module is ready for:
1. Database migration setup (Alembic)
2. Seeding builtin roles (Admin, Member, Viewer)
3. Integration testing with authentication
4. Performance testing at scale
5. Documentation updates to API docs

No further changes needed to complete the implementation.
"""
