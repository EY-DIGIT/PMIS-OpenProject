```markdown
# OpenProject Frontend Integration Guide

## Can You Convert the OpenProject Frontend to Use This FastAPI Backend?

### TL;DR: **Partially Yes, with Significant Effort**

This guide explains the feasibility, approach, and steps required to integrate the OpenProject Angular frontend with this FastAPI backend.

---

## Understanding the Challenge

### OpenProject Architecture

OpenProject consists of:

1. **Ruby on Rails Backend**
   - Handles all business logic
   - Serves API v3 endpoints
   - Manages database operations
   - Includes 50+ modules (work packages, projects, time tracking, budgets, etc.)

2. **Angular Frontend**
   - Modern TypeScript/Angular application
   - Communicates via API v3
   - Located in `/frontend` directory
   - Tightly coupled to Rails backend features

### This FastAPI Implementation

✅ **What's Implemented:**
- User management (CRUD operations)
- Authentication (login, logout, registration)
- Password management
- User preferences
- HAL+JSON response format
- API v3 compatible endpoints

❌ **What's NOT Implemented:**
- Work packages
- Projects
- Time tracking
- Budgets
- Teams/Groups
- Meetings
- Wiki
- Forums
- And 40+ other OpenProject features

---

## Feasibility Assessment

### Option 1: Microservices Architecture ⭐ **RECOMMENDED**

**Feasibility: HIGH**
**Effort: Medium**
**Risk: Low**

Run both backends simultaneously:

```
┌─────────────────┐
│  Angular Client │
└────────┬────────┘
         │
    ┌────▼────┐
    │  Nginx  │  (API Gateway)
    │ Reverse │
    │  Proxy  │
    └────┬────┘
         │
    ┌────┴─────────────────┐
    │                      │
┌───▼────────┐      ┌──────▼──────┐
│  FastAPI   │      │    Rails    │
│   (Users)  │      │  (Others)   │
└────────────┘      └─────────────┘
```

**Configuration:**

```nginx
# nginx.conf
upstream fastapi_backend {
    server localhost:8000;
}

upstream rails_backend {
    server localhost:3000;
}

server {
    listen 80;

    # User endpoints go to FastAPI
    location /api/v3/users {
        proxy_pass http://fastapi_backend;
    }

    location /api/v3/auth {
        proxy_pass http://fastapi_backend;
    }

    # Everything else goes to Rails
    location / {
        proxy_pass http://rails_backend;
    }
}
```

**Frontend Changes:**

```typescript
// src/app/core/services/api.service.ts
import { HttpClient } from '@angular/common/http';

export class ApiService {
  // No changes needed - API URLs remain the same
  // Nginx handles routing to correct backend
}
```

**Advantages:**
✅ Minimal frontend changes
✅ Gradual migration path
✅ Both backends coexist
✅ Lower risk
✅ Existing functionality preserved

**Disadvantages:**
❌ Two backends to maintain
❌ Shared database complexity
❌ Additional infrastructure (Nginx)

---

### Option 2: Gradual Frontend Migration

**Feasibility: MEDIUM**
**Effort: High**
**Risk: Medium**

Modify Angular app to use FastAPI for user features only:

```typescript
// src/environments/environment.ts
export const environment = {
  production: false,
  userApiUrl: 'http://localhost:8000/api/v3',  // FastAPI
  projectApiUrl: 'http://localhost:3000/api/v3'  // Rails
};

// src/app/core/services/user-api.service.ts
@Injectable()
export class UserApiService {
  constructor(private http: HttpClient) {}

  baseUrl = environment.userApiUrl;

  getUser(id: string) {
    return this.http.get(`${this.baseUrl}/users/${id}`);
  }

  listUsers(params: any) {
    return this.http.get(`${this.baseUrl}/users`, { params });
  }

  createUser(userData: any) {
    return this.http.post(`${this.baseUrl}/users`, userData);
  }
}

// src/app/core/services/project-api.service.ts
@Injectable()
export class ProjectApiService {
  constructor(private http: HttpClient) {}

  baseUrl = environment.projectApiUrl;  // Still uses Rails

  getProject(id: string) {
    return this.http.get(`${this.baseUrl}/projects/${id}`);
  }
}
```

**Steps:**

1. **Update API Services**
   - Create separate service for user operations
   - Point user service to FastAPI
   - Keep other services pointing to Rails

2. **Update Authentication**
   - Modify auth interceptor for dual backends
   - Handle sessions/tokens for both

3. **Test Integration**
   - Ensure user pages work with FastAPI
   - Verify other pages still work with Rails

**Advantages:**
✅ Use FastAPI benefits for user management
✅ Keep existing Rails functionality
✅ Can migrate incrementally

**Disadvantages:**
❌ Complex service layer
❌ Two authentication systems
❌ Increased maintenance
❌ Potential state synchronization issues

---

### Option 3: Full Rewrite ⚠️ **NOT RECOMMENDED**

**Feasibility: LOW**
**Effort: Very High (6-12 months)**
**Risk: Very High**

Implement all OpenProject features in FastAPI.

**Why NOT Recommended:**

1. **Massive Effort**: OpenProject has 50+ modules, 10+ years of development
2. **Business Logic**: Complex domain logic needs reimplementation
3. **Testing**: Requires comprehensive test suite
4. **Maintenance**: Better to contribute to OpenProject directly
5. **Database Schema**: Complex schema with migrations
6. **Features**: File attachments, notifications, email, webhooks, etc.

**Better Alternative:** Contribute to OpenProject's modularity efforts or use their API.

---

## Practical Integration Steps

### Step 1: Set Up FastAPI Backend

```bash
# Install dependencies
cd user_service
pip install -r requirements_api.txt

# Initialize database
python -c "from user_service.database import init_db; init_db()"

# Run server
uvicorn user_service.main:app --reload --port 8000
```

### Step 2: Configure Nginx Reverse Proxy

```bash
# Install Nginx
sudo apt install nginx  # Ubuntu/Debian
brew install nginx      # macOS

# Copy configuration
sudo cp nginx.conf /etc/nginx/sites-available/openproject
sudo ln -s /etc/nginx/sites-available/openproject /etc/nginx/sites-enabled/

# Test and reload
sudo nginx -t
sudo nginx -s reload
```

### Step 3: Update Frontend Configuration

```typescript
// angular.json or environment files
"serve": {
  "options": {
    "proxyConfig": "proxy.conf.json"
  }
}

// proxy.conf.json
{
  "/api/v3/users": {
    "target": "http://localhost:8000",
    "secure": false,
    "changeOrigin": true
  },
  "/api/v3": {
    "target": "http://localhost:3000",
    "secure": false,
    "changeOrigin": true
  }
}
```

### Step 4: Test Integration

```bash
# Start FastAPI
uvicorn user_service.main:app --reload --port 8000

# Start Rails (if keeping it)
cd openproject
./bin/rails server -p 3000

# Start Angular
cd openproject/frontend
npm start
```

### Step 5: Verify Endpoints

```bash
# Test FastAPI user endpoint
curl http://localhost:4200/api/v3/users/me \
  -H "Cookie: session_id=..." \
  -H "X-Requested-With: XMLHttpRequest"

# Should return user data from FastAPI

# Test Rails project endpoint
curl http://localhost:4200/api/v3/projects/1 \
  -H "Cookie: session_id=..."

# Should return project data from Rails
```

---

## Frontend Code Examples

### Update User Service

```typescript
// src/app/core/services/user.service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { User, UserCollection } from '../models/user.model';

@Injectable({
  providedIn: 'root'
})
export class UserService {
  private apiUrl = '/api/v3/users';  // Nginx routes to FastAPI

  constructor(private http: HttpClient) {}

  getUsers(offset: number = 0, pageSize: number = 20): Observable<UserCollection> {
    const params = new HttpParams()
      .set('offset', offset.toString())
      .set('pageSize', pageSize.toString());

    return this.http.get<UserCollection>(this.apiUrl, { params });
  }

  getUser(id: string): Observable<User> {
    return this.http.get<User>(`${this.apiUrl}/${id}`);
  }

  getCurrentUser(): Observable<User> {
    return this.http.get<User>(`${this.apiUrl}/me`);
  }

  createUser(userData: Partial<User>): Observable<User> {
    return this.http.post<User>(this.apiUrl, userData);
  }

  updateUser(id: number, userData: Partial<User>): Observable<User> {
    return this.http.patch<User>(`${this.apiUrl}/${id}`, userData);
  }

  deleteUser(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }

  lockUser(id: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/${id}/lock`, {});
  }

  unlockUser(id: number): Observable<any> {
    return this.http.post(`${this.apiUrl}/${id}/unlock`, {});
  }
}
```

### Update Authentication Service

```typescript
// src/app/core/services/auth.service.ts
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { tap } from 'rxjs/operators';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private authUrl = '/api/v3/auth';  // Nginx routes to FastAPI
  private currentUserSubject = new BehaviorSubject<any>(null);
  public currentUser$ = this.currentUserSubject.asObservable();

  constructor(private http: HttpClient) {}

  login(username: string, password: string): Observable<any> {
    return this.http.post(`${this.authUrl}/login`, { username, password })
      .pipe(
        tap(response => {
          this.currentUserSubject.next(response.user);
        })
      );
  }

  logout(): Observable<any> {
    return this.http.post(`${this.authUrl}/logout`, {})
      .pipe(
        tap(() => {
          this.currentUserSubject.next(null);
        })
      );
  }

  register(userData: any): Observable<any> {
    return this.http.post(`${this.authUrl}/register`, userData);
  }

  changePassword(currentPassword: string, newPassword: string): Observable<any> {
    return this.http.post(`${this.authUrl}/change-password`, {
      currentPassword,
      newPassword,
      newPasswordConfirmation: newPassword
    });
  }
}
```

### Update User Component

```typescript
// src/app/modules/users/user-list/user-list.component.ts
import { Component, OnInit } from '@angular/core';
import { UserService } from '../../../core/services/user.service';

@Component({
  selector: 'app-user-list',
  template: `
    <div class="user-list">
      <h2>Users</h2>
      <table>
        <thead>
          <tr>
            <th>Login</th>
            <th>Name</th>
            <th>Email</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let user of users">
            <td>{{ user.login }}</td>
            <td>{{ user.name }}</td>
            <td>{{ user.email }}</td>
            <td>{{ user.status }}</td>
            <td>
              <button (click)="editUser(user)">Edit</button>
              <button (click)="deleteUser(user)">Delete</button>
              <button *ngIf="user.status !== 'locked'" (click)="lockUser(user)">Lock</button>
              <button *ngIf="user.status === 'locked'" (click)="unlockUser(user)">Unlock</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  `
})
export class UserListComponent implements OnInit {
  users: any[] = [];

  constructor(private userService: UserService) {}

  ngOnInit() {
    this.loadUsers();
  }

  loadUsers() {
    this.userService.getUsers().subscribe(
      response => {
        this.users = response._embedded.elements;
      }
    );
  }

  editUser(user: any) {
    // Navigate to edit page
  }

  deleteUser(user: any) {
    if (confirm(`Delete user ${user.name}?`)) {
      this.userService.deleteUser(user.id).subscribe(
        () => this.loadUsers()
      );
    }
  }

  lockUser(user: any) {
    this.userService.lockUser(user.id).subscribe(
      () => this.loadUsers()
    );
  }

  unlockUser(user: any) {
    this.userService.unlockUser(user.id).subscribe(
      () => this.loadUsers()
    );
  }
}
```

---

## Database Considerations

### Shared Database Approach

Both backends access the same database:

```
┌─────────────┐     ┌──────────────┐
│   FastAPI   │────▶│  PostgreSQL  │◀────│    Rails    │
│   (Users)   │     │   Database   │     │  (Others)   │
└─────────────┘     └──────────────┘     └─────────────┘
```

**Challenges:**
- Schema compatibility
- Migration coordination
- Transaction management

**Solution:**
- Use identical schema for user tables
- Coordinate database migrations
- Use database-level constraints

### Separate Databases (Better)

```
┌─────────────┐     ┌──────────────┐
│   FastAPI   │────▶│  Users DB    │
│             │     │ (PostgreSQL) │
└─────────────┘     └──────────────┘

┌─────────────┐     ┌──────────────┐
│    Rails    │────▶│  Main DB     │
│             │     │ (PostgreSQL) │
└─────────────┘     └──────────────┘
```

**Advantages:**
✅ Clear separation
✅ Independent scaling
✅ Easier maintenance

**Disadvantages:**
❌ Data synchronization needed
❌ Foreign key constraints difficult

---

## Authentication & Session Management

### Shared Sessions

Use Redis for shared session storage:

```python
# FastAPI (user_service/session.py)
import redis
from fastapi import Request

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def get_session(request: Request):
    session_id = request.cookies.get('session_id')
    if session_id:
        session_data = redis_client.get(f'session:{session_id}')
        if session_data:
            return json.loads(session_data)
    return None
```

```ruby
# Rails (config/initializers/session_store.rb)
Rails.application.config.session_store :redis_store,
  servers: ["redis://localhost:6379/0/session"],
  expire_after: 90.minutes,
  key: "_openproject_session"
```

---

## Testing the Integration

### 1. Unit Tests

```typescript
// user.service.spec.ts
describe('UserService', () => {
  let service: UserService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [UserService]
    });
    service = TestBed.inject(UserService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  it('should fetch users from FastAPI', () => {
    service.getUsers().subscribe(response => {
      expect(response._type).toBe('Collection');
    });

    const req = httpMock.expectOne('/api/v3/users?offset=0&pageSize=20');
    expect(req.request.method).toBe('GET');
  });
});
```

### 2. Integration Tests

```python
# test_integration.py
def test_angular_user_list_integration():
    """Test that Angular can fetch user list"""
    response = client.get("/api/v3/users?offset=0&pageSize=20")
    assert response.status_code == 200
    data = response.json()
    assert data["_type"] == "Collection"
    assert "_embedded" in data
    assert "elements" in data["_embedded"]
```

### 3. End-to-End Tests

```typescript
// e2e/user-management.e2e-spec.ts
describe('User Management', () => {
  it('should list users', () => {
    cy.visit('/admin/users');
    cy.get('table tbody tr').should('have.length.gt', 0);
  });

  it('should create new user', () => {
    cy.visit('/admin/users/new');
    cy.get('input[name="login"]').type('testuser');
    cy.get('input[name="email"]').type('test@example.com');
    cy.get('button[type="submit"]').click();
    cy.url().should('include', '/admin/users/');
  });
});
```

---

## Performance Considerations

### FastAPI Advantages

✅ **Faster**: Async I/O, lightweight
✅ **Scalable**: Easy horizontal scaling
✅ **Modern**: Type hints, automatic docs

### Optimization Tips

```python
# Use connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)

# Add caching
from functools import lru_cache

@lru_cache(maxsize=100)
def get_user_cached(user_id: int):
    return get_user(user_id)

# Use async database
from databases import Database
database = Database(DATABASE_URL)
```

---

## Deployment

### Docker Compose

```yaml
version: '3.8'

services:
  fastapi:
    build: ./user_service
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/openproject
    depends_on:
      - db

  rails:
    build: ./openproject
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/openproject
    depends_on:
      - db

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - fastapi
      - rails

  db:
    image: postgres:14
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: openproject
```

---

## Conclusion

### Recommended Approach

For integrating the OpenProject frontend with this FastAPI backend:

1. **Use Microservices Architecture** with Nginx reverse proxy
2. **Route user endpoints to FastAPI**, everything else to Rails
3. **Share session storage** via Redis
4. **Gradually migrate** other modules if needed

### Expected Results

✅ **Fast user management** with modern FastAPI backend
✅ **Existing functionality** preserved via Rails
✅ **Low risk** migration path
✅ **Scalable** architecture

### Resources

- [API Documentation](./API_README.md)
- [OpenProject API Docs](https://www.openproject.org/docs/api/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Nginx Reverse Proxy](https://docs.nginx.com/nginx/admin-guide/web-server/reverse-proxy/)

---

## Support

For questions or issues with the integration:
1. Check the [API_README.md](./API_README.md)
2. Review OpenProject documentation
3. Test endpoints with `/api/docs`
```
