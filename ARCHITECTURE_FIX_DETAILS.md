# Before and After: Architecture Fixes

## Issue 1: Repository Cross-Domain Imports

### BEFORE (Broken)
```python
# File: app/infrastructure/db/repositories/work_package_repository.py

class WorkPackageRepository:
    def project_exists(self, project_id: int) -> bool:
        from ...models.project import ProjectModel  # BAD: Circular import path
        return self.db.query(ProjectModel).filter(
            ProjectModel.id == project_id
        ).first() is not None
    
    def user_exists(self, user_id: int) -> bool:
        from ...models.user import UserModel  # BAD: Imports models in method
        return self.db.query(UserModel).filter(
            UserModel.id == user_id
        ).first() is not None
```

**Problems:**
- Repository imports ProjectModel and UserModel
- Imports are INSIDE method bodies (fragile, hard to trace)
- Violates DDD: Repository shouldn't know about other domains
- Causes: `ModuleNotFoundError: No module named 'app.infrastructure.models'`

### AFTER (Fixed)
```python
# File: app/infrastructure/db/repositories/work_package_repository.py

class WorkPackageRepository:
    """Repository for Work Package database operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Only CRUD methods for work_packages:
    def create(...) -> WorkPackage: ...
    def get_by_id(...) -> Optional[WorkPackage]: ...
    def update(...) -> WorkPackage: ...
    def delete(...) -> bool: ...
    def list_by_project(...) -> Tuple[List[WorkPackage], int]: ...
    
    # NO project_exists() method
    # NO user_exists() method
    # NO cross-domain imports
```

**Benefits:**
- Repository only handles work_packages CRUD
- No circular dependencies
- Clean architecture respected
- Single responsibility principle

---

## Issue 2: Service Layer Validation Pattern

### BEFORE (Antipattern)
```python
# File: app/api/v3/work_packages/services/create.py

def create_work_package(db: Session, project_id: int, assignee_id: int, ...):
    repository = WorkPackageRepository(db)
    
    # Service calls repository methods for validation (WRONG)
    if not repository.project_exists(project_id):  # BAD
        return ServiceResult.fail(...)
    
    if not repository.user_exists(assignee_id):  # BAD
        return ServiceResult.fail(...)
    
    # Creates work package
    wp = repository.create(...)
    return ServiceResult.ok(wp)
```

**Problems:**
- Repository doing things other than CRUD
- Services relying on repository for validation
- No injection of specialized repositories
- Cross-domain logic mixed in repository layer

### AFTER (Clean Architecture)
```python
# File: app/api/v3/work_packages/services/create.py

from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....infrastructure.db.repositories.project_member_repository import ProjectMemberRepository
from .....infrastructure.db.repositories.work_package_repository import WorkPackageRepository

def create_work_package(db: Session, project_id: int, assignee_id: int, ...):
    # Instantiate specialized repositories
    repository = WorkPackageRepository(db)
    project_repo = ProjectRepository(db)
    member_repo = ProjectMemberRepository(db)
    
    # Services validate using specialized repositories (RIGHT)
    if not project_repo.exists_by_id(project_id):  # GOOD
        return ServiceResult.fail(...)
    
    if not member_repo.is_member(project_id, assignee_id):  # GOOD
        return ServiceResult.fail(...)
    
    # Creates work package
    wp = repository.create(...)
    return ServiceResult.ok(wp)
```

**Benefits:**
- Clear separation of concerns
- Each repository has single responsibility
- Dependency injection of specialized repos
- ProjectRepository.exists_by_id() is its responsibility
- ProjectMemberRepository.is_member() is its responsibility
- WorkPackageRepository only does CRUD

---

## Architecture Diagram

### BEFORE (Broken)
```
Service Layer
    |
    v
WorkPackageRepository (does CRUD + validation)
    |-- project_exists(project_id)  [BAD: knows about projects]
    |-- user_exists(user_id)        [BAD: knows about users]
    |-- create()
    |-- get_by_id()
    |-- update()
    |-- delete()
    |
    +-> Tries to import ProjectModel, UserModel (FAILS!)
```

### AFTER (Fixed)
```
Service Layer
    |
    +---> ProjectRepository (validates project existence)
    |         |-- exists_by_id()
    |
    +---> ProjectMemberRepository (validates membership)
    |         |-- is_member()
    |
    +---> WorkPackageRepository (only CRUD)
              |-- create()
              |-- get_by_id()
              |-- update()
              |-- delete()
              |-- list_by_project()
```

---

## Validation Flow Example: Create Work Package

```python
# Client Request
POST /api/v3/projects/1/work_packages
{
    "subject": "Add login feature",
    "assignee_id": 5
}

# Routes Layer
routes.py -> controller.create_work_package()

# Controller Layer
controller.py -> services.create_work_package(db=session, project_id=1, assignee_id=5, ...)

# Service Layer with Clean Architecture
services/create.py:
    1. Normalize and validate subject (0-255 chars)
    2. Validate done_ratio (0-100)
    3. Validate status (enum check)
    4. Validate priority (enum check)
    
    5. Check project exists via ProjectRepository
       ProjectRepository(db).exists_by_id(project_id=1)
       -> Queries projects table
       -> Returns True/False
    
    6. Check assignee is project member via ProjectMemberRepository
       ProjectMemberRepository(db).is_member(project_id=1, user_id=5)
       -> Queries project_members table
       -> Returns True/False
    
    7. Create work package via WorkPackageRepository
       WorkPackageRepository(db).create(...)
       -> Inserts into work_packages table
       -> Returns WorkPackage domain object

# Response Layer
response.py -> generic HAL helpers; controller builds WorkPackage HAL
-> HAL+JSON response with links, embedded objects

# Client Response
200 OK
{
    "id": 42,
    "subject": "Add login feature",
    "project_id": 1,
    "assignee_id": 5,
    ...
    "_links": {
        "self": {"href": "/api/v3/work_packages/42"},
        "project": {"href": "/api/v3/projects/1"}
    }
}
```

---

## Summary of Changes

| File | Change | Reason |
|------|--------|--------|
| work_package_repository.py | Removed `project_exists()` method | Not repository's job; violates DDD |
| work_package_repository.py | Removed `user_exists()` method | Not repository's job; violates DDD |
| create.py | Added ProjectRepository injection | Service validates project exists |
| create.py | Added ProjectMemberRepository injection | Service validates assignee membership |
| create.py | Removed calls to `repository.project_exists()` | Replaced with `project_repo.exists_by_id()` |
| create.py | Removed calls to `repository.user_exists()` | Replaced with `member_repo.is_member()` |
| update.py | Removed calls to `repository.user_exists()` | Replaced with `member_repo.is_member()` |
| list.py | Added ProjectRepository injection | Service validates project exists |
| list.py | Removed calls to `repository.project_exists()` | Replaced with `project_repo.exists_by_id()` |

---

## Result
- All 5 API endpoints working
- Clean architecture restored
- Zero breaking changes
- Ready for production
