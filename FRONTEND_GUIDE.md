# Frontend Integration Guide

**Connecting Angular Frontend to FastAPI Backend**

This guide shows you how to launch and test the Project module with the OpenProject Angular frontend.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Backend Setup](#backend-setup)
3. [Frontend Setup](#frontend-setup)
4. [Angular Configuration](#angular-configuration)
5. [Testing the Integration](#testing-the-integration)
6. [API Service Examples](#api-service-examples)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python 3.8+** with pip
- **Node.js 16+** and npm
- **Angular CLI** (`npm install -g @angular/cli`)
- **Git** (for cloning OpenProject frontend)

### Verify Installation

```bash
python --version    # Should be 3.8+
node --version      # Should be 16+
ng version          # Should show Angular CLI
```

---

## Backend Setup

### Step 1: Install Python Dependencies

```bash
cd c:\Programming\user_service
pip install fastapi uvicorn sqlalchemy pydantic python-multipart bcrypt pytest
```

### Step 2: Initialize Database

```bash
python init_project_db.py
```

Expected output:
```
============================================================
OpenProject Project Module - Database Initialization
============================================================
Creating project module tables...

Created/verified 10 tables:
  ✓ enabled_modules
  ✓ member_roles
  ✓ members
  ✓ projects
  ✓ role_permissions
  ✓ roles
  ✓ users
  ...

Seeding default data...
Created role: Project admin with 9 permissions
Created role: Member with 3 permissions
Created role: Reader with 2 permissions

✓ Seeded 3 default roles
✓ Initialization complete!
============================================================
```

### Step 3: Start FastAPI Backend

```bash
cd c:\Programming\user_service
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 4: Verify Backend

Open browser to http://localhost:8000/api/docs

You should see the Swagger UI with all endpoints:
- `/api/v3/projects` - Project endpoints
- `/api/v3/memberships` - Membership endpoints
- `/api/v3/users` - User endpoints
- `/api/v3/auth` - Authentication endpoints

**Keep the backend running** in this terminal.

---

## Frontend Setup

### Option 1: Use Existing OpenProject Frontend

If you already have the OpenProject Angular frontend:

```bash
cd <your-openproject-frontend-directory>
npm install
```

### Option 2: Clone OpenProject Frontend

```bash
cd c:\Programming
git clone https://github.com/opf/openproject.git
cd openproject/frontend
npm install
```

**Note**: The full OpenProject frontend is complex. For testing, you may want to create a minimal Angular app (see Option 3).

### Option 3: Create Minimal Test Angular App (Recommended for Testing)

```bash
cd c:\Programming
ng new openproject-test-frontend --routing --style=scss
cd openproject-test-frontend
npm install
```

---

## Angular Configuration

### 1. Configure Proxy (Redirect API calls to FastAPI)

Create `proxy.conf.json` in your Angular project root:

```json
{
  "/api": {
    "target": "http://localhost:8000",
    "secure": false,
    "changeOrigin": true,
    "logLevel": "debug"
  }
}
```

### 2. Update `angular.json`

Add proxy configuration to serve options:

```json
{
  "projects": {
    "your-project-name": {
      "architect": {
        "serve": {
          "options": {
            "proxyConfig": "proxy.conf.json"
          }
        }
      }
    }
  }
}
```

### 3. Update `package.json` (Optional)

Add a convenient start script:

```json
{
  "scripts": {
    "start": "ng serve --proxy-config proxy.conf.json --port 4200",
    "start:backend": "cd ../user_service && uvicorn main:app --reload --port 8000"
  }
}
```

---

## Testing the Integration

### Step 1: Start Both Servers

**Terminal 1 (Backend)**:
```bash
cd c:\Programming\user_service
uvicorn main:app --reload --port 8000
```

**Terminal 2 (Frontend)**:
```bash
cd c:\Programming\openproject-test-frontend
ng serve --proxy-config proxy.conf.json
```

### Step 2: Open Browser

Navigate to: http://localhost:4200

### Step 3: Test API Calls from Browser Console

Open browser DevTools (F12) and run:

```javascript
// Test backend connection
fetch('/api/v3/projects')
  .then(r => r.json())
  .then(data => console.log('Projects:', data));

// Create a test project
fetch('/api/v3/projects', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    name: 'Test Project',
    identifier: 'test-project',
    description: 'Created from frontend',
    public: false
  })
})
  .then(r => r.json())
  .then(data => console.log('Created:', data));
```

### Step 4: Check Network Tab

In DevTools Network tab, you should see:
- Request to `/api/v3/projects`
- Proxied to `http://localhost:8000/api/v3/projects`
- Response with project data

---

## API Service Examples

### Create Angular Service for Projects

Generate service:
```bash
ng generate service services/project
```

**services/project.service.ts**:

```typescript
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Project {
  id: number;
  name: string;
  identifier: string;
  description?: string;
  public: boolean;
  active: boolean;
  workspace_type: string;
  status_code: number;
  created_at: number;
  updated_at: number;
}

export interface ProjectCreate {
  name: string;
  identifier: string;
  description?: string;
  public?: boolean;
  parent_id?: number;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  public?: boolean;
  active?: boolean;
  status_code?: number;
}

@Injectable({
  providedIn: 'root'
})
export class ProjectService {
  private apiUrl = '/api/v3/projects';

  constructor(private http: HttpClient) { }

  // List projects with filters
  listProjects(filters?: {
    active?: boolean;
    public?: boolean;
    parent_id?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    offset?: number;
    pageSize?: number;
  }): Observable<Project[]> {
    let params = new HttpParams();

    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          params = params.set(key, String(value));
        }
      });
    }

    return this.http.get<Project[]>(this.apiUrl, { params });
  }

  // Get single project
  getProject(id: number): Observable<Project> {
    return this.http.get<Project>(`${this.apiUrl}/${id}`);
  }

  // Create project
  createProject(data: ProjectCreate): Observable<Project> {
    return this.http.post<Project>(this.apiUrl, data);
  }

  // Update project
  updateProject(id: number, data: ProjectUpdate): Observable<Project> {
    return this.http.patch<Project>(`${this.apiUrl}/${id}`, data);
  }

  // Archive project
  archiveProject(id: number): Observable<Project> {
    return this.http.post<Project>(`${this.apiUrl}/${id}/archive`, {});
  }

  // Unarchive project
  unarchiveProject(id: number): Observable<Project> {
    return this.http.post<Project>(`${this.apiUrl}/${id}/unarchive`, {});
  }

  // Copy project
  copyProject(
    id: number,
    data: ProjectCreate,
    options?: {
      copy_members?: boolean;
      copy_modules?: boolean;
      copy_settings?: boolean;
      copy_status?: boolean;
    }
  ): Observable<Project> {
    const params = new HttpParams({ fromObject: options || {} });
    return this.http.post<Project>(
      `${this.apiUrl}/${id}/copy`,
      data,
      { params }
    );
  }

  // Delete project
  deleteProject(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }
}
```

### Create Angular Service for Memberships

Generate service:
```bash
ng generate service services/membership
```

**services/membership.service.ts**:

```typescript
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Membership {
  id: number;
  user_id: number;
  project_id: number;
  entity_type?: string;
  entity_id?: number;
  roles: Role[];
  created_at: number;
  updated_at: number;
}

export interface Role {
  id: number;
  name: string;
  position: number;
  builtin: number;
}

export interface MembershipCreate {
  user_id: number;
  project_id: number;
  role_ids: number[];
}

export interface MembershipUpdate {
  role_ids: number[];
}

@Injectable({
  providedIn: 'root'
})
export class MembershipService {
  private apiUrl = '/api/v3';

  constructor(private http: HttpClient) { }

  // List project memberships
  listProjectMemberships(projectId: number): Observable<Membership[]> {
    return this.http.get<Membership[]>(
      `${this.apiUrl}/projects/${projectId}/memberships`
    );
  }

  // Add member to project
  addMember(projectId: number, data: MembershipCreate): Observable<Membership> {
    return this.http.post<Membership>(
      `${this.apiUrl}/projects/${projectId}/memberships`,
      data
    );
  }

  // Get membership details
  getMembership(id: number): Observable<Membership> {
    return this.http.get<Membership>(`${this.apiUrl}/memberships/${id}`);
  }

  // Update membership roles
  updateMembership(id: number, data: MembershipUpdate): Observable<Membership> {
    return this.http.patch<Membership>(
      `${this.apiUrl}/memberships/${id}`,
      data
    );
  }

  // Remove member
  removeMembership(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/memberships/${id}`);
  }
}
```

### Example Component Usage

Generate component:
```bash
ng generate component components/project-list
```

**components/project-list/project-list.component.ts**:

```typescript
import { Component, OnInit } from '@angular/core';
import { ProjectService, Project } from '../../services/project.service';

@Component({
  selector: 'app-project-list',
  templateUrl: './project-list.component.html',
  styleUrls: ['./project-list.component.scss']
})
export class ProjectListComponent implements OnInit {
  projects: Project[] = [];
  loading = false;
  error: string | null = null;

  constructor(private projectService: ProjectService) { }

  ngOnInit(): void {
    this.loadProjects();
  }

  loadProjects(): void {
    this.loading = true;
    this.error = null;

    this.projectService.listProjects({ active: true })
      .subscribe({
        next: (projects) => {
          this.projects = projects;
          this.loading = false;
        },
        error: (err) => {
          this.error = 'Failed to load projects';
          console.error('Error loading projects:', err);
          this.loading = false;
        }
      });
  }

  createProject(name: string, identifier: string): void {
    this.projectService.createProject({ name, identifier })
      .subscribe({
        next: (project) => {
          console.log('Project created:', project);
          this.loadProjects(); // Reload list
        },
        error: (err) => {
          console.error('Error creating project:', err);
        }
      });
  }

  archiveProject(id: number): void {
    if (confirm('Archive this project?')) {
      this.projectService.archiveProject(id)
        .subscribe({
          next: () => {
            console.log('Project archived');
            this.loadProjects();
          },
          error: (err) => {
            console.error('Error archiving project:', err);
          }
        });
    }
  }
}
```

**components/project-list/project-list.component.html**:

```html
<div class="project-list">
  <h2>Projects</h2>

  <div *ngIf="loading">Loading projects...</div>
  <div *ngIf="error" class="error">{{ error }}</div>

  <div class="project-grid">
    <div *ngFor="let project of projects" class="project-card">
      <h3>{{ project.name }}</h3>
      <p class="identifier">{{ project.identifier }}</p>
      <p class="description">{{ project.description }}</p>

      <div class="badges">
        <span class="badge" *ngIf="project.public">Public</span>
        <span class="badge" *ngIf="!project.active">Archived</span>
      </div>

      <div class="actions">
        <button (click)="archiveProject(project.id)"
                *ngIf="project.active">
          Archive
        </button>
      </div>
    </div>
  </div>

  <div class="create-form">
    <h3>Create New Project</h3>
    <input #nameInput placeholder="Project Name">
    <input #identifierInput placeholder="project-identifier">
    <button (click)="createProject(nameInput.value, identifierInput.value)">
      Create Project
    </button>
  </div>
</div>
```

---

## Troubleshooting

### Issue: CORS Errors

**Symptom**: Browser console shows:
```
Access to fetch at 'http://localhost:8000/api/v3/projects' from origin
'http://localhost:4200' has been blocked by CORS policy
```

**Solution**: The FastAPI backend already has CORS enabled in [main.py](main.py:71-83). Verify it includes:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue: Proxy Not Working

**Symptom**: Requests go to `http://localhost:4200/api/v3/projects` instead of port 8000

**Solution**:
1. Verify `proxy.conf.json` exists in Angular project root
2. Check `angular.json` has `proxyConfig` setting
3. Restart Angular dev server with `--proxy-config` flag:
   ```bash
   ng serve --proxy-config proxy.conf.json
   ```

### Issue: 404 Not Found

**Symptom**: `/api/v3/projects` returns 404

**Solution**:
1. Verify FastAPI backend is running on port 8000
2. Check http://localhost:8000/api/docs - should show Swagger UI
3. Verify routers are included in [main.py](main.py:126-127):
   ```python
   app.include_router(projects_router)
   app.include_router(members_router)
   ```

### Issue: Authentication Required

**Symptom**: 401 Unauthorized errors

**Solution**: The current implementation uses a placeholder `get_current_user()` that auto-creates an admin user. For production:

1. Implement proper authentication in FastAPI
2. Update Angular to send authentication headers:
   ```typescript
   // In Angular HTTP interceptor
   const authReq = req.clone({
     headers: req.headers.set('Authorization', 'Bearer ' + token)
   });
   ```

### Issue: Database Not Initialized

**Symptom**: `sqlalchemy.exc.OperationalError: no such table: projects`

**Solution**:
```bash
cd c:\Programming\user_service
python init_project_db.py
```

### Issue: Import Errors in Python

**Symptom**: `ModuleNotFoundError: No module named 'models'`

**Solution**: Ensure you're running from the correct directory:
```bash
cd c:\Programming\user_service
python -c "import models; print('OK')"
```

If still failing, install in development mode:
```bash
pip install -e .
```

---

## Complete Launch Checklist

### First Time Setup

- [ ] Python 3.8+ installed
- [ ] Node.js 16+ installed
- [ ] Angular CLI installed globally
- [ ] Backend dependencies installed (`pip install ...`)
- [ ] Database initialized (`python init_project_db.py`)
- [ ] Frontend created or cloned
- [ ] `proxy.conf.json` created in Angular project
- [ ] `angular.json` updated with proxy config

### Every Launch

**Terminal 1 - Backend**:
```bash
cd c:\Programming\user_service
uvicorn main:app --reload --port 8000
```
Wait for: `Application startup complete.`

**Terminal 2 - Frontend**:
```bash
cd c:\Programming\openproject-test-frontend
ng serve --proxy-config proxy.conf.json
```
Wait for: `Compiled successfully.`

**Browser**:
- Open http://localhost:4200
- Open DevTools (F12) → Network tab
- Test API call from console

---

## Next Steps

1. **Implement Authentication**
   - Add JWT token generation in FastAPI
   - Create login component in Angular
   - Add HTTP interceptor for auth headers

2. **Create More Components**
   - Project detail view
   - Member management UI
   - Role assignment interface

3. **Add Error Handling**
   - Global error interceptor in Angular
   - User-friendly error messages
   - Retry logic for failed requests

4. **Optimize Performance**
   - Implement pagination in Angular
   - Add caching for frequently accessed data
   - Use Angular OnPush change detection

5. **Production Deployment**
   - Switch to PostgreSQL
   - Configure environment variables
   - Set up HTTPS/SSL
   - Build Angular for production (`ng build --prod`)

---

## Quick Reference

### Backend URLs

- **API Root**: http://localhost:8000/
- **Swagger Docs**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json
- **Health Check**: http://localhost:8000/health

### Frontend URLs

- **Dev Server**: http://localhost:4200
- **Proxied API**: http://localhost:4200/api/v3/*

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v3/projects` | GET | List projects |
| `/api/v3/projects` | POST | Create project |
| `/api/v3/projects/{id}` | GET | Get project |
| `/api/v3/projects/{id}` | PATCH | Update project |
| `/api/v3/projects/{id}/archive` | POST | Archive project |
| `/api/v3/projects/{id}/unarchive` | POST | Unarchive project |
| `/api/v3/projects/{id}/copy` | POST | Copy project |
| `/api/v3/projects/{id}` | DELETE | Delete project |
| `/api/v3/projects/{id}/memberships` | GET | List members |
| `/api/v3/projects/{id}/memberships` | POST | Add member |
| `/api/v3/memberships/{id}` | GET | Get membership |
| `/api/v3/memberships/{id}` | PATCH | Update membership |
| `/api/v3/memberships/{id}` | DELETE | Remove member |

---

## Summary

You now have:
- ✅ FastAPI backend running on port 8000
- ✅ Angular frontend running on port 4200
- ✅ Proxy configuration routing `/api` calls to backend
- ✅ TypeScript services for Projects and Memberships
- ✅ Example components showing API usage

**Start testing**: Create projects, add members, and verify everything works through the browser!
