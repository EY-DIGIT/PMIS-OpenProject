# SQLite → Postgres Migration (with Alembic)

This document captures the migration from SQLite to Postgres 16 that happened
on 2026-04-23, plus the exact steps needed to bring the stack back up after
any laptop reboot.

---

## Part 1 — What we did, start to end

### Starting state

- App: FastAPI monolith backed by a single SQLite file (`pmis.db`) in the
  project root.
- Schema: managed by `Base.metadata.create_all()` on every startup, plus a
  collection of inline `ALTER TABLE` statements in `app/infrastructure/db/session.py`
  to patch legacy `pmis.db` files column-by-column as new features landed.
- Hard logout was working; the dep feature with soft-delete was working; all
  175 tests green.

### Why we moved

Two specific reasons Postgres beats SQLite here:
1. **Concurrent writes from multiple processes.** SQLite relies on file
   locks; two FastAPI services talking to the same `pmis.db` on Windows
   would intermittently hit `database is locked` errors.
2. **Real schema management.** Inline `ALTER TABLE` blocks in `init_db()`
   don't scale past a handful of columns. Alembic gives us versioned,
   reviewable, reversible migrations.

### What we changed

**Configuration (`.env`, `.env.example`, `app/core/config.py`)**
- `DATABASE_URL` switched from `sqlite:///./pmis.db` to
  `postgresql://pmis:<pw>@localhost:5432/pmis`.
- Added `BOOTSTRAP_ADMIN_LOGIN / EMAIL / PASSWORD` env vars so the
  seeded admin credentials aren't hardcoded in Python.

**Schema management (Alembic)**
- `pip install alembic==1.18.4`
- `alembic init alembic` — creates `alembic/`, `alembic.ini`, `alembic/env.py`,
  `alembic/script.py.mako`, `alembic/versions/`
- Rewrote `alembic/env.py` to:
  - Read `DATABASE_URL` from `app.core.config.settings` (not `alembic.ini`)
  - Set `target_metadata = Base.metadata` after importing every model
- Generated the initial migration from current models:
  `alembic revision --autogenerate -m "initial schema"`
  → produces `alembic/versions/1272a77b9407_initial_schema.py` with all
  25 tables, indexes, partial-unique indexes, foreign keys.

**`init_db()` refactor (`app/infrastructure/db/session.py`)**
- If dialect is SQLite (test suite): keep `Base.metadata.create_all()` +
  all the legacy ALTER blocks exactly as before.
- If dialect is Postgres (runtime): run `alembic upgrade head` as a
  **subprocess** before any seeding happens.
- Subprocess pattern was chosen after the in-process `command.upgrade()`
  call hung — see "Errors" below.

**Infrastructure**
- Created `infra/docker-compose.yml` for Postgres 16 (Docker route)
- Ultimately switched to Postgres natively in WSL Ubuntu because Docker
  Desktop on Windows was unstable

**Documentation**
- Updated `README.md` with Postgres setup + Alembic workflow + env catalog.

### Final state

- `pmis.db` is no longer read at runtime; only in tests (in-memory).
- All 26 Postgres tables exist (25 app + `alembic_version`).
- Alembic auto-applies pending migrations on every app boot.
- Admin is seeded via env vars, idempotently.
- 175 tests + 3 skipped still pass on the SQLite test fixture.
- End-to-end smoke passed on Postgres: login → project → milestone →
  activities → dependency → status gate → tree → logout → token rejected →
  re-login works.

---

## Part 2 — Errors we hit and how we fixed them

### Error 1: Docker Desktop's daemon kept dying

**Symptom:** `docker ps` and `docker compose ...` returned
```
error during connect: Get "http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine...":
open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```
even though the Docker Desktop UI showed the container as running.

**Cause:** Docker Desktop on Windows has a known instability where the UI
process is up but the WSL backend that serves the CLI pipe dies silently
after sleep/wake or under memory pressure.

**Fix:** Full restart of Docker Desktop didn't reliably help. We switched
to **Postgres natively in WSL Ubuntu** via `sudo apt install postgresql-16`,
eliminating Docker entirely from the dev path.

### Error 2: Postgres reachable from WSL but not from Windows

**Symptom (from PowerShell):**
```
Test-NetConnection -ComputerName localhost -Port 5432
# TcpTestSucceeded : False
```
while the same command from inside WSL worked fine.

**Cause:** WSL2's default NAT mode doesn't auto-forward localhost from
Windows to the VM. Also, Postgres was bound to `127.0.0.1` inside WSL
(not `0.0.0.0`), so even if forwarding worked, only localhost inside
WSL would reach it.

**Fix (two parts):**

a) Bind Postgres to all interfaces inside WSL:
```bash
sudo sed -i "s/^#listen_addresses = 'localhost'/listen_addresses = '*'/" \
    /etc/postgresql/16/main/postgresql.conf
echo "host all all 0.0.0.0/0 scram-sha-256" | \
    sudo tee -a /etc/postgresql/16/main/pg_hba.conf
sudo service postgresql restart
```

b) Enable WSL2 mirrored networking so Windows and WSL share the network
namespace and `localhost` works from both sides:
```powershell
@"
[wsl2]
networkingMode=mirrored

[boot]
systemd=true
"@ | Out-File -FilePath "$env:USERPROFILE\.wslconfig" -Encoding ASCII

wsl --shutdown
```
After reopening Ubuntu, `Test-NetConnection localhost 5432` returned
`TcpTestSucceeded : True`.

Requires Windows 11 22H2+ and WSL 2.0+. Both checked.

### Error 3: `alembic upgrade head` hung when called from FastAPI startup

**Symptom:** `uvicorn` would log "Initializing database..." and then
hang forever. No error, no progress.

**Cause:** The in-process call `command.upgrade(alembic_cfg, "head")`
was conflicting with SQLAlchemy's connection pool (which the FastAPI app
was also initializing) plus Python logging reconfiguration via
`fileConfig()` inside `alembic/env.py`. Hard to pin down the exact
deadlock but the pattern is well-known.

**Fix:** Run alembic as a **subprocess** with a timeout. Gets a clean
Python process, no shared logger config, no shared engine pool, clear
exit code. Implemented in `app/infrastructure/db/session.py`:
```python
subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    cwd=project_root, capture_output=True, text=True, timeout=120
)
```

### Error 4: `UnboundLocalError: cannot access local variable 'logging'`

**Symptom:** `init_db()` crashed with `UnboundLocalError` on the
success log line that followed the alembic upgrade.

**Cause:** Classic Python scoping bug. The SQLite-drift block later
in the function had `import logging` inside a `try:` clause. Python
detects the assignment at function-scope and treats `logging` as a
**local** variable throughout the whole function — even before the
`import` line executes. So the earlier `logging.info(...)` call
referenced an unbound local.

**Fix:** Deleted the redundant `import logging` inside the drift block
(it's already imported at module level). Added a comment explaining
why not to re-add it.

### Error 5: `ModuleNotFoundError: No module named 'psycopg2'`

**Symptom:** uvicorn crashed at import time.

**Cause:** `requirements.txt` listed `psycopg2-binary==2.9.9`, and I had
installed it globally, but the project's **venv** didn't have it.

**Fix:** `pip install psycopg2-binary==2.9.9 alembic==1.18.4` with the
venv active.

### Error 6: `password authentication failed for user "pmis"`

**Symptom:** Postgres rejected the app's connection after we changed
the Postgres user's password.

**Cause:** Password was changed in Postgres with `ALTER USER`, but
`.env`'s `DATABASE_URL` still had the old password.

**Fix:** Update `.env` to match. Two gotchas to remember:
- `@` in a password must be URL-encoded as `%40` in the connection
  string. We avoided it by picking a password without special characters
  (`admin123`).
- Changing the Postgres password does NOT affect app user credentials
  (`admin` / `admin123` in Swagger). They're two different systems —
  the DB user is `pmis`, the app user is `admin`.

---

## Part 3 — Restart from scratch after a laptop reboot

This is the runbook. Follow the steps in order.

### Step 0 — Verify WSL came back up

After Windows boot, WSL auto-starts when you open Ubuntu. It doesn't
run in the background otherwise. Just opening the Ubuntu app is enough.

### Step 1 — Start Postgres inside WSL

We configured `systemd=true` in `.wslconfig`, so Postgres SHOULD auto-start.
Verify:

```bash
# In Ubuntu
sudo service postgresql status
```

**If it's running** (`online`), skip to Step 2.

**If it's stopped:**
```bash
sudo service postgresql start
```

If you also want it to auto-start on every WSL boot (one-time):
```bash
sudo systemctl enable postgresql
```

### Step 2 — Verify Postgres is reachable from Windows

In **PowerShell**:
```powershell
Test-NetConnection -ComputerName localhost -Port 5432
```

Expected: `TcpTestSucceeded : True`.

**If False:** mirrored networking didn't apply. Run in PowerShell:
```powershell
wsl --shutdown
```
Then reopen Ubuntu (Postgres restarts via systemd), and test again.

### Step 3 — Activate the venv + install deps (only if needed)

```powershell
cd C:\Users\WC544QK\Downloads\PMIS-OpenProject
.\venv\Scripts\Activate.ps1
```

If this is the first boot after pulling new code, refresh deps:
```powershell
pip install -r requirements.txt
```

### Step 4 — Boot uvicorn

```powershell
uvicorn app.main:app --reload
```

Expected logs:
```
Starting application...
Initializing database...
alembic upgrade head completed successfully
Database initialized successfully
Application PMIS API v3.0.0 started
Uvicorn running on http://127.0.0.1:8000
```

On a normal restart, Alembic sees the DB is already at head and is a
no-op — you just see the success line.

### Step 5 — Verify the app is healthy

Open http://localhost:8000/docs in a browser. Should load Swagger UI.

Quick login test:
- **POST `/api/v3/users/login`** → `{"login":"admin","password":"admin123"}`
- Should get 200 with an access token.

---

## Part 4 — Troubleshooting

### "Connection refused" to Postgres

Something in the chain between Windows → WSL → Postgres is down.

Diagnose in order:
1. `Test-NetConnection -ComputerName localhost -Port 5432` from PowerShell.
   If False: either WSL isn't running, Postgres isn't running, or
   mirrored networking broke.
2. Open Ubuntu and run `sudo service postgresql status`. If stopped,
   `sudo service postgresql start`.
3. `ss -tlnp | grep 5432` in Ubuntu should show `0.0.0.0:5432` listening.
4. If Postgres is up in WSL but Windows can't reach it, run
   `wsl --shutdown` in PowerShell and reopen Ubuntu.

### "password authentication failed for user pmis"

`.env` and Postgres disagree on the password.

- Check `.env`'s `DATABASE_URL` for the password portion.
- Compare with what you set in Postgres last. If unsure, reset:
  ```bash
  sudo -u postgres psql -c "ALTER USER pmis WITH PASSWORD 'admin123';"
  ```
- Update `.env` to match.
- Restart uvicorn.

### "alembic upgrade head failed"

Usually downstream of a connection failure. Read the `STDERR:` section
of the error — most of the time it's `psycopg2.OperationalError`
(connection refused / auth failed). Fix the connection first.

If the error says something about migration conflicts or duplicate
tables, the DB state got out of sync with the migration history.
Nuclear reset:
```bash
sudo -u postgres psql -c "DROP DATABASE pmis;"
sudo -u postgres psql -c "CREATE DATABASE pmis OWNER pmis;"
```
Then restart uvicorn — Alembic will rebuild everything from scratch
and the seeder will recreate admin.

### "ModuleNotFoundError: No module named 'psycopg2'" (or alembic)

Venv is missing deps. From the project root with venv active:
```powershell
pip install -r requirements.txt
```

### I want to wipe the DB and start over (dev only)

```bash
# In Ubuntu
sudo -u postgres psql -c "DROP DATABASE pmis;"
sudo -u postgres psql -c "CREATE DATABASE pmis OWNER pmis;"
```

Next uvicorn boot will run all migrations from scratch and re-seed the
admin. Loses all your data — use only when you're fine with that.

---

## Part 5 — Useful one-liners

### Health check (run with venv active)

```powershell
python -c "
from sqlalchemy import create_engine, text
from app.core.config import settings
e = create_engine(settings.DATABASE_URL, connect_args={'connect_timeout':5})
with e.connect() as c:
    print('Dialect    :', e.dialect.name)
    print('Postgres   :', c.execute(text('SELECT version()')).scalar()[:55])
    print('Alembic    :', c.execute(text('SELECT version_num FROM alembic_version')).scalar())
    print('Tables     :', c.execute(text(\"SELECT count(*) FROM information_schema.tables WHERE table_schema='public'\")).scalar())
    print('Admin user :', c.execute(text(\"SELECT login FROM users WHERE login=:l\"), {'l': settings.BOOTSTRAP_ADMIN_LOGIN}).scalar())
"
```

### Inspect Postgres directly

```bash
# In Ubuntu
psql "postgresql://pmis:admin123@localhost:5432/pmis"
# Then use: \dt (list tables), \d projects (describe table), \q (quit)
```

### Create a new migration after changing a model

```powershell
alembic revision --autogenerate -m "short description"
# review alembic/versions/<new>.py
alembic upgrade head    # apply it (or let the next uvicorn boot do it)
```

### Run the test suite (still SQLite, fast)

```powershell
pytest
```

Expected: `175 passed, 3 skipped`.

---

## Part 6 — Key files to know

| File | What it does |
|---|---|
| `.env` | Runtime config (gitignored). `DATABASE_URL`, `SECRET_KEY`, bootstrap admin |
| `.env.example` | Template for `.env`. Committed. |
| `app/core/config.py` | Loads `.env` into a `settings` object |
| `app/infrastructure/db/session.py` | Engine + `init_db()` (alembic upgrade + seeders) |
| `alembic/env.py` | Alembic's runtime config — wired to app's `settings` |
| `alembic/versions/1272a77b9407_initial_schema.py` | The initial migration |
| `alembic.ini` | Alembic boilerplate. Not much of interest. |
| `infra/docker-compose.yml` | Alternative Postgres route (we don't use it now but it's there) |

---

## Part 7 — What we did NOT do (known follow-ups)

- **Prod deployment config** — this is all local dev. Staging/prod will
  need real secrets, TLS, proper Postgres with backups, etc.
- **Rotate `SECRET_KEY`** — still using the default placeholder. Fine
  for dev; must change before any real deploy.
- **Blacklist cleanup cron** — `revoked_tokens` table grows unbounded
  until you wire `cleanup_expired()` to a scheduler. Not urgent for dev.
- **The `pmis-user-service` microservice split** — plan is locked, to
  be executed next.
