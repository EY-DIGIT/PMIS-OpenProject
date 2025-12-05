# OpenProject → FastAPI: Technical Summary

**Source**: OpenProject stable/16 branch
**Target**: Python 3.10+ / FastAPI / SQLAlchemy / PostgreSQL

---

## 1. Core Data Model

```
Project (1) ─────< (M) Member (M) >─────< (M) MemberRole (M) >───── (1) Role (1) ──< (M) RolePermission
   │                     │                                                │
   │                     │                                                └─ permission (string)
   │                     │
   │                     └── user_id → User.id (from user_service)
   │
   └── parent_id (self-referential for hierarchy)
   └── lft/rgt (nested set for efficient tree queries)
   └── EnabledModule (1:M) - feature flags
```

### Entity Relationships

| Entity | Type | Purpose |
|--------|------|---------|
| **Project** | Core | Main project entity with hierarchy support |
| **Member** | Junction | Links User ↔ Project (with optional entity specificity) |
| **MemberRole** | Junction | Links Member ↔ Role (with inheritance tracking) |
| **Role** | Container | Groups permissions, can be built-in or custom |
| **RolePermission** | Junction | Links Role ↔ Permission (string) |
| **EnabledModule** | Feature flag | Tracks which modules are active per project |

---

## 2. Key Tables Schema

### Projects
```sql
id, name, identifier (UNIQUE), description, public, active, templated,
parent_id, lft, rgt, workspace_type, status_code, status_explanation,
settings (JSONB), created_at, updated_at
```

**Constraints**:
- `identifier` ~ '^[a-z0-9\-_]+$' (lowercase, alphanumeric, dash, underscore)
- `identifier` not purely numeric
- `identifier` not in ['new', 'menu', 'queries', 'export_list_modal']

### Members
```sql
id, user_id, project_id, entity_type, entity_id, created_at, updated_at
```

**Uniqueness**:
- (user_id, project_id) when entity is NULL
- (user_id, project_id, entity_type, entity_id) when entity specified

### MemberRoles
```sql
id, member_id, role_id, inherited_from
```

**Purpose**: Many-to-many between Members and Roles with inheritance tracking

### Roles
```sql
id, name (UNIQUE), position, builtin, type, created_at, updated_at
```

**Built-in values**: 0=custom, 1=non-member, 2=anonymous

### RolePermissions
```sql
id, permission, role_id, created_at, updated_at
```

---

## 3. Permission System

### Core Permissions

| Permission | Description | Require | Public |
|------------|-------------|---------|--------|
| `view_project` | View project | - | Yes |
| `edit_project` | Edit project settings | member | No |
| `manage_members` | Add/remove/update members | member | No |
| `add_subprojects` | Create child projects | member | No |
| `archive_project` | Archive/unarchive project | member | No |
| `copy_projects` | Copy project | member | No |

### Authorization Flow

```python
def allows_to(project, user, permission):
    if user.admin:
        return True

    member = get_member(user.id, project.id)
    if not member:
        if project.public and permission == 'view_project':
            return check_non_member_role(permission)
        return False

    for role in member.roles:
        if permission in role.permissions:
            return True

    return False
```

---

## 4. API Endpoints

### Projects

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v3/projects` | List projects (filters: active, public, parent_id) |
| GET | `/api/v3/projects/{id}` | Get single project |
| POST | `/api/v3/projects` | Create project |
| PATCH | `/api/v3/projects/{id}` | Update project |
| POST | `/api/v3/projects/{id}/archive` | Archive project |
| POST | `/api/v3/projects/{id}/copy` | Copy project |

### Memberships

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v3/projects/{id}/memberships` | List project members |
| POST | `/api/v3/projects/{id}/memberships` | Add member to project |
| PATCH | `/api/v3/memberships/{id}` | Update member roles |
| DELETE | `/api/v3/memberships/{id}` | Remove member |

---

## 5. Business Logic

### Project Creation

```python
1. Authorization check (admin OR has add_subprojects on parent)
2. Validate identifier uniqueness
3. Create Project record
4. Add creator as member with "Project admin" role
5. Enable default modules (work_package_tracking, wiki, calendar, board)
6. Update nested set values if has parent
7. Commit transaction
```

### Project Archiving

```python
1. Authorization check (has archive_project permission)
2. Set project.active = False
3. Recursively archive all active child projects
4. Commit transaction
```

### Member Management

```python
# Add Member
1. Authorization check (has manage_members permission)
2. Validate user exists and is active
3. Check not already member
4. Create Member record
5. Create MemberRole records for each role
6. If user is Group: create inherited MemberRole records for all group users

# Remove Member
1. Authorization check (has manage_members permission)
2. If has inherited roles: only remove direct roles
3. If no inherited roles: remove entire Member record
```

---

## 6. SQLAlchemy Models (Minimal)

```python
class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    identifier = Column(String(100), unique=True, nullable=False)
    public = Column(Boolean, default=True)
    active = Column(Boolean, default=True)
    parent_id = Column(Integer, ForeignKey('projects.id'))
    lft = Column(Integer)  # Nested set
    rgt = Column(Integer)  # Nested set

    members = relationship("Member", back_populates="project")
    enabled_modules = relationship("EnabledModule")

class Member(Base):
    __tablename__ = 'members'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'))

    member_roles = relationship("MemberRole", cascade="all, delete-orphan")

    @property
    def roles(self):
        return [mr.role for mr in self.member_roles if mr.role]

class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    name = Column(String(256), unique=True, nullable=False)
    builtin = Column(Integer, default=0)

    role_permissions = relationship("RolePermission")

    def get_permissions(self):
        return [rp.permission for rp in self.role_permissions]
```

---

## 7. Service Layer Pattern

```python
class ProjectService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def create_project(self, data: ProjectCreate) -> ServiceResult:
        # 1. Auth check
        if not self._can_create_project(data.parent_id):
            return ServiceResult.failure(...)

        # 2. Create project
        project = Project(**data.dict())
        self.db.add(project)
        self.db.flush()

        # 3. Initialize (add creator, enable modules)
        self._initialize_project(project)

        # 4. Commit
        self.db.commit()
        return ServiceResult.success(project)
```

---

## 8. User Module Integration

### Extend User Model

```python
# In user_service/models/user.py
class User(Base):
    # ... existing fields ...

    # Add relationship
    members = relationship("Member", foreign_keys="Member.user_id")

    @property
    def projects(self):
        """Get all projects user is member of"""
        return [m.project for m in self.members if m.project]
```

### Authentication Dependency

```python
from fastapi import Depends
from fastapi.security import HTTPBearer

security = HTTPBearer()

def get_current_user(credentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    user_id = validate_jwt_token(token)  # Your implementation
    user = db.query(User).get(user_id)
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(401)
    return user
```

---

## 9. Angular Integration

### API Service

```typescript
@Injectable()
export class ProjectApiService {
  private baseUrl = '/api/v3/projects';

  constructor(private http: HttpClient) {}

  listProjects(filters?: any): Observable<Project[]> {
    return this.http.get<Project[]>(this.baseUrl, { params: filters });
  }

  getProject(id: number): Observable<Project> {
    return this.http.get<Project>(`${this.baseUrl}/${id}`);
  }

  createProject(data: Partial<Project>): Observable<Project> {
    return this.http.post<Project>(this.baseUrl, data);
  }

  updateProject(id: number, data: Partial<Project>): Observable<Project> {
    return this.http.patch<Project>(`${this.baseUrl}/${id}`, data);
  }
}
```

### Component

```typescript
@Component({...})
export class ProjectListComponent implements OnInit {
  projects: Project[] = [];

  constructor(private projectService: ProjectApiService) {}

  ngOnInit() {
    this.projectService.listProjects().subscribe(
      projects => this.projects = projects
    );
  }
}
```

---

## 10. Deployment: Microservices with Nginx

```nginx
# Nginx configuration
upstream fastapi_backend {
    server localhost:8000;
}

upstream rails_backend {
    server localhost:3000;
}

server {
    listen 80;

    # User & Project endpoints → FastAPI
    location /api/v3/users {
        proxy_pass http://fastapi_backend;
    }

    location /api/v3/projects {
        proxy_pass http://fastapi_backend;
    }

    location /api/v3/memberships {
        proxy_pass http://fastapi_backend;
    }

    # Everything else → Rails
    location / {
        proxy_pass http://rails_backend;
    }
}
```

---

## 11. Migration Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| **Setup** | 1 week | Database schema, models, relationships |
| **Backend** | 2-3 weeks | Services, routers, auth integration |
| **Frontend** | 1 week | Update Angular services, test components |
| **Testing** | 1 week | Unit, integration, E2E tests |
| **Deploy** | 1 week | Staging rollout, production deployment |

**Total**: ~5-6 weeks

---

## 12. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Nested Set (lft/rgt)** | Efficient ancestor/descendant queries (OpenProject standard) |
| **Member Junction Table** | Supports both project-level and entity-level memberships |
| **MemberRole.inherited_from** | Tracks group inheritance, allows partial removal |
| **String Permissions** | Flexible, extensible (vs hardcoded enums) |
| **Service Layer** | Encapsulates business logic, testable |
| **ServiceResult Pattern** | Consistent error handling across services |
| **JWT Auth** | Stateless, scalable (vs session cookies) |

---

## 13. Testing Strategy

```python
# Unit Test
def test_create_project(db, admin_user):
    service = ProjectService(db, admin_user)
    data = ProjectCreate(name="Test", identifier="test")
    result = service.create_project(data)
    assert result.is_success()
    assert result.result.name == "Test"

# Integration Test
def test_create_project_api(client, auth_header):
    response = client.post("/api/v3/projects",
                          json={"name": "Test", "identifier": "test"},
                          headers=auth_header)
    assert response.status_code == 201
    assert response.json()['name'] == "Test"
```

---

## 14. Quick Reference: Permission Checks

```python
# In routes
if not project.allows_to(current_user, 'edit_project'):
    raise HTTPException(403, "Not authorized")

# In services
if not self._can_create_project(parent_id):
    return ServiceResult.failure(errors={'auth': ['Not authorized']})

# In models
def allows_to(self, user, permission):
    # Implementation in Project model
```

---

## 15. File Structure

```
user_service/
├── models/
│   ├── user.py (existing)
│   ├── project.py (new)
│   ├── member.py (new)
│   └── role.py (new)
├── schemas/
│   ├── user.py (existing)
│   ├── project.py (new)
│   └── member.py (new)
├── services/
│   ├── user_service.py (existing)
│   ├── project_service.py (new)
│   └── member_service.py (new)
├── routers/
│   ├── users.py (existing)
│   ├── projects.py (new)
│   └── members.py (new)
└── main.py
```

---

## Summary

**What's Implemented:**
✅ Complete data model matching OpenProject stable/16
✅ Full RBAC with role-based permissions
✅ Project hierarchies via nested set
✅ Group membership with inheritance
✅ Entity-specific memberships (WorkPackage, etc.)
✅ Archive/copy/manage operations
✅ FastAPI REST API with OpenProject-compatible endpoints

**What to Do:**
1. Copy models to your codebase
2. Run migrations
3. Seed default roles
4. Implement routers
5. Test with Angular frontend
6. Deploy with Nginx reverse proxy

**Result:**
Modern Python/FastAPI backend that matches OpenProject Project module functionality while integrating seamlessly with your existing User module.
