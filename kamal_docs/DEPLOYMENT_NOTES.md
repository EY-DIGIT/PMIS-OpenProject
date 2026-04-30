# Deployment Notes

A running log of changes that need DevOps action when deploying this
repo. Read the latest entry before each deploy. Newest at the top.

For the full environment-variable reference, see [`.env.example`](../.env.example)
at the repo root — that file is the source of truth for "what env vars
exist". This document is for **what changed in each release** and what
DevOps needs to do.

---

## 2026-04-30 — Resource type rename: CCM → CCN

### What changed

- The seeded resource_type with code ``ccm`` ("Change Control Memo")
  is renamed to ``ccn`` ("Change Control Notice") to match the product
  spec. Affects the catalog returned by ``GET /api/v3/resource_types``
  and the seed inside ``init_db``.
- Alembic migration ``e7f4a8b9c1d2`` auto-applies on boot and renames
  any existing ``ccm`` row in-place. The row's UUID ``id`` is preserved,
  so any ``activity_resources.type_of_resource_id`` references already
  pointing at the old row remain valid — they now resolve to a row
  whose code/name say "ccn" / "Change Control Notice".
- Idempotent: ``WHERE code = 'ccm'`` makes a re-run a no-op on a DB
  that's already migrated, or on a fresh install where ``init_db``
  seeded ``ccn`` directly.

### DevOps actions on the server

```bash
cd <repo>
git pull
sudo systemctl restart <monolith-service>   # or docker compose up -d
```

Migration runs automatically. No manual SQL, no env vars.

### Verify

```bash
curl -H "Authorization: Bearer <token>" http://<server>/api/v3/resource_types
```

Response's ``data._embedded.elements`` should contain ``rfp``, ``asg``,
``ccn``. The ``ccm`` code should no longer appear.

### Failure mode if FE keeps sending the old "ccm" code

It was already wrong — FE should send ``typeOfResourceId`` as the
row's UUID, not the code. After this rename, sending ``"ccm"`` (or
``"ccn"``) as ``typeOfResourceId`` still fails with
``The selected 'type of resource' could not be found or is inactive.``
The FE fix (use the UUID from ``GET /resource_types``) remains
required regardless of the rename.

### Rollback

```bash
cd <repo>
alembic downgrade -1   # restores 'ccm' / 'Change Control Memo'
git revert <commit>
```

---

## 2026-04-28 — User Management batch (vendor / division / project mapping / soft-delete)

### What changed

- `users` table gains five new columns: `vendor_id` (FK to vendors),
  `division`, `division_other`, `deleted_at`, `deleted_by`.
- Alembic migration `c262a1b3e895` auto-applies on boot — additive only,
  all new columns are nullable, safe to roll forward.
- Behavioural changes to `/api/v3/users/*`:
  - `POST /create` now **requires** `vendorId`, `division`, and at least
    one entry in `projectIds`. Existing clients must be updated.
  - `GET /users` is now sorted **newest-first** (`created_at DESC`).
  - Default list filter excludes soft-deleted users (admin can opt in
    with `?include_deleted=true`).
  - `DELETE /users/{id}` now **soft-deletes** — sets `deleted_at` +
    `status='inactive'`. Project mappings stay intact for restore.
  - `PATCH /users/{id}` accepts `status='inactive'` (was rejected before).
    Setting `status='active'` on a soft-deleted user **restores** them
    (clears `deleted_at`).
  - Response embeds `vendor`, `division`, `divisionOther`, `projects`
    (filtered to live + non-closed) on every user response.
- Bootstrap admin remains valid (vendor/division NULL is permitted at
  the DB layer; the API enforces the requirement only on incoming
  create requests).

### DevOps actions on the server

#### 1. Pull and restart

```bash
cd <repo>
git pull
sudo systemctl restart <monolith-service>   # or docker compose up -d
```

The Alembic migration runs automatically on boot. No manual SQL needed.

#### 2. No new env vars

This release introduces zero new environment variables. The existing
`.env` works as-is.

#### 3. Verify

```bash
curl http://<server>/health        # should still be 200, unchanged shape
curl http://<server>/api/v3/users -H "Authorization: Bearer <admin>"
```

The user list response should now include `vendor`, `division`,
`projects`, and `deletedAt` fields on each user.

### Failure mode if rolled out without coordinating with frontend

The frontend's existing user-create form (if it doesn't yet send
`vendorId` / `division` / `projectIds`) will start getting `422`
responses. That's the intended behaviour, but coordinate the frontend
update timing with the FE team to avoid downtime on the create flow.

### Rollback

```bash
cd <repo>
alembic downgrade -1   # drops the new columns
git revert <commit>
```

Soft-deleted-user data and vendor/division values for any rows created
since the upgrade are lost — the columns get dropped. Document any
test data created post-upgrade if you'll need to restore.

### Emergency recovery — locked out of admin

The user-management batch protects against API-level lockout: the
service layer refuses to (a) delete your own account, (b) demote
yourself from admin, (c) demote/deactivate the last active admin.
Together those guards make it impossible to leave the system with
zero usable admins via the HTTP surface alone.

**However**, direct DB writes, a botched migration, or a failed
init_db seed can still leave the DB without a usable admin. In
that case login returns 401 with no API-side recovery path.
Recovery requires direct Postgres access:

#### A. Restore a soft-deleted admin (most common case)

```sql
UPDATE users
SET deleted_at = NULL,
    deleted_by = NULL,
    status = 'active'
WHERE login = 'admin';
```

#### B. Reset the bootstrap admin password

The bootstrap admin's credentials come from env vars
``BOOTSTRAP_ADMIN_LOGIN`` (default: ``admin``),
``BOOTSTRAP_ADMIN_EMAIL`` (default: ``admin@example.com``),
``BOOTSTRAP_ADMIN_PASSWORD`` (default: ``admin123``). To reset
the password to whatever's currently in the env, hash it with the
app's bcrypt helper and ``UPDATE``:

```bash
# In the repo's venv:
python3 -c "from app.core.security import hash_password; print(hash_password('<new-password>'))"
# Copy the $2b$... output, then:
psql -d pmis -c "UPDATE users SET hashed_password = '<paste-hash>', \
                       status = 'active', deleted_at = NULL, \
                       deleted_by = NULL \
                 WHERE login = 'admin';"
```

(Quote the hash with single quotes — bcrypt strings contain ``$``
which the shell would otherwise expand.)

#### C. No admin exists at all (init_db never ran successfully)

The bootstrap admin is created idempotently on every boot if no
user with ``login = BOOTSTRAP_ADMIN_LOGIN`` exists. So restarting
the app should re-seed it. If it doesn't, the boot logs will show
why — usually a migration failure. Fix the migration root cause,
restart, and the admin reappears.

---

## 2026-04-27 — Comments & Attachments feature

### What changed

- New endpoints under `/api/v3/{milestones,activities,tasks,subtasks}/{id}/comments`
  and `/api/v3/.../{id}/attachments`, plus id-scoped `/comments/{id}` and
  `/attachments/{id}/download` routes.
- New tables `comments` and `attachments` (alembic migration auto-applies on boot).
- New file-storage subsystem. The app reads/writes attachment files to a
  filesystem path configured via env. In production this path points at
  an NFS mount; in dev it's a local folder. The app code itself is
  storage-agnostic — it just opens files.

### DevOps actions on the server

#### 1. Update the server's `.env`

Add the following block to `.env` on the server:

```bash
# ---- File attachments ----

# REQUIRED — local path where attachment bytes are stored. In production
# this MUST be the NFS mount point. Without setting this explicitly,
# the app falls back to ./local_uploads inside its working directory,
# which won't survive container restarts and won't be backed up.
ATTACHMENTS_STORAGE_BASE_PATH=/mnt/pmis_files

# RECOMMENDED — informational. Surfaced in /health so support can verify
# which file store this instance is wired to. The app NEVER connects to
# these directly — the OS-level NFS mount does. Leave empty if unknown.
ATTACHMENTS_NFS_SERVER=<nfs-server-ip-or-hostname>
ATTACHMENTS_NFS_EXPORT=<exported-path-on-nfs-server>

# OPTIONAL — sensible defaults already exist in code. Set only to override.
ATTACHMENTS_MAX_BYTES=26214400
ATTACHMENTS_ALLOWED_EXTENSIONS=pdf,doc,docx,xls,xlsx,ppt,pptx,txt,csv,png,jpg,jpeg,gif,webp
ATTACHMENTS_SUBDIR_STRATEGY=year_month
ATTACHMENTS_RETENTION_DAYS=90
ATTACHMENTS_ON_UNAVAILABLE=fail
```

Only `ATTACHMENTS_STORAGE_BASE_PATH` is functionally required.
Everything else either has a working default or is informational.

#### 2. Confirm the NFS mount is set up at the path above

The OS (not the app) handles the NFS mount. Typical `/etc/fstab` entry:

```
<nfs-server>:<exported-path>   /mnt/pmis_files   nfs   defaults,_netdev   0  0
```

The mounted directory must be writable by whatever UID the application
process runs as. Verify with:

```bash
sudo mount | grep pmis_files
ls -la /mnt/pmis_files
sudo -u <app-user> touch /mnt/pmis_files/.write_probe && rm /mnt/pmis_files/.write_probe
```

#### 3. (If running via Docker) bind-mount the NFS path into the container

In the monolith's `docker-compose.yml`, add the volume mount so the
container can see the host's NFS mount:

```yaml
services:
  monolith:
    # ... existing config ...
    volumes:
      - /mnt/pmis_files:/mnt/pmis_files:rw
```

The path is the same on host and container so logs and stack traces
stay readable.

#### 4. Restart the monolith

```bash
sudo systemctl restart <monolith-service>          # if systemd
docker compose up -d --build monolith              # if docker-compose
```

On boot, the alembic migration `4825a33f9ed3_add_comments_and_attachments_tables`
automatically runs and creates the `comments` and `attachments` tables.
The migration is **additive only** — safe to roll back with
`alembic downgrade -1` if needed.

#### 5. Verify

```bash
curl http://<server>/health
```

Expected response includes:

```json
{
  "status": "healthy",
  "storage": {
    "healthy": true,
    "base_path": "/mnt/pmis_files",
    "nfs_server": "<nfs-server-ip>",
    "nfs_export": "<exported-path>",
    "max_bytes": 26214400
  }
}
```

If `storage.healthy` is `false`, the mount isn't reachable / writable.
Check the mount, the path env var, and the app's UID/permissions.

### Failure mode if DevOps skips these steps

- App boots fine.
- `GET /health` reports `storage.healthy: false`.
- Comments without files: still work.
- Comments **with** files, and standalone attachment uploads: return
  HTTP 503 with `error_type: "storage_unavailable"`.
- Downloads of any file already uploaded earlier: also 503 if mount is
  inaccessible.

No data loss. No crash. Just attachment-related endpoints degrade until
the mount is fixed.

### Rollback

If something is wrong with the migration:

```bash
cd <monolith-repo>
alembic downgrade -1
```

This drops the `comments` and `attachments` tables. The app will still
run; the new endpoints will return 500 until either the migration is
re-applied or the route handlers are removed.

---

## How to use this document going forward

For every PR/feature that requires DevOps action on the server (new
env var, new infra, schema change with manual step, new compose volume,
etc.), add a new section at the top with the date and a short title.
Keep older entries — they're the audit trail.

If a release needs no DevOps action, no entry is required.
