# PMIS Python - Project Management Information System

Production-ready Python FastAPI backend for OpenProject-compatible project management.

## Quick Start

> **Prerequisite — Postgres must be running on `localhost:5432`.**
> See [Database setup](#database-setup) below if you don't have it yet.

```bash
pip install -r requirements.txt
cp .env.example .env   # then adjust if needed
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

On startup the app:
1. Auto-runs `alembic upgrade head` (Postgres only — schema is fully managed by Alembic)
2. Seeds the bootstrap admin (idempotent — only inserts if the configured login is missing)
3. Seeds resource types, vendors, and built-in work-package types

Default credentials (override via `BOOTSTRAP_ADMIN_*` env vars): `admin` / `admin123`

## Database setup

This project runs on **Postgres 16**. SQLite is still supported for the test
suite (in-memory, isolated per test) but production code paths target Postgres.

### Option A — Postgres natively in WSL Ubuntu (recommended on Windows)

The most reliable setup on Windows. Avoids Docker Desktop quirks entirely.

In **Ubuntu (WSL)**:
```bash
sudo apt update
sudo apt install -y postgresql-16 postgresql-contrib
sudo service postgresql start

sudo -u postgres psql -c "CREATE USER pmis WITH PASSWORD 'pmis_dev_password';"
sudo -u postgres psql -c "CREATE DATABASE pmis OWNER pmis;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE pmis TO pmis;"

# Bind to all interfaces so Windows can reach it
sudo sed -i "s/^#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/16/main/postgresql.conf
echo "host all all 0.0.0.0/0 scram-sha-256" | sudo tee -a /etc/postgresql/16/main/pg_hba.conf
sudo service postgresql restart
sudo systemctl enable postgresql      # auto-start on WSL boot
```

In **PowerShell**, enable WSL2 mirrored networking so Windows `localhost` reaches
WSL Postgres without hardcoding the WSL IP:
```powershell
@"
[wsl2]
networkingMode=mirrored

[boot]
systemd=true
"@ | Out-File -FilePath "$env:USERPROFILE\.wslconfig" -Encoding ASCII

wsl --shutdown
# Reopen Ubuntu — Postgres comes back up automatically
```

Verify from PowerShell:
```powershell
Test-NetConnection -ComputerName localhost -Port 5432
# TcpTestSucceeded : True
```

### Option B — Postgres in Docker

```bash
docker compose -f infra/docker-compose.yml up -d
docker ps --filter name=pmis-postgres
```

Note: Docker Desktop on Windows is occasionally fragile (port forwarding can
drop after sleep/wake). If you hit `Connection refused` even with the
container "running" in the UI, fall back to Option A.

## Schema migrations (Alembic)

Schema is managed by Alembic — no more manual `CREATE TABLE` or ad-hoc ALTERs.

```bash
# Apply pending migrations (also auto-runs on app boot)
alembic upgrade head

# Generate a new migration after changing models
alembic revision --autogenerate -m "describe your change"

# Inspect history
alembic history --verbose
```

Migrations live in `alembic/versions/`. The `env.py` is wired to
`app.core.config.settings.DATABASE_URL` and `app.infrastructure.db.session.Base.metadata`,
so you never have to keep `alembic.ini` in sync with `.env`.

## Environment configuration

Every tunable is `.env`-driven (see `.env.example` for the catalog):

| Var | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql://pmis:pmis_dev_password@localhost:5432/pmis` | Primary DB connection |
| `SECRET_KEY` | (set explicitly) | JWT signing secret. **Must match** any sibling service (e.g. `pmis-user-service`) sharing the same auth domain |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `BOOTSTRAP_ADMIN_LOGIN` | `admin` | Seeded on first boot if no admin exists |
| `BOOTSTRAP_ADMIN_EMAIL` | `admin@example.com` | |
| `BOOTSTRAP_ADMIN_PASSWORD` | `admin123` | **Override in any non-dev environment** |

## Features

- **User Management** — CRUD, JWT authentication, password management, hard logout (jti blacklist)
- **Project Management** — Projects with status lifecycle, ownership, categories, baseline/version split
- **M/A/T/S Hierarchy** — Milestones / activities / tasks / subtasks with cross-version cascade
- **Dependencies** — `dependsOn` on activities/tasks/subtasks with hierarchy enforcement, cycle detection, status gate, soft-delete
- **Work Packages** — Tasks, issues, subtasks with project scoping
- **Meetings** — Meetings, participants, agenda items
- **Roles** — Global role definitions with RBAC enforcement
- **Project Members** — User-project membership management
- **Vendors + Resource Types** — Catalogs with project/milestone associations

## Tech Stack

FastAPI 0.135 | SQLAlchemy 2.0 | Alembic 1.18 | Pydantic 2.12 | Postgres 16 (SQLite for tests) | JWT (HS256) | Argon2id

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Testing

```bash
pytest                   # full suite (uses in-memory SQLite — fast + isolated)
pytest -k logout         # subset
```

Tests intentionally use in-memory SQLite for speed. Production code paths run against Postgres.

## Detailed Documentation

| Document | Description |
|----------|-------------|
| [Architecture & API Reference](consolidated_docs/ARCHITECTURE_AND_API_REFERENCE.md) | System architecture, database schema, all API endpoints, response formats, RBAC permissions |
| [Authentication & Security](consolidated_docs/AUTHENTICATION_AND_SECURITY.md) | JWT auth flow, RBAC, Swagger UI setup, frontend integration, security checklist |
| [Testing & Quality](consolidated_docs/TESTING_AND_QUALITY.md) | Test suites, coverage, code issues found/fixed, quality assessment |
| [Deployment & Integration](consolidated_docs/DEPLOYMENT_AND_INTEGRATION.md) | Installation, configuration, deployment checklist, frontend integration, monitoring |

## License

MIT
