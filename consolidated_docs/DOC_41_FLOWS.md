# Doc 41 — flows summary (monolith stub)

**Canonical flows summary lives in
[`PMIS-user-management/consolidated_docs/DOC_41_FLOWS.md`](../../PMIS-user-management/consolidated_docs/DOC_41_FLOWS.md).**
This file is a stub so monolith-side reviewers can find the doc by
name.

## Why the canonical doc lives in user-management

User-management is the authoritative writer for the doc-41 RBAC
tables (`user_role_assignments`, `roles`, `permissions`,
`role_permissions`). Monolith holds mirror models so its scope-aware
route helpers (`require_project_permission`,
`require_org_permission`) can hydrate per-scope permissions on every
request — but every RBAC write at runtime flows through user-mgmt.
Splitting flow docs across the two repos creates drift; one
canonical doc with a stub here is the cleaner pattern.

## Monolith-side facts you might need

- Auth middleware lives at [`app/core/middleware/auth.py`](../app/core/middleware/auth.py).
- The two scope-aware helpers + ancestor resolver chain live at
  [`app/core/middleware/rbac.py`](../app/core/middleware/rbac.py).
- M-A-T-S write routes that gate on `require_project_permission`:
  - [`app/api/v3/projects/routes.py`](../app/api/v3/projects/routes.py) — PATCH/DELETE/save/publish/close
  - [`app/api/v3/milestones/routes.py`](../app/api/v3/milestones/routes.py) — POST/PATCH/DELETE/restore
  - [`app/api/v3/activities/routes.py`](../app/api/v3/activities/routes.py)
  - [`app/api/v3/tasks/routes.py`](../app/api/v3/tasks/routes.py)
  - [`app/api/v3/subtasks/routes.py`](../app/api/v3/subtasks/routes.py)
  - [`app/api/v3/project_members/routes.py`](../app/api/v3/project_members/routes.py)
- Comment + attachment writes deliberately stay on the union path —
  see canonical doc § "Known follow-ups" for rationale.
