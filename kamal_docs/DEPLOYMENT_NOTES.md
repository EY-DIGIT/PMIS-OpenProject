# Deployment Notes

A running log of changes that need DevOps action when deploying this
repo. Read the latest entry before each deploy. Newest at the top.

For the full environment-variable reference, see [`.env.example`](../.env.example)
at the repo root — that file is the source of truth for "what env vars
exist". This document is for **what changed in each release** and what
DevOps needs to do.

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
