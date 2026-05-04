# Testing and Code Quality

## Test Suite Overview

Test framework: pytest + FastAPI `TestClient`. SQLite in-memory DB per test, app `init_db` short-circuited so each test starts from a clean slate (see [tests/conftest.py](../tests/conftest.py)).

Last run: **494 passed, 3 skipped** (full suite, post-doc 24).

### Test Execution

```bash
# Full suite
.venv/Scripts/python.exe -m pytest tests/ -q

# A single file
.venv/Scripts/python.exe -m pytest tests/test_dependencies.py -q

# A single class / method
.venv/Scripts/python.exe -m pytest tests/test_rbac.py::TestRolePermissionManagement -v

# With coverage
.venv/Scripts/python.exe -m pytest tests/ --cov=app --cov-report=html
```

### Test Files

| File | Scope |
|------|-------|
| `test_auth.py` | Login, refresh-token rotation + grace window (doc 19), logout, introspect |
| `test_users.py` | User CRUD, vendor/division required-fields, last-admin lockout, restore |
| `test_rbac.py` | DB-driven RBAC (doc 21B): permission catalog CRUD, role-permission management, user-role assignment, lockout protection, /me/permissions, master-router relocation (doc 21B follow-up) |
| `test_roles.py` | Legacy role CRUD path (deprecation headers stamped) |
| `test_master_data.py` | `/api/v3/master/*` (doc 20): divisions / project_status_transitions / resource_types / vendors |
| `test_projects.py` | Project CRUD, version creation, baseline lifecycle, **past-startDate test** (doc 24 part 1), inclusive-date validation |
| `test_baseline_version_propagation.py` | Baseline → active-version propagation for M/A; lock guards |
| `test_dependencies.py` | Activity / task / subtask deps, soft-delete, cycle detection, cross-milestone, cross-task (post-doc-24-part-3 — no parent hierarchy rule), milestone-to-milestone deps + propagation (doc 21A) |
| `test_nested_subtasks.py` | **Doc 24 part 2**: nested-subtask creation, variable-depth labels, cross-branch deps, cascade-delete subtree, position uniqueness per parent, depth cap env var, tree response shape |
| `test_labels.py` | Display labels (doc 22) — parse / format / resolve / compute / build_label_index |
| `test_position_heal.py` | Self-heal of duplicate live positions before the partial-unique index can be added (doc 22 hotfix) |
| `test_hierarchy.py` | Project tree shape: M → A → T → S |
| `test_long_cycle_dependency.py` | Cycle-detection stress test |
| `test_activity_split.py` | Standard / resource activity create-endpoint split |
| `test_catalogs_and_other_reason.py` | `category='others'` + `categoryOtherReason`; deprecated catalog endpoints |
| `test_new_features.py` | Doc-12+ feature suite (vendors, milestone fields incl. depends_on, contact details, phoneNumber required) |
| `test_comments.py`, `test_attachments.py` | Polymorphic comments/attachments on M/A/T/S |
| `test_meetings.py`, `test_project_members.py`, `test_work_packages.py` | Adjacent modules |

### Test Categories Covered

- **Auth**: login flows, refresh-token rotation with 120s grace window, logout, introspect (with DB-resolved `isAdmin`).
- **DB-driven RBAC** (doc 21B): permission catalog CRUD, role lifecycle, role-permission grants, user-role / direct user-permission assignments, last-admin lockout, admin-role mutation rejection, deprecation header on legacy paths.
- **Master data router** (doc 20 + 21B follow-up): divisions / transitions / resource_types / vendors / roles / permissions all reachable under `/api/v3/master/*`.
- **Project lifecycle**: create / update / publish / save / close / suspend / version-create / soft-delete with cascade.
- **Baseline-to-version propagation**: M/A create/update/delete cascades; milestone dependency-edge propagation.
- **Dependencies**: same-project enforcement, no self-edge, cycle detection, soft-delete edge history, cross-milestone (locked-in by explicit tests), cross-task (no hierarchy rule per doc 24 part 3), milestone-to-milestone (doc 21A).
- **Nested subtasks** (doc 24 part 2): unlimited nesting, label depth, cascade subtree on delete, position uniqueness per parent, env-var depth cap.
- **Display labels** (doc 22): parse, format, resolve label → id, compute label, bulk index, position-heal hotfix.
- **HAL+JSON**: response shape validation across endpoints.
- **Validation**: schema (422) and service-layer (422 / 403 / 409) errors.
- **Edge cases**: empty arrays, special characters, null optionals, idempotent creates.

## Code Quality Assessment

### Strengths
- Clean layered architecture (Routes → Controllers → Services → Repositories) with no skip-layer access.
- Type-safe at every boundary (Pydantic on the wire, dataclasses in domain, SQLAlchemy in repos).
- **DB-driven RBAC** (doc 21B): permissions are extensible at runtime; the legacy in-memory `Role -> Permission` dict is gone. Per-request hydration is one DB query.
- **Soft-delete everywhere** with restore endpoints — no destructive operations except the cleanup of revoked-token rows.
- **Auto-healing dev DB** for SQLite drift; **Alembic + auto-`upgrade head` on boot** for Postgres.
- **Audit trail** for project/M/A writes via `project_audit_logs`, including baseline-to-version cascade rows.
- **HAL+JSON envelope** is centralized in `core/response.py`; controllers don't hand-roll responses.
- **Display labels** (doc 22) eliminate FE-side label computation and let `dependsOn` accept either UUIDs or labels.
- **Single alembic head** maintained across every revision; merge revisions are explicit when chains diverge.

### Production Recommendations
- Use PostgreSQL (default migration path is `alembic upgrade head` on boot).
- Set strong `SECRET_KEY` (32+ chars) via env.
- Rotate the bootstrap admin password via `PATCH /api/v3/users/{id}/password` and consider deleting the bootstrap user once another admin is provisioned (last-admin guard prevents lockout).
- Enable HTTPS at the proxy layer.
- Set `CORS_ORIGINS` to specific FE origins.
- Tune `REFRESH_TOKEN_GRACE_SECONDS` per FE refresh-storm characteristics (default 120 is conservative).
- Consider setting `SUBTASK_MAX_NESTING_DEPTH` if the UX warrants a soft cap on nesting depth (default `None` = unlimited).
- Disable Swagger UI in production (`openapi_url=None` in `app/main.py`) if the API is not publicly browsable.

## Previous Documentation Cleanup
A prior consolidation reduced 55 scattered docs into the [consolidated_docs/](.) bundle. The bundle is hand-maintained — every doc-numbered change in [planned_changes/](../planned_changes/) is meant to be reflected here within the same PR.
