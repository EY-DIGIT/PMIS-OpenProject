# PMIS Python — Architecture and API Reference

**Project**: PMIS (Project Management Information System) — FastAPI backend
**Version**: 3.0.0
**Status**: Production-ready
**Last refresh**: 2026-05-06 (after doc 35)

---

## 1. Technology Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.135.3 |
| Database | SQLite (dev/tests) / PostgreSQL 16 (production) |
| ORM | SQLAlchemy 2.0.49 |
| Migrations | Alembic (auto-run on boot for non-SQLite engines) |
| Authentication | JWT HS256, Argon2id password hashing |
| Validation | Pydantic 2.12.5 |
| API Format | HAL+JSON envelope (OpenProject v3 compatible) |
| Python | 3.12 |
| Server | Uvicorn (dev) / Gunicorn + Uvicorn workers (prod) |

---

## 2. Architecture Overview

### Layered Architecture (DDD-flavored)

```
┌─────────────────────────────────────────────────────────────┐
│ API Layer (routes, controllers, schemas)                    │
├─────────────────────────────────────────────────────────────┤
│ Service Layer (business logic, returns ServiceResult<T>)    │
├─────────────────────────────────────────────────────────────┤
│ Domain Layer (pure business entities — no framework deps)   │
├─────────────────────────────────────────────────────────────┤
│ Infrastructure (repositories, SQLAlchemy ORM, DB session)   │
├─────────────────────────────────────────────────────────────┤
│ Core (security, RBAC middleware, config, errors, response)  │
└─────────────────────────────────────────────────────────────┘
```

### Architectural Principles

1. **Separation of concerns** — each layer has a single responsibility.
2. **Unidirectional dependencies** — no circular imports.
3. **Domain layer is framework-free** — pure dataclasses.
4. **Repository pattern** — all DB access through repos; repos return domain entities.
5. **Service layer** — business logic, returns `ServiceResult<T>`; no HTTP / RBAC concerns.
6. **Controller layer** — HAL+JSON projection only; no business logic.
7. **Route layer** — declares URL + permission code only.
8. **RBAC** — string-coded `require_permission("…")` dependency, hydrated per-request from the DB.
9. **Response format** — centralized HAL+JSON envelope via `core/response.py` and `core/base_controller.py`.

### Directory Structure (current state)

```
app/
├── main.py                            # Application entry point
├── core/
│   ├── config.py                      # Settings (Pydantic BaseSettings)
│   ├── security.py                    # JWT + Argon2 password hashing
│   ├── rbac.py                        # Legacy enums kept for back-compat
│   ├── permissions.py                 # Canonical permission code registry (doc 21B)
│   ├── response.py                    # HAL+JSON formatters
│   ├── base_controller.py             # ok / created / no_content / error / stamp_deprecation
│   ├── errors.py                      # NotFoundError, ValidationError, AuthorizationError, …
│   ├── dependencies.py                # FastAPI DI helpers
│   ├── project_lock.py                # Baseline-vs-version writability guards
│   └── middleware/
│       ├── auth.py                    # JWT decode + per-request perm hydration (doc 21B)
│       ├── rbac.py                    # require_permission(string code) dependency
│       └── logging.py                 # X-Request-ID + duration logging
├── api/
│   ├── router.py                      # Central router; mounts every v3 module
│   └── v3/
│       ├── users/                     # Users + RBAC user-side assignments
│       ├── projects/                  # Projects (incl. versions, audit, baseline_version_sync)
│       ├── project_members/
│       ├── roles/                     # Legacy /roles + /roles/{id}/permissions (deprecated → /master/roles)
│       ├── permissions/               # Legacy /permissions catalog (deprecated → /master/permissions)
│       ├── master_data/               # Consolidated /api/v3/master/* router (doc 20 + 21B follow-up)
│       ├── milestones/                # M layer — depends_on edges (doc 21A)
│       ├── activities/                # A layer
│       ├── tasks/                     # T layer (version-only)
│       ├── subtasks/                  # S layer (version-only; nested per doc 24)
│       ├── tree/                      # GET /projects/{id}/tree — full nested response
│       ├── catalogs/                  # Legacy GETs (deprecated → /master)
│       ├── vendors/                   # Legacy CRUD (deprecated → /master/vendors)
│       ├── resource_types/            # Legacy GETs (deprecated → /master/resource_types)
│       ├── work_packages/             # OpenProject-style WPs — live, not in M/A/T/S graph
│       ├── work_package_types/        # WP catalog
│       ├── meetings/
│       └── comments/                  # Polymorphic comments on M/A/T/S; doc 35 — attachments folded in
├── domain/                            # Pure business entities
├── infrastructure/db/
│   ├── session.py                     # Engine, sessionmaker, init_db, drift healers
│   ├── models/                        # 36 SQLAlchemy models (doc 33 +3, doc 35 −1)
│   └── repositories/                  # Per-aggregate data access
└── shared/
    ├── service_result.py              # ServiceResult<T>
    ├── pagination.py                  # 1-indexed page helpers
    ├── labels.py                      # M/A/T/S display labels (doc 22, doc 24)
    ├── position_heal.py               # Self-heal duplicate live positions (doc 22 hotfix)
    ├── date_rules.py                  # validate_entity_dates / validate_resource_dates
    ├── upsert_helpers.py
    ├── project_code.py                # Project-code generator
    └── utils.py
```

### Request Processing Pipeline

```
 1. HTTP Request → FastAPI
 2. CORS Middleware
 3. Logging Middleware  → assigns X-Request-ID, logs request
 4. Authentication Middleware (doc 21B)
       - decodes JWT (HS256)
       - checks revoked-token blacklist by jti
       - on success, sets request.state:
            user_id, user_login, token_jti, token_exp
            user_permissions: Set[str]   ← from RbacRepository (one DB query)
            is_admin: bool                ← from membership in seeded `admin` role
 5. Route → Permission check via require_permission("module:action")
       - reads request.state.user_permissions
       - 401 if user_id is None, 403 if code not in the set
 6. FastAPI dependency injection (get_db, schema validation)
 7. Controller → calls services, formats HAL+JSON response
 8. Service → business logic via repositories, returns ServiceResult
 9. Repository → SQLAlchemy ORM
10. Response Formatting → HAL+JSON via core/response.py
11. Logging Middleware (response) → status + duration + X-Request-ID
12. HTTP Response
```

### Key Design Patterns

- **ServiceResult** — `ServiceResult.ok(data)` / `ServiceResult.fail(error, error_type, details)`. Controllers map `error_type` to HTTP status.
- **Repository pattern** — all DB access through repos; repos own SQL and return domain entities.
- **HAL+JSON envelope** — every response is `{ "data": { _type, _links, _embedded?, … }, "status": <int> }` or `{ "error": { errorIdentifier, message, … }, "status": <int> }`.
- **String-coded RBAC** — routes call `require_permission("projects:create")`. The string is the canonical code (see [app/core/permissions.py](../app/core/permissions.py)). Codes are upserted into the DB at boot.
- **Soft-delete everywhere** — `deleted_at` + (where present) `deleted_by`. Reads filter by `deleted_at IS NULL` unless `include_deleted=True`. Restore endpoints (`POST /…/restore`) clear `deleted_at`.
- **Single-tier projects (post-doc-33)** — versioning was removed; M/A/T/S all live directly on whichever live project owns the activity. Permission gates remain (admin / member / vendor / viewer).

---

## 3. Database Schema

The full schema (every table, column, index, constraint, FK relationship) is documented in **[DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)**.

Auto-generated DDL for both dialects lives in [scripts/ddl/](../scripts/ddl/) — regenerate with `python scripts/generate_ddl.py` whenever a model changes.

Total tables on `Base.metadata`: **37** (doc 33 change 3 added `notification_log` / `otp_codes` / `password_reset_tokens`; doc 35 dropped `attachments`, folding it into `comments.attachments` JSON; doc 36 added `notification_templates`).

Schema highlights to be aware of:

- **`users.id` is `VARCHAR(36)` UUID** as of doc 26 (was `INTEGER` autoincrement). Every FK column referencing `users.id` (~30 across the schema) was retyped to `String(36)`. JWT `user_id` claim now carries a UUID string — pre-doc-26 tokens become invalid.
- **`users.two_factor_enabled`** (doc 33 change 3) — per-user 2FA opt-in, defaults `true`. Bootstrap admin is forced `false` on every boot.
- **Versioning is REMOVED** (doc 33 change 1). `projects.is_version` / `version_of` / `baseline_id` / `version_no`, `milestones.cloned_from_id`, `activities.cloned_from_id`, `project_status_transitions.version_only`, the `suspended` status, and the `ux_projects_active_version_per_baseline` partial unique index are all gone.
- **`project_audit_logs.actor_role`** (doc 33 change 1) — records the role bucket (admin / member / vendor / viewer) the actor occupied at write time. Audit coverage expanded to T/S create+delete and dep-edge changes.
- **`comments.attachments` JSON** (doc 35) — the standalone `attachments` table was dropped. A comment row now carries body, attachments JSON list, or both. `body` is nullable (attachment-only rows are valid). Service rule: at least one of body/attachments must be present.
- **`vendors.vendor_code` + `users.user_code`** (doc 25) — human-readable display IDs `VN-XXXX-YYMMDDHHMMSS` / `US-XXXX-YYMMDDHHMMSS`. Lookup endpoints accept either the canonical UUID OR the code.
- **`users`** has no `admin` boolean column — superuser status comes from membership in the seeded `admin` role (doc 21B).
- **`milestones.depends`** JSON column was dropped (doc 22). Milestone deps live in `milestone_dependencies` (doc 21A).
- **`subtasks.parent_subtask_id`** (nullable self-FK) supports nested subtasks (doc 24).
- **Position uniqueness** for live siblings is enforced by partial-unique indexes on every M/A/T/S level (doc 22 + doc 24's nested-subtask split).
- **DB-RBAC** (doc 21B): `permissions`, `role_permissions`, `user_roles`, `user_permissions`. The legacy `roles.permissions` JSON column was dropped.
- **Notification log + OTP / password-reset tables** (doc 33 change 3) — `notification_log` records every dispatch (mock or http backend); `otp_codes` and `password_reset_tokens` store hashed single-use tokens.
- **DB-backed notification templates** (doc 36) — `notification_templates` table holds the email subject/body and SMS body for each `(template_kind, channel)` pair, with `{placeholder}` substitution at render time. Replaces the hardcoded if/elif/else in `app/shared/notifications.py`. Ops can edit copy via `/api/v3/master/notification_templates/*` without a release.
- **Required division contact** (doc 36) — `divisions.email` + `phone_number` are NOT NULL. Seed rows backfilled from `DIVISION_DEFAULT_EMAIL` / `DIVISION_DEFAULT_PHONE` env vars.
- **`UtcDateTime` column type** (doc 27) — every datetime column uses the project-internal type so IST/UTC values compare correctly across submission formats.

---

## 4. API Endpoint Reference

### System

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | No | Root — API links |
| GET | `/health` | No | Health check |
| GET | `/docs` | No | Swagger UI |
| GET | `/redoc` | No | ReDoc |
| GET | `/openapi.json` | No | OpenAPI document |

### Authentication & users

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/api/v3/users/login` | Public | Stage 1. Returns access + refresh JWT for users with `two_factor_enabled=False`; returns `{requires_otp: true, ephemeral_token, channels_available}` for 2FA-enabled users (doc 33 change 3) |
| POST | `/api/v3/users/login/send-otp` | Public (ephemeral token) | **Doc 33 change 3** — generate + dispatch OTP for an in-progress 2FA session. Body: `{ephemeral_token, channel}`. Cooldown enforced via `OTP_RESEND_COOLDOWN_SECONDS` |
| POST | `/api/v3/users/login/verify-otp` | Public (ephemeral token + OTP) | **Doc 33 change 3** — verify OTP and mint real JWT. Wrong codes consume attempts up to `OTP_MAX_ATTEMPTS`; correct code consumes the row (single-use) |
| POST | `/api/v3/users/forgot-password` | Public | **Doc 33 change 3** — request password reset. Body: `{login_or_email, channel}`. Always 200 (anti-enumeration). Email sends URL token; SMS sends 6-digit OTP |
| POST | `/api/v3/users/reset-password` | Public (reset token) | **Doc 33 change 3** — complete password reset. Body: `{token_or_code, new_password}`. Single-use token, expires after `PASSWORD_RESET_TTL_SECONDS` |
| POST | `/api/v3/users/refresh` | Public (refresh-token) | Rotate access token (grace window — doc 19) |
| POST | `/api/v3/users/introspect` | Public | RFC 7662 introspect; resolves `isAdmin` from DB at call time |
| POST | `/api/v3/users/logout` | Authenticated | Revoke current access JTI + clear all refresh slots |
| GET | `/api/v3/users/me` | Authenticated | Current user record |
| GET | `/api/v3/users/me/permissions` | Authenticated | Effective permission set (FE uses to draw UI) |
| POST | `/api/v3/users/create` | `users:create` | Create user (vendor + project mapping required) |
| GET | `/api/v3/users` | `users:read_all` | List users |
| GET | `/api/v3/users/{id}` | `users:read` | Get user |
| PATCH | `/api/v3/users/{id}` | `users:update` (self) / `users:update_all` | Update user |
| PATCH | `/api/v3/users/{id}/password` | `users:update` | Update password |
| DELETE | `/api/v3/users/{id}` | `users:delete_all` | Soft-delete (last-admin protected) |
| POST | `/api/v3/users/{id}/restore` | `users:delete_all` | Restore soft-deleted user |

### RBAC user-side (doc 21B)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/api/v3/users/{id}/permissions` | `permissions:read` | Effective permissions for a user |
| POST | `/api/v3/users/{id}/permissions/{code}` | `rbac:assign` | Direct grant (additive) |
| DELETE | `/api/v3/users/{id}/permissions/{code}` | `rbac:assign` | Revoke direct grant |
| GET | `/api/v3/users/{id}/roles` | `permissions:read` | List user's roles |
| POST | `/api/v3/users/{id}/roles/{role_id}` | `rbac:assign` | Assign role |
| DELETE | `/api/v3/users/{id}/roles/{role_id}` | `rbac:assign` | Unassign role (last-admin lockout protected) |

### Projects (single-tier post-doc-33)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/api/v3/projects/create` | `projects:create` | Create project (`startDate` may be in past — doc 24) |
| PUT | `/api/v3/projects/{uuid}` | `projects:create`/`projects:update_all` | Idempotent upsert |
| GET | `/api/v3/projects` | `projects:read` | List live projects (paged) |
| GET | `/api/v3/projects/all` | `projects:read_all` | Admin view incl. soft-deleted |
| GET | `/api/v3/projects/{id}` | `projects:read` | Get project |
| PATCH | `/api/v3/projects/{id}` | `projects:update_all` | Update project |
| DELETE | `/api/v3/projects/{id}` | `projects:delete_all` | Soft-delete (cascades M/A/T/S + comments) |
| POST | `/api/v3/projects/{id}/save` | `projects:update_all` | Move `new` → `draft` |
| POST | `/api/v3/projects/{id}/publish` | `projects:publish` | Move `{new,draft} → published`. **Doc 30**: rejects (422 `invalid_publish`) projects with zero milestones (`no_milestones`) or any milestone with zero live activities (`milestone_without_activity`). **Doc 33**: `published → draft` revert is a legal transition. |
| POST | `/api/v3/projects/{id}/close` | `projects:close` | Move to `closed` |
| GET | `/api/v3/projects/{id}/tree` | `projects:read` | Full nested tree (M/A/T/S, recursive subtask nesting) |
| GET / POST | `/api/v3/projects/{id}/memberships[/create]` | `projects:read` / `projects:update_all` | List + add project members |
| PATCH / DELETE | `/api/v3/memberships/{id}` | `projects:update_all` | Edit / remove a membership |
| GET / POST | `/api/v3/projects/{id}/work_packages[/create]` | `projects:read` / `projects:update_all` | List + create OpenProject-style WPs (separate from M/A/T/S graph) |
| GET / PATCH / DELETE | `/api/v3/work_packages/{id}` | `projects:read` / `projects:update_all` | WP CRUD |
| GET | `/api/v3/work_packages/{id}/children` | `projects:read` | Child WPs |
| GET / POST / PATCH / DELETE | `/api/v3/work_package_types[/{id}]` | `master_data:view` / `master_data:manage` | WP-type catalog |

> **Doc 33 change 1**: `POST /api/v3/projects/{id}/suspend` and `POST /api/v3/projects/{id}/versions/create` were REMOVED. The `suspended` status is gone. Project response shape no longer includes `isVersion` / `versionOf` / `baselineId` / `versionNo`.

### Master data (`/api/v3/master/*` — doc 20 + 21B follow-up)

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| GET | `/api/v3/master/divisions` | `master_data:view` | List divisions |
| POST | `/api/v3/master/divisions/create` | `master_data:manage` | Add division |
| PATCH | `/api/v3/master/divisions/{code}` | `master_data:manage` | Edit division |
| DELETE | `/api/v3/master/divisions/{code}` | `master_data:manage` | Soft-delete (built-ins protected) |
| POST | `/api/v3/master/divisions/{code}/restore` | `master_data:manage` | Restore |
| GET | `/api/v3/master/project_status_transitions` | `master_data:view` | List transitions |
| POST/PATCH/DELETE | `/api/v3/master/project_status_transitions[/…]` | `master_data:manage` | Transition CRUD |
| GET | `/api/v3/master/resource_types` | `master_data:view` | List resource types |
| POST/PATCH/DELETE | `/api/v3/master/resource_types[/…]` | `master_data:manage` | Resource-type CRUD |
| GET | `/api/v3/master/vendors` | `master_data:view` | List vendors |
| POST/PATCH/DELETE | `/api/v3/master/vendors[/…]` | `master_data:manage` | Vendor CRUD (delegates to legacy handlers) |
| GET | `/api/v3/master/roles` | `master_data:view` | List roles (doc 21B follow-up) |
| POST | `/api/v3/master/roles/create` | `master_data:manage` | Create role |
| PATCH/DELETE | `/api/v3/master/roles/{id}` | `master_data:manage` | Edit / delete role (admin role protected) |
| GET | `/api/v3/master/roles/{id}/permissions` | `master_data:view` | List role's permission set |
| PUT | `/api/v3/master/roles/{id}/permissions` | `master_data:manage` | Replace permission set |
| POST/DELETE | `/api/v3/master/roles/{id}/permissions/{code}` | `master_data:manage` | Grant / revoke single |
| GET | `/api/v3/master/permissions` | `master_data:view` | List permission catalog (flat) |
| GET | `/api/v3/master/permissions/by-module` | `master_data:view` | **Doc 33 change 2** — same catalog grouped by module prefix; modules sorted alphabetically; permissions per module sorted by code |
| POST | `/api/v3/master/permissions/create` | `master_data:manage` | Create custom permission |
| PATCH/DELETE | `/api/v3/master/permissions/{code}` | `master_data:manage` | Edit / delete (built-ins protected) |
| GET | `/api/v3/master/notification_templates` | `master_data:view` | **Doc 36** — list email + SMS templates. `?include_inactive=true` for admin view |
| GET | `/api/v3/master/notification_templates/{id}` | `master_data:view` | Single read |
| POST | `/api/v3/master/notification_templates/create` | `master_data:manage` | Create template (409 when an active row already covers the `(templateKind, channel)` pair) |
| PATCH | `/api/v3/master/notification_templates/{id}` | `master_data:manage` | Edit subject/body/active/description (built-ins editable on copy; templateKind + channel immutable). Placeholder validation runs against the row's pinned kind+channel. |
| DELETE | `/api/v3/master/notification_templates/{id}` | `master_data:manage` | Soft-deactivate (`active=false`); built-ins protected from hard delete |
| POST | `/api/v3/master/notification_templates/{id}/restore` | `master_data:manage` | Re-activate (409 if another active row already covers the pair) |

The legacy paths (`/api/v3/divisions`, `/api/v3/resource_types`, `/api/v3/vendors/*`, `/api/v3/roles/*`, `/api/v3/permissions/*`) keep responding but stamp `Deprecation: true` + `Link: <successor>; rel="successor-version"`.

### Milestones / Activities / Tasks / Subtasks

`dependsOn` arrays accept either UUIDs or **display labels** (`M1`, `A1.2`, `T1.2.3`, `S1.2.3.4`, and now `S1.2.3.4.5…` for nested subtasks per doc 24). Every response includes `displayCode` + `dependsOnDisplay`.

**Milestones**
| Method | Path | Permission | Description |
|---|---|---|---|
| POST | `/api/v3/projects/{id}/milestones/create` | `milestones:create` | Create on the project. `dependsOn` accepted (doc 21A). **Doc 32**: accepts JSON or multipart; multipart adds optional `body` (comment) + `files` (uploads) inline. **Doc 33**: versioning was removed — milestones live directly on the project; the "baseline only" rule is gone. |
| GET | `/api/v3/projects/{id}/milestones` | `milestones:read` | List |
| GET | `/api/v3/milestones/{id}` | `milestones:read` | Get |
| PATCH | `/api/v3/milestones/{id}` | `milestones:update` | Update (baseline only) |
| DELETE | `/api/v3/milestones/{id}` | `milestones:delete` | Soft-delete + cascade |
| POST | `/api/v3/milestones/{id}/restore` | `milestones:restore` | Restore |

**Activities** — `POST /milestones/{id}/activities/standard/create` (or `…/resource/count/create`, `…/resource/details/create`, `…/transactional/create`), `GET/PATCH/DELETE/restore` on `/activities/{id}`. Same dependency rules as milestones. **Doc 32**: every variant of the create endpoint accepts JSON or multipart on the same URL; multipart adds inline `body` + `files`. **Doc 33**: writable on the project (the "baseline only" rule was dropped with the versioning feature).

**Tasks** — `POST /activities/{id}/tasks/create` (type derived from parent activity); `GET/PATCH/DELETE/restore` on `/tasks/{id}`. **Doc 24 part 3: no parent-activity hierarchy rule on dependencies.** **Doc 32**: create accepts JSON or multipart. **Doc 33**: tasks now live directly under the project's M/A subtree (the version-only rule was dropped along with the versioning feature).

**Subtasks** — writable directly under the project (per doc 33; the version-only rule was dropped).
| Method | Path | Permission | Description |
|---|---|---|---|
| POST | `/api/v3/tasks/{task_id}/subtasks/create` | `subtasks:create` | Top-level subtask under task. **Doc 32**: accepts JSON or multipart |
| POST | `/api/v3/subtasks/{parent_subtask_id}/subtasks/create` | `subtasks:create` | **Nested subtask (doc 24).** **Doc 32**: accepts JSON or multipart |
| GET | `/api/v3/tasks/{task_id}/subtasks` | `subtasks:read` | List with descendants embedded recursively under each top-level row (doc 28) |
| GET | `/api/v3/subtasks/{id}` | `subtasks:read` | Get (response includes `parentSubtaskId`) |
| PATCH/DELETE/restore | `/api/v3/subtasks/{id}` | `subtasks:update`/`delete`/`restore` | Mutate / cascade-soft-delete entire subtree |

**Doc 24 part 3: no parent-task hierarchy rule on dependencies.** Subtask deps follow the same rule as activity deps: same project, no self, no cycle. Cap nesting depth via env var `SUBTASK_MAX_NESTING_DEPTH` (default `None` = unlimited).

**Doc 30 dep-date enforcement.** For activity/task/subtask dep edges, `source.start_date >= target.end_date` must hold (equality allowed — same-day handoff). Validated on create + update in two directions: forward (when `dependsOn` is assigned/replaced or `start_date` moves) and reverse (when a target's `end_date` is pushed past an existing successor's `start_date`). Error messages list every offender with its label. Helper: [`app/shared/dep_date_rules.py`](../app/shared/dep_date_rules.py).

**Doc 31 milestone-specific rules.** Milestones use a different dep-date rule than the other three kinds: `source.start_date >= target.start_date` (equality allowed — phases may run in parallel) AND `source.end_date > target.end_date` (strict — equality REJECTED, the dependent must outlast its predecessor). Both directions guarded. Plus a status-completion gate: a milestone cannot be marked `completed` while any dep target is `not_completed` (mirrors the activity-side gate). Side-effect of the strict-end rule: a date-valid milestone cycle is structurally impossible, so the cycle-detection check is unreachable for milestones (the date rule fires first).

### Comments + attachments

Polymorphic on M/A/T/S target — see the route files for the full surface.

---

## 5. Response Format (HAL+JSON)

### Single resource

```json
{
  "data": {
    "_type": "User",
    "_links": { "self": { "href": "/api/v3/users/8bd99f06-5f2a-424c-aaff-10ab163c3e42", "title": "admin" } },
    "id": "8bd99f06-5f2a-424c-aaff-10ab163c3e42",
    "userCode": "US-ADMI-260502143015",
    "login": "admin",
    "firstName": "Admin",
    "lastName": "User",
    "email": "admin@example.com",
    "phoneNumber": "9876543210",
    "admin": true,
    "status": "active",
    "vendor": { "id": "…", "vendorCode": "VN-ACME-260502143015", "name": "Vendor A" },
    "division": "tmd1",
    "divisionOther": null,
    "projects": [ { "id": "…", "projectCode": "UIDAI-PR…", "name": "…", "status": "draft" } ],
    "createdAt": "2026-05-01T10:00:00",
    "updatedAt": "2026-05-04T08:30:00"
  },
  "status": 200
}
```

> **Doc 33 change 3** (notifications + 2FA + forgot-password): two-stage 2FA login — `POST /users/login` returns ephemeral token when `users.two_factor_enabled=True` (default mandatory, env-overridable); `POST /users/login/send-otp` + `POST /users/login/verify-otp` complete the flow. Self-service password reset via `POST /users/forgot-password` (anti-enumeration: always 200) + `POST /users/reset-password`. New `notification_log` / `otp_codes` / `password_reset_tokens` tables. `NotificationClient` interface with `MockNotificationClient` (DB sink) + `HttpNotificationClient` (stub). Env vars `OTP_TTL_SECONDS` / `OTP_RESEND_COOLDOWN_SECONDS` / `OTP_MAX_ATTEMPTS` / `OTP_CODE_LENGTH` / `REQUIRE_2FA` / `PASSWORD_RESET_TTL_SECONDS` / `NOTIFICATION_CLIENT` / `NOTIFICATION_SERVICE_URL`.
> **Doc 33 change 2** (RBAC extension): added `GET /api/v3/master/permissions/by-module` returning the catalog grouped by module prefix so the FE can render a permission picker tree without parsing codes. Deleted dead RBAC code from `app/core/rbac.py` (`Role` enum, `ROLE_PERMISSIONS` dict, `has_permission`, `get_role_permissions`). Runtime permission registration via `POST /api/v3/master/permissions/create` was already shipped in doc 21B.
> **Doc 33 change 1**: versioning removed. The baseline/version split is gone — projects own their M/A/T/S directly. `/versions/create`, `/suspend`, the `suspended` status, and the entire `baseline_version_sync` propagation module were dropped. Tasks/subtasks writable on the project (no version-only rule). Published is a sign-off checkpoint, revertible to draft. New built-in `vendor` role with curated M/A/T/S CRUD permission set. Audit expanded: T/S create + delete + dep-edge changes recorded on `project_audit_logs`; new `actor_role` column. Project response shape no longer includes `isVersion` / `versionOf` / `baselineId` / `versionNo`.
> **Doc 32** (kamal21, tagged "Doc 30" in commit): every M/A/T/S create endpoint now accepts JSON or multipart on the same URL. Multipart adds optional `body` (comment) and `files` (file uploads) so the create + comment + attachments flow can be one round-trip. Two followups bundled: `_normalize` collapses to IST calendar midnight (legacy-row tolerance), and caller-supplied `position` collisions auto-bump instead of 500.
> **Doc 31**: milestone-specific dep-date rules — `source.start >= target.start` (equality OK) AND `source.end > target.end` (strict). Status-completion gate added to milestones: cannot mark `completed` while a dep target is incomplete.
> **Doc 30**: dep-date enforcement for activity/task/subtask deps (`source.start >= target.end`, equality allowed) on create + update, forward and reverse. Publish rejects projects with zero milestones or any milestone holding zero live activities — both gates apply to baselines and versions; specific identifier in `_embedded.details.errorIdentifier` (`no_milestones` / `milestone_without_activity`).
> **Doc 27** (kamal21): IST/UTC date-equality fixes via `UtcDateTime` column type so cross-format milestone/project date comparisons land on the same calendar day. Stale pre-doc-26 JWTs return 401 not 500.
> **Doc 28/29** (kamal21): nested subtask listing fix + IST calendar-date input normalization across submission formats.
> **Doc 26**: `users.id` is now a UUID string (was an integer). The legacy `GET /api/v3/users/1` no longer resolves — call by UUID or by the doc-25 `userCode`.
> **Doc 25**: every user / vendor response carries the human-readable `userCode` / `vendorCode` alongside the UUID. Lookup paths and cross-entity vendor inputs accept either form.

### Collection

```json
{
  "data": {
    "_type": "Collection",
    "_links": { "self": { "href": "/api/v3/users?offset=1&pageSize=20" } },
    "total": 137,
    "count": 20,
    "pageSize": 20,
    "offset": 1,
    "_embedded": { "elements": [ /* … */ ] }
  },
  "status": 200
}
```

### Error

```json
{
  "error": {
    "_type": "Error",
    "errorIdentifier": "not_found",
    "message": "User with ID 99 not found"
  },
  "status": 404
}
```

### Status code taxonomy

| Status | Usage |
|---|---|
| 200 | Successful GET / PATCH / soft-delete on master rows |
| 201 | Successful POST (create) |
| 204 | Successful DELETE returning no body |
| 400 | Bad request |
| 401 | Unauthorized (no token / revoked / decode failure) |
| 403 | Forbidden (lacks permission, last-admin lockout, admin-role lock) |
| 404 | Not found |
| 409 | Conflict (duplicate, active-version exists, etc.) |
| 422 | Validation error |
| 500 | Server error |

---

## 6. RBAC (DB-driven, doc 21B)

### Model

- **Permissions** are string codes (`projects:create`, `master_data:manage`, `rbac:assign`, …). The full registry lives in [app/core/permissions.py](../app/core/permissions.py).
- **Roles** are arbitrary named bundles of permission codes. Three are seeded on startup:
  - **`admin`** — holds every registered permission. Cannot be deleted, renamed, or have its permission set modified. Auto-syncs to include any new permission codes added in code.
  - **`member`** — default contributor set (read/write on M/A/T/S, read on master, etc.).
  - **`viewer`** — read-only.
- **Users** are assigned roles via the `user_roles` table. Effective permissions = union of role-derived ∪ direct grants from `user_permissions`. Direct grants are additive; there is no deny semantics.

### Enforcement

```python
from app.core.middleware.rbac import require_permission
from app.core.permissions import PROJECTS_CREATE

@router.post(
    "/create",
    dependencies=[require_permission(PROJECTS_CREATE)],
    status_code=201,
)
def create_project(...):
    ...
```

Per-request flow: auth middleware loads the user's effective permission set into `request.state.user_permissions` once. The decorator does a `O(1)` set membership check.

### Lockout protections

- Removing the last user holding the `admin` role → 403.
- Deleting / renaming / mutating the `admin` role → 403.
- Self-delete / self-demote on a sole admin → 422.

### JWT contents (doc 21B + doc 26)

```json
{ "sub": "admin", "user_id": "8bd99f06-5f2a-424c-aaff-10ab163c3e42", "email": "admin@…", "jti": "…", "iat": …, "exp": … }
```

> **Doc 26**: `user_id` is a UUID string, not an integer. Tokens minted before the migration carry an integer that no longer matches any `users.id` row — those users have to log in once to mint a fresh UUID-bearing token. The auth middleware returns 401 (not 500) on stale integer-id tokens (doc 27 hotfix).

No `role` / `is_admin` claims — they're resolved from the DB on every request. Tokens issued before doc 21B that still carry those claims keep working; the middleware ignores them.

---

## 7. Configuration

### Settings source

All env-var bindings live in **[`app/core/config.py`](../app/core/config.py)** — a Pydantic `BaseSettings` class (`Settings`) with `model_config = ConfigDict(env_file=".env", case_sensitive=True, extra="ignore")`. The deployment loads values from process env first, then falls back to a `.env` file colocated with the entry point. The single global `settings = Settings()` instance is what every module imports — no other reader of OS env exists. To add a new env var, declare a typed field on `Settings` (with `Field(default=…, description="…")`) and reference `settings.YOUR_VAR` from the call site; do not call `os.environ.get` in feature code.

### Environment variables

```bash
SECRET_KEY=<32+ char secure key>
DATABASE_URL=sqlite:///./pmis.db                    # or postgresql://user:pw@host/db
DEBUG=False
CORS_ORIGINS=["http://localhost:3000"]
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
REFRESH_TOKEN_GRACE_SECONDS=120                     # doc 19
DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=100
BOOTSTRAP_ADMIN_LOGIN=admin
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=admin123
SUBTASK_MAX_NESTING_DEPTH=                          # doc 24 — None = unlimited

# ---- Doc 33 change 3: 2FA + forgot-password + notifications ----
REQUIRE_2FA=true                                    # global toggle; per-user via twoFactorEnabled
OTP_TTL_SECONDS=300                                 # OTP validity
OTP_RESEND_COOLDOWN_SECONDS=60                      # min seconds between resends
OTP_MAX_ATTEMPTS=5                                  # wrong codes before invalidation
OTP_CODE_LENGTH=6
OTP_HASH_PEPPER=                                    # falls back to SECRET_KEY when blank
PASSWORD_RESET_TTL_SECONDS=3600                     # forgot-password token TTL
NOTIFICATION_CLIENT=mock                            # mock | http
NOTIFICATION_SERVICE_URL=                           # required when NOTIFICATION_CLIENT=http

# ---- Doc 33 hotfix: deploy-time migration controls ----
DATABASE_URL_MIGRATIONS=                            # optional elevated URL ONLY for `alembic upgrade head` at startup; falls back to DATABASE_URL
MIGRATIONS_AUTORUN=true                             # set false to skip alembic at boot (DBA runs it out-of-band)
MIGRATIONS_REQUIRED=true                            # set false to log alembic failures and continue boot anyway

# ---- Doc 36: division contact backfill defaults ----
DIVISION_DEFAULT_EMAIL=ops@pmis.example             # backfilled into divisions.email NULLs during migration + new seed rows
DIVISION_DEFAULT_PHONE=+910000000000                # backfilled into divisions.phone_number NULLs (production deploys override both)
```

### Bootstrap admin

On first boot the RBAC seed creates the `admin` role (and its permissions) and assigns it to the bootstrap user. The bootstrap user can be deleted later as long as another user holds the `admin` role (lockout guard). Defaults: `admin` / `admin123`.

### Running

```bash
# Dev
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Prod
gunicorn -w 4 -b 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker app.main:app
```

### API documentation

- Swagger UI: `http://<host>:8000/docs`
- ReDoc: `http://<host>:8000/redoc`
- OpenAPI JSON: `http://<host>:8000/openapi.json`

---

## 8. Migration history (planned_changes/)

Numbered docs in [planned_changes/](../planned_changes/) describe every BE shape change with reasoning. Most relevant since 19:

| Doc | Topic |
|---|---|
| 19 | Refresh-token grace window |
| 20 | `/api/v3/master/*` consolidation; project_owners removed |
| 21A | Milestone-to-milestone dependencies |
| 21B | DB-driven RBAC overhaul |
| 21B follow-up | Roles + permissions CRUD relocated under `/master/*` |
| 22 | Display labels (M/A/T/S) + drop `milestones.depends` JSON + per-parent position uniqueness |
| 23 | Users `phone_number` + vendor `phoneNumber` required |
| 24 | Past `start_date`, nested subtasks, drop dependency hierarchy rules |
| 25 | Human-readable `vendorCode` / `userCode` (`VN-…` / `US-…`); polymorphic lookup; cross-entity vendor inputs accept UUID or code |
| 26 | `users.id` flipped from `INTEGER` to `VARCHAR(36)` UUID; ~30 FK columns retyped in the same migration; pre-doc-26 JWTs invalidated |
| 27 | IST/UTC date-equality fixes via `UtcDateTime` column type; pre-doc-26 JWT 401-not-500 |
| 28/29 | Nested subtask listing fix; calendar-date input normalization across IST/UTC formats |
| 30 | Dep-date enforcement for activities/tasks/subtasks; publish structural-completeness gate (`no_milestones` / `milestone_without_activity`) |
| 31 | Milestone-specific dep-date rules (`source.start >= target.start`, `source.end > target.end`); milestone status-completion gate |
| 32 | M/A/T/S create endpoints accept JSON or multipart on the same URL (inline `body` + `files`) |
| 33 change 1 | Versioning removed (`/versions/create`, `/suspend`, `suspended` status, `isVersion`/`versionOf`/`baselineId`/`versionNo` fields all gone); tasks/subtasks writable directly on the project; new built-in `vendor` role; audit expanded with `actor_role` |
| 33 change 2 | RBAC extension: `GET /api/v3/master/permissions/by-module` (catalog grouped by module); dead-code cleanup in `app/core/rbac.py` |
| 33 change 3 | 2FA OTP login (`/login/send-otp`, `/login/verify-otp`); forgot-password (`/forgot-password`, `/reset-password`); per-user `twoFactorEnabled` toggle; `notification_log` / `otp_codes` / `password_reset_tokens` tables; `MockNotificationClient` (DB sink) + `HttpNotificationClient` (stub) |
| 33 hotfix | `MIGRATIONS_AUTORUN` / `MIGRATIONS_REQUIRED` env vars + `DATABASE_URL_MIGRATIONS` for deploys where the runtime DB role lacks DDL ownership; PG boolean literal fix in `two_factor_enabled` backfill |
| 33 follow-up | Live `HttpNotificationClient` integrated against PMIS-notification-service (`POST /api/v1/notifications/email/send` + `/sms/send`); audit-row lifecycle (queued → sent / failed) with provider + message_id stashed under `payload._dispatch` |
| 34 (1/3) | Cascade soft-delete of comments + attachments under M/A/T/S delete (was previously orphaning polymorphic rows); shared helper at `app/shared/comments_attachments_cascade.py`; uniform cascade timestamp lets the restore-cascade identify exactly which rows belong to a delete event |
| 34 (2/3) | External-dependency block on M/A/T/S delete: refuse with 422 + `errorIdentifier="dependency_block"` when anything in the subtree is the target of a live dep edge whose source lives outside the subtree. Self-contained edges don't block. Helper at `app/shared/dep_block.py`. Project delete is unchanged (deps are project-scoped). |
| 34 (3/3) | Cascade-restore: when an M/A/T/S is restored, every row whose `deleted_at` exactly matches the cascade timestamp is revived (M/A/T/S subtree + resources + comments + attachments). Rows soft-deleted independently before the parent cascade stay dead. Dep edges are NOT auto-restored — re-establish via PATCH `dependsOn`. |
| 35 | **Comments + attachments unified.** The standalone `attachments` table was DROPPED. `comments.attachments` (JSON) carries a list of `{url, filename, mimeType, sizeBytes, uploadedAt}` directly on the comment row. `comments.body` relaxed to nullable so attachment-only rows are legal. URL points at external file server (`FILE_SERVER_PUBLIC_BASE_URL`); local fallback `GET /files/{storage_key}` route serves bytes for legacy keys. Live attachment rows were folded onto parent comments during migration; standalone attachments became attachment-only comments. Soft-deleted attachments were not migrated. |
| 36 | **DB-backed notification templates** — new `notification_templates` master table seeded with 6 built-in rows (3 kinds × 2 channels); `/api/v3/master/notification_templates/*` CRUD with placeholder validation; renderers `_render_email` / `_render_sms` in `app/shared/notifications.py` now look up by `(template_kind, channel)` and `str.format(**placeholders)` over stored copy. Active-uniqueness enforced (Postgres partial unique index + service-layer guard). **Division contact required** — `divisions.email` + `phone_number` flipped NOT NULL with env-driven seed backfill (`DIVISION_DEFAULT_EMAIL` / `DIVISION_DEFAULT_PHONE`). Alembic head `c2d4e7f9a1b3`. |
