# Deployment and Integration Guide

## Installation

### Prerequisites
- Python 3.12+
- pip

### Setup
```bash
cd PMIS_Python
pip install -r requirements.txt
```

### Running (Development)
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Running (Production)
```bash
gunicorn -w 4 -b 0.0.0.0:8000 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --access-logfile - \
  --error-logfile - \
  app.main:app
```

## Configuration

### Environment Variables
```bash
# Required for production
SECRET_KEY=<32+ character secure key>
DATABASE_URL=postgresql://user:password@host:5432/pmis
DEBUG=False
CORS_ORIGINS=["https://yourdomain.com"]
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Default Settings (app/core/config.py)
- DATABASE_URL: sqlite:///./pmis.db
- SECRET_KEY: "change-in-production"
- DEFAULT_PAGE_SIZE: 20
- MAX_PAGE_SIZE: 100

### Default Admin Credentials
```
Login: admin
Password: admin123
Email: admin@example.com
```
**Change these in production!**

## Database

### SQLite (Development)
Default. Database file: pmis.db (auto-created on first run)

### PostgreSQL (Production)
Set DATABASE_URL environment variable:
```bash
DATABASE_URL=postgresql://user:password@host:5432/pmis
```

### Initialization
The database is initialized automatically on startup:
- Tables created if they don't exist
- Schema drift handled for SQLite (missing columns added)
- Default admin user created if none exists
- Built-in work package types created (Task, Bug, Feature, Story, Milestone)

## Pre-Deployment Checklist

### Security
- [ ] Change SECRET_KEY to unique, secure value (32+ characters)
- [ ] Change default admin credentials
- [ ] Set DEBUG=False
- [ ] Update CORS_ORIGINS to specific domains only
- [ ] Enable HTTPS for all API endpoints
- [ ] Configure rate limiting
- [ ] Consider disabling Swagger UI (openapi_url=None)

### Database
- [ ] Migrate from SQLite to PostgreSQL
- [ ] Set up automated backups
- [ ] Configure connection pooling
- [ ] Test recovery procedures

### Operations
- [ ] Set up application monitoring
- [ ] Configure error logging and alerting
- [ ] Plan capacity and scaling strategy
- [ ] Document runbooks for common issues

### Testing
- [ ] Run full test suite: `pytest test_*.py -v`
- [ ] Load testing (simulate expected traffic)
- [ ] Security vulnerability scan
- [ ] Failover and recovery testing

## Health Checks

```bash
# Health check
curl http://localhost:8000/health
# Response: {"_type": "Health", "status": "healthy", "version": "3.0.0"}

# Root endpoint
curl http://localhost:8000/

# Authenticated check
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v3/users/me
```

## Frontend Integration

### Quick Start
1. Start backend: `python -m uvicorn app.main:app --reload`
2. Set frontend env: `VITE_API_URL=http://localhost:8000`
3. Implement login flow (see Authentication docs)
4. Use JWT token for all API calls

### API Base URL
- Development: http://localhost:8000
- Production: https://api.yourdomain.com

### JavaScript Integration Example

```javascript
// Login
async function login(login, password) {
  const response = await fetch('/api/v3/users/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login, password })
  });
  const data = await response.json();
  localStorage.setItem('access_token', data.data.access_token);
  localStorage.setItem('refresh_token', data.data.refresh_token);
  return data.data.user;
}

// Authenticated API call
async function apiCall(endpoint, method = 'GET', body = null) {
  const token = localStorage.getItem('access_token');
  const response = await fetch(`/api/v3${endpoint}`, {
    method,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: body ? JSON.stringify(body) : null
  });
  return await response.json();
}

// Usage examples
const users = await apiCall('/users');
const projects = await apiCall('/projects?offset=1&pageSize=20');
const newProject = await apiCall('/projects', 'POST', {
  identifier: 'my-project',
  name: 'My Project'
});
```

### Error Handling
```javascript
async function handleApiCall(endpoint, options = {}) {
  try {
    const response = await apiCall(endpoint, options.method, options.body);
    if (response.status >= 200 && response.status < 300) {
      return { success: true, data: response.data };
    }
    if (response.status === 401) {
      window.location.href = '/login'; // Token expired
    } else if (response.status === 403) {
      showError("You don't have permission for this action");
    } else if (response.status === 404) {
      showError('Resource not found');
    } else if (response.status === 422) {
      showError('Invalid input: ' + response.error.message);
    }
    return { success: false, error: response.error };
  } catch (err) {
    showError('Network error: ' + err.message);
    return { success: false, error: err };
  }
}
```

## Monitoring

### Key Metrics
1. Authentication failures (failed login attempts)
2. Permission errors (403 responses)
3. Database performance (query execution times)
4. Token refresh rate
5. Error rate (5xx responses)
6. Response times / API latency
7. Uptime / service availability

### Typical Response Times
- Health check: ~5ms
- Login: ~50ms
- User creation: ~30ms
- Project listing: ~20ms
- Meeting creation: ~25ms

### Scaling
- Single instance: ~500-1000 req/sec capacity
- Horizontal: Multiple instances behind load balancer
- Database: PostgreSQL replication for HA
- Caching: Add Redis for session/data caching

## User Service (Alternative Reference Implementation)

The `user_service/` folder contains an alternative, richer User implementation based on OpenProject's stable/16 branch. It includes:
- User statuses: ACTIVE, REGISTERED, INVITED, LOCKED, DELETED
- Special user types: AnonymousUser, SystemUser, DeletedUser, PlaceholderUser
- Password history tracking and reuse prevention
- Failed login tracking with automatic account locking
- User preferences (timezone, theme, notifications)

This is a reference implementation and is NOT integrated with the main app. See `user_service/README.md` for details.
