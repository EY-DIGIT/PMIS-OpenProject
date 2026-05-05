# Testing and Code Quality

## Test Suite Overview

Test framework: pytest + FastAPI `TestClient`. SQLite in-memory DB per test, app `init_db` short-circuited so each test starts from a clean slate (see [tests/conftest.py](../tests/conftest.py)).

Last run: **688 passed, 3 skipped** (full suite, post-doc 31).

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
| `test_code_generators.py` | **Doc 25** — unit tests for `app/shared/code_generators.py`: slug formation, IST timestamp, collision suffixing, exclude-id behavior, recognizer regexes |
| `test_doc25_codes.py` | **Doc 25** — end-to-end: code generation on create, polymorphic lookup (UUID or `VN-`/`US-` code), response shape includes the new field, soft-delete + restore by code, cross-entity vendor input acceptance, unknown-code rejection |
| `test_doc26_user_uuid.py` | **Doc 26** — asserts `users.id` is a UUID across fixture + create paths; lookup by UUID and by `US-` code; login response embeds UUID; JWT `user_id` survives roundtrip as UUID; project `createdBy` carries a UUID |
| `test_doc26_full_endpoint_sweep.py` | **Doc 26** — exhaustive sweep over every endpoint that exposes a user-id (list/get/me/login/refresh/introspect, RBAC me/roles/permissions, project `createdBy`/`updatedBy`, audit log `actor_id`, vendor `deletedBy`, comment `author.id`) plus a schema walk enumerating every FK column targeting `users.id` and confirming `String(36)` |
| `test_doc27_date_equality.py` | **Doc 27** (kamal21) — IST/UTC date-equality fixes via `UtcDateTime` column type so cross-format milestone/project date comparisons land on the same calendar day |
| `test_doc27_stale_jwt_guard.py` | **Doc 27 hotfix** (kamal21) — pre-doc-26 stale JWTs (integer `user_id`) return 401 instead of 500 |
| `test_doc28_subtask_list_nested.py` | **Doc 28** (kamal21) — nested subtask listing fix |
| `test_doc29_calendar_date_normalization.py` | **Doc 29** (kamal21) — IST calendar-date normalization across submission formats |
| `test_doc30_dep_dates.py` | **Doc 30** — generic dep-date enforcement (activities/tasks/subtasks): forward (source.start ≥ target.end on create + update), reverse (target.end push past existing successor.start), equality branch, multi-successor enumeration, empty/null handling. (Milestone tests moved to doc 31.) |
| `test_doc30_publish_gate.py` | **Doc 30** — publish-time structural gate: zero-milestones + empty-milestone rejections, lists every empty milestone, soft-deleted activities count, version publish gate, version inherits publishable graph |
| `test_doc31_milestone_dep_rules.py` | **Doc 31** — milestone-specific dep-date rules: start floor (`source.start >= target.start`, equality OK), strict end (`source.end > target.end`, equality REJECTED), combined-error enumeration, forward + reverse re-validation on date edits, status-completion gate (`status='completed'` blocked while any dep target is incomplete) |
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
- **Dependencies**: same-project enforcement, no self-edge, cycle detection, soft-delete edge history, cross-milestone (locked-in by explicit tests), cross-task (no hierarchy rule per doc 24 part 3), milestone-to-milestone (doc 21A), **dep-date enforcement (doc 30)** — for activities/tasks/subtasks: `source.start >= target.end` (equality allowed) on every create/update path; reverse direction guarded so editing a target's end_date that would invalidate an existing successor is rejected with all offenders named.
- **Milestone-specific dep rules (doc 31)** — milestones use a different rule than the other three kinds: `source.start >= target.start` (equality OK) AND `source.end > target.end` (strict, equality REJECTED). Both directions guarded. Plus a status-completion gate: a milestone cannot be marked `completed` until every dep target is also `completed`.
- **Publish gates** (doc 30): publish rejects projects with zero milestones (`no_milestones`) and any milestone with zero live activities (`milestone_without_activity`); applies uniformly to baselines and versions.
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
