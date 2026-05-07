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
# ---- Core ----
SECRET_KEY=<32+ character secure key>
DATABASE_URL=postgresql://user:password@host:5432/pmis
DEBUG=False
CORS_ORIGINS=["https://yourdomain.com"]
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
REFRESH_TOKEN_GRACE_SECONDS=120          # doc 19 — refresh-token concurrent-rotation grace
SUBTASK_MAX_NESTING_DEPTH=               # doc 24 part 2 — None / unset = unlimited
BOOTSTRAP_ADMIN_LOGIN=admin
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=admin123

# ---- 2FA + forgot-password + notifications (doc 33 change 3) ----
REQUIRE_2FA=true                         # global toggle; per-user override via users.two_factor_enabled
OTP_TTL_SECONDS=300                      # OTP validity
OTP_RESEND_COOLDOWN_SECONDS=60           # min seconds between /login/send-otp resends per ephemeral session
OTP_MAX_ATTEMPTS=5                       # wrong codes before invalidation
OTP_CODE_LENGTH=6
OTP_HASH_PEPPER=                         # falls back to SECRET_KEY when blank — set per-deployment in prod
PASSWORD_RESET_TTL_SECONDS=3600          # forgot-password URL token / SMS OTP TTL
NOTIFICATION_CLIENT=mock                 # mock | http
NOTIFICATION_SERVICE_URL=                # required when NOTIFICATION_CLIENT=http (e.g. http://notif:8002/api/v1)

# ---- Migration controls (doc 33 hotfix) ----
DATABASE_URL_MIGRATIONS=                 # optional elevated URL ONLY for `alembic upgrade head` at boot;
                                         # falls back to DATABASE_URL when blank
MIGRATIONS_AUTORUN=true                  # set false to skip alembic at boot (DBA runs it out-of-band)
MIGRATIONS_REQUIRED=true                 # set false to log alembic failures and continue boot anyway

# ---- File storage ----
ATTACHMENTS_STORAGE_BASE_PATH=./local_uploads   # NFS mount point in prod
FILE_SERVER_PUBLIC_BASE_URL=             # public base URL for the external file server;
                                         # blank → comments carry storage-key-only URLs served by the local
                                         # /files/{key} fallback route added in doc 35

# ---- Division contact backfill defaults (doc 36) ----
DIVISION_DEFAULT_EMAIL=ops@pmis.example  # backfilled into divisions.email NULLs during the doc-36 migration
DIVISION_DEFAULT_PHONE=+910000000000     # backfilled into divisions.phone_number NULLs;
                                         # also used by init_db when seeding fresh built-in rows.
                                         # Production deploys override both.

# ---- User-service proxy (doc 37 part 2) ----
USER_SERVICE_PROXY_ENABLED=false         # when true, monolith forwards user/auth/RBAC/notification_template
                                         # requests to USER_SERVICE_URL; otherwise handles them locally
USER_SERVICE_URL=                        # base URL of PMIS-user-management (e.g. http://user-mgmt:8001);
                                         # required when USER_SERVICE_PROXY_ENABLED=true
USER_SERVICE_TIMEOUT_SECONDS=10.0        # read-timeout for proxied calls; connect timeout fixed at 5s
```

### Default Settings (app/core/config.py)
- DATABASE_URL: sqlite:///./pmis.db
- SECRET_KEY: "change-in-production"
- DEFAULT_PAGE_SIZE: 20
- MAX_PAGE_SIZE: 100
- REFRESH_TOKEN_GRACE_SECONDS: 120
- SUBTASK_MAX_NESTING_DEPTH: None (unlimited)
- REQUIRE_2FA: True (per-user override via `users.two_factor_enabled`; bootstrap admin is forced `false` on every boot to avoid lockout)
- NOTIFICATION_CLIENT: "mock" (writes to `notification_log` as terminal sink in dev/tests)

### Default Admin Credentials
```
Login: admin
Password: admin123
Email: admin@example.com
```
**Change these in production!** The bootstrap admin user is auto-assigned to the seeded `admin` role on first boot (doc 21B). The user can be deleted later as long as another user holds the `admin` role — the last-admin lockout guard prevents leaving the system without an administrator.

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
- **PostgreSQL**: `alembic upgrade head` runs as a subprocess on boot (idempotent — already-applied migrations are no-ops). Gated by `MIGRATIONS_AUTORUN` / `MIGRATIONS_REQUIRED` flags (doc 33 hotfix) so a DBA can run alembic out-of-band when the runtime DB role lacks DDL ownership; `DATABASE_URL_MIGRATIONS` lets the boot path use an elevated URL just for the upgrade. The full migration chain is in [alembic/versions/](../alembic/versions/) — multiple heads exist; merge revisions are added when chains diverge.
- **SQLite**: `Base.metadata.create_all` rebuilds missing tables; the SQLite drift healer adds any column that was added to the model after the on-disk file was created.
- RBAC seed (doc 21B + doc 33 change 1 + doc 41): every permission code in [app/core/permissions.py](../app/core/permissions.py) is upserted into the `permissions` table; the seeded `admin` / `member` / `viewer` / `vendor` roles are created if missing, plus the doc-41 scoped roles (`super_admin` / `org_admin` / `project_admin` / `project_member` / `division_member`); `admin` and `super_admin` are auto-synced to hold every registered code.
- Doc 41 introduced `user_role_assignments` (alembic `d0c41a55145d`, deployed 2026-05-08). The migration backfilled every legacy `user_roles` row as a global-scope assignment and copied recognised `project_members.roles[]` entries as project-scoped assignments. **Heads-up**: an earlier revision id (`a1b2c3d4e5f6`) collided with an existing migration in production; the canonical doc-41 revision is `d0c41a55145d`. If you see two migration files with the older id, only `d0c41a55145d_doc41_user_role_assignments.py` is correct.
- Bootstrap user `admin/admin123` is created if missing, assigned to the `admin` role, and forced `two_factor_enabled=false` on every boot so the always-reachable break-glass account never gets locked out by an unconfigured notification channel.
- Built-in master data is seeded: divisions (`tmd1`, `tmd2`, `others` — with `email` + `phone_number` populated from `DIVISION_DEFAULT_EMAIL` / `DIVISION_DEFAULT_PHONE` post-doc-36), resource types (RFP/ASG/CCN), project_status_transitions catalog (status set: `new` / `draft` / `published` / `closed` post-doc-33), notification_templates (six rows: `otp_login` / `password_reset_link` / `password_reset_otp` × email/sms — doc 36).
- Built-in work package types are seeded if missing (Task, Bug, Feature, Story, Milestone, Activity).

## Pre-Deployment Checklist

### Security
- [ ] Change SECRET_KEY to unique, secure value (32+ characters)
- [ ] Change default admin credentials
- [ ] Set DEBUG=False
- [ ] Update CORS_ORIGINS to specific domains only
- [ ] Enable HTTPS for all API endpoints
- [ ] Configure rate limiting
- [ ] Consider disabling Swagger UI (openapi_url=None)
- [ ] Set `OTP_HASH_PEPPER` to a deployment-unique value (don't fall back to `SECRET_KEY` in prod — doc 33 change 3)
- [ ] Configure `NOTIFICATION_CLIENT=http` + `NOTIFICATION_SERVICE_URL` (otherwise OTP / password-reset only land in `notification_log`)
- [ ] Set `FILE_SERVER_PUBLIC_BASE_URL` if a dedicated file server is in use (doc 35 — comments carry attachment URLs directly; blank → fallback `/files/{key}` route serves bytes from `ATTACHMENTS_STORAGE_BASE_PATH`)
- [ ] Decide per-environment whether `REQUIRE_2FA=true` is acceptable (service accounts may need per-user opt-out via `PATCH /users/{id}` with `twoFactorEnabled=false`)

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

## Microservice extraction (parallel codebases)

Three sister repos run as standalone services alongside the monolith. They share the same SECRET_KEY and PostgreSQL instance:

| Port | Repo | Notes |
|------|------|-------|
| 8001 | `PMIS-user-management` | **Doc 37 part 2 SHIPPED end-to-end** — foundation `f840fde` + parity `19a30e5`. Routes / services / RBAC repository / slim master_data router all at monolith parity. Monolith proxies via `UserServiceProxyMiddleware` when `USER_SERVICE_PROXY_ENABLED=true` + `USER_SERVICE_URL` set; intercepts `/api/v3/users/*` and `/api/v3/master/{roles,permissions}/*`. Fail-closed (503) when user-service unreachable. **Doc 41 added scoped role-assignment + project-mapping endpoints**: `/api/v3/users/{id}/role-assignments` and `/api/v3/users/{id}/projects` are reachable through the existing `/users/*` proxy rule; `/api/v3/projects/{id}/role-assignments` and `/api/v3/vendors/{id}/projects?expand=role-assignments` are **NOT proxied** — FE talks to `:8001` directly for those. See `planned_changes/37` part 2 status section for the cutover runbook. |
| 8002 | `PMIS-notification-service` | Stateless. `POST /api/v1/notifications/{email,sms,otp}/send` + `/otp/verify`. Mock + real provider backends. |
| 8003 | `PMIS-project-management` | Slim project slice. Still carries `/projects/{id}/suspend` and `/projects/{id}/versions/create` from before doc 33 — divergence will need to be reconciled when versioning-removal is migrated to microservices. |

The monolith (port 8000) is the source of truth and ships features first; microservices are migrated case-by-case. See `C:\Users\CL725CJ\.claude\projects\c--Programming\memory\project_pmis_architecture.md` for the cross-service route inventory.
