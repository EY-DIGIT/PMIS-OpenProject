# PMIS Database Schema

**Last refresh**: 2026-05-06 (post-doc 37 part 1)
**Source of truth**: SQLAlchemy models under [app/infrastructure/db/models/](../app/infrastructure/db/models/) → regenerated DDL at [scripts/ddl/](../scripts/ddl/) (`schema_postgres.sql`, `schema_sqlite.sql`).
**Tables on `Base.metadata`**: 41 (was 34 pre-doc-33; doc 33 change 3 added 3 — `notification_log`, `otp_codes`, `password_reset_tokens`; doc 35 dropped 1 — `attachments` merged into `comments.attachments` JSON; doc 36 added 1 — `notification_templates`; doc 37 part 1 added 4 — `project_categories`, `activity_types`, `milestone_statuses`, `activity_statuses`).

This doc inventories every table, its columns, indexes, FKs, and relationships. The DDL files are the authoritative type / index detail; this doc explains *intent* — what each table holds, how it links to its neighbours, and which docs introduced or reshaped it.

> **Migration management.** PostgreSQL runs `alembic upgrade head` on every boot (gated by the doc-33-hotfix `MIGRATIONS_AUTORUN` / `MIGRATIONS_REQUIRED` flags so a DBA can run alembic out-of-band when the runtime DB role lacks DDL ownership). SQLite uses `Base.metadata.create_all` plus a column-drift healer. The most recent revision is `b8c9d0e1f2a3` (doc 35 — comments + attachments unified). Multiple alembic heads currently exist; merge revisions are added when chains diverge.

---

## Table of contents

| # | Table | Purpose |
|---|-------|---------|
| 1 | [`users`](#1-users) | User accounts (refresh-token rotation slots, vendor + division mapping, doc 33 `two_factor_enabled`) |
| 2 | [`roles`](#2-roles) | Named permission bundles |
| 3 | [`permissions`](#3-permissions) | Permission catalog (string codes) |
| 4 | [`role_permissions`](#4-role_permissions) | Many-to-many: role ↔ permission |
| 5 | [`user_roles`](#5-user_roles) | Many-to-many: user ↔ role (legacy global; doc 41 introduces scoped variant in `user_role_assignments`) |
| 6a | [`user_role_assignments`](#6a-user_role_assignments-doc-41) | Doc 41 scoped grants (global / org / project) |
| 6 | [`user_permissions`](#6-user_permissions) | Direct user-level permission grants (additive) |
| 7 | [`revoked_tokens`](#7-revoked_tokens) | JWT JTI blacklist |
| 8 | [`vendors`](#8-vendors) | Vendor catalog |
| 9 | [`divisions`](#9-divisions) | Division catalog (`tmd1` / `tmd2` / `others` + custom) |
| 10 | [`resource_types`](#10-resource_types) | Resource-type catalog (RFP / ASG / CCN + custom) |
| 11 | [`project_status_transitions`](#11-project_status_transitions) | Allowed `(from_status, to_status)` edges |
| 12 | [`projects`](#12-projects) | Projects (versioning REMOVED in doc 33) |
| 13 | [`project_members`](#13-project_members) | Per-project member assignments |
| 14 | [`project_vendors`](#14-project_vendors) | Project ↔ vendor mapping |
| 15 | [`project_audit_logs`](#15-project_audit_logs) | Audit trail for project / M / A / T / S writes (doc 33 `actor_role`) |
| 16 | [`milestones`](#16-milestones) | Milestones under a project |
| 17 | [`milestone_dependencies`](#17-milestone_dependencies) | Milestone → milestone edges (doc 21A) |
| 18 | [`milestone_vendors`](#18-milestone_vendors) | Milestone ↔ vendor mapping |
| 19 | [`activities`](#19-activities) | Activities under a milestone |
| 20 | [`activity_dependencies`](#20-activity_dependencies) | Activity → activity edges |
| 21 | [`activity_resources`](#21-activity_resources) | Resource rows for resource-type activities |
| 22 | [`tasks`](#22-tasks) | Tasks under an activity |
| 23 | [`task_dependencies`](#23-task_dependencies) | Task → task edges |
| 24 | [`task_resources`](#24-task_resources) | Resource rows for tasks |
| 25 | [`subtasks`](#25-subtasks) | Subtasks under a task or another subtask (nested per doc 24) |
| 26 | [`subtask_dependencies`](#26-subtask_dependencies) | Subtask → subtask edges |
| 27 | [`subtask_resources`](#27-subtask_resources) | Resource rows for subtasks |
| 28 | [`comments`](#28-comments) | Polymorphic comments on M/A/T/S; doc 35 — carries `attachments` JSON list |
| 29 | [`notification_log`](#29-notification_log) | **Doc 33 change 3** — every email/SMS/OTP dispatch recorded here |
| 30 | [`otp_codes`](#30-otp_codes) | **Doc 33 change 3** — 2FA OTP rows (hashed) |
| 31 | [`password_reset_tokens`](#31-password_reset_tokens) | **Doc 33 change 3** — forgot-password tokens (hashed) |
| 32 | [`notification_templates`](#32-notification_templates) | **Doc 36** — email + SMS template content (subject/body with `{placeholder}` substitution) |
| 33 | [`meetings`](#33-meetings) | Project meetings |
| 34 | [`meeting_participants`](#34-meeting_participants) | Meeting ↔ user |
| 35 | [`meeting_agenda_items`](#35-meeting_agenda_items) | Agenda lines per meeting |
| 36 | [`work_package_types`](#36-work_package_types) | Built-in WP types catalog |
| 37 | [`work_packages`](#37-work_packages) | Generic OpenProject-style work packages |

> **The `attachments` table was DROPPED in doc 35** — its rows were folded into `comments.attachments` JSON. The local fallback `GET /files/{storage_key}` route still serves bytes for legacy keys.

---

## Universal conventions

- **Primary keys**: `INTEGER` autoincrement on catalog/admin tables (`roles`, `divisions`, `meetings`, `meeting_participants`, `meeting_agenda_items`, `project_status_transitions`, `project_audit_logs`, `project_members`, `notification_log`, `otp_codes`, `password_reset_tokens`, `work_packages`, `work_package_types`); **`VARCHAR(36)` UUID** on every product-facing entity — projects, M/A/T/S, vendors, resource_types, dep edges, comments, **and `users` as of doc 26**.
- **Soft-delete**: `deleted_at TIMESTAMP NULL` on every entity that supports it; reads filter `deleted_at IS NULL` unless `include_deleted=True` is explicitly passed. Where applicable, `deleted_by VARCHAR(36) FK→users(id)` records the actor (post-doc-26).
- **Audit timestamps**: `created_at`, `updated_at` (auto-set on insert / update), `created_by`, `updated_by` where the column exists.
- **UTC-aware datetimes (doc 27)**: every timestamp column is the project-internal `UtcDateTime` type (TIMESTAMP WITH TIME ZONE on Postgres; ISO-string with normalization on SQLite). Ensures cross-format date comparisons (IST vs UTC) land on the same calendar instant.
- **Position uniqueness**: per-parent live-position partial-unique indexes on M/A/T/S guarantee labels (`M{m}`, `A{m}.{a}`, `T{m}.{a}.{t}`, `S{m}.{a}.{t}.{s1}[.{s2}…]`) are unambiguous (doc 22, doc 24).
- **Edge tables** (`*_dependencies`): surrogate UUID PK + partial unique on `(source, target) WHERE deleted_at IS NULL` so historical (soft-deleted) rows can coexist with a fresh live row for the same pair.
- **All FK columns referencing `users.id` are `VARCHAR(36)` post-doc-26.** This includes every `created_by` / `updated_by` / `deleted_by` / `actor_id` / `assignee_id` / `created_by_id` / `author_user_id` / `user_id` column across the schema (verified — every `ForeignKey("users.id")` declaration uses `String(36)`).

---

## 1. `users`

**Doc 26** flipped `users.id` from `INTEGER` autoincrement to `VARCHAR(36)` UUID. **Doc 25** added the human-readable `user_code` display identifier. **Doc 21B** dropped the `admin BOOLEAN` column — superuser status comes from membership in the seeded `admin` role via `user_roles`. **Doc 19** added the refresh-token grace slot. **Doc 23** added `phone_number`. **Doc 33 change 3** added `two_factor_enabled`.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | **Doc 26** — UUID (was `INTEGER` autoincrement) |
| `user_code` | `VARCHAR(50) UNIQUE NULL` | **Doc 25** — human-readable display ID `US-XXXX-YYMMDDHHMMSS` |
| `login` | `VARCHAR(255) UNIQUE NOT NULL` | 3-50 chars, alphanumeric/underscore/hyphen at the API boundary |
| `email` | `VARCHAR(255) UNIQUE NOT NULL` | |
| `hashed_password` | `VARCHAR(255) NOT NULL` | Argon2id |
| `first_name`, `last_name` | `VARCHAR(255) NULL` | |
| `status` | `VARCHAR(50) NOT NULL` | `active` / `inactive` |
| `refresh_token_jti` | `VARCHAR(64) NULL` | Currently-active refresh-token JTI |
| `refresh_token_expires_at` | `UtcDateTime NULL` | |
| `previous_refresh_token_jti` | `VARCHAR(64) NULL` | **Doc 19** — grace slot |
| `previous_refresh_token_jti_valid_until` | `UtcDateTime NULL` | **Doc 19** — grace expiry |
| `vendor_id` | `VARCHAR(36) FK → vendors(id) NULL` | Single vendor per user (`use_alter=True` to break the create-cycle with `vendors.deleted_by → users.id`) |
| `division` | `VARCHAR(32) NULL` | One of `tmd1` / `tmd2` / `others` (required at the wire) |
| `division_other` | `VARCHAR(255) NULL` | Required when `division='others'` |
| `phone_number` | `VARCHAR(50) NULL` | **Doc 23** — required at the wire on create |
| `two_factor_enabled` | `BOOLEAN NOT NULL DEFAULT TRUE` | **Doc 33 change 3** — per-user 2FA opt-in. Bootstrap admin is forced `false` on every boot to avoid lockout. Ignored when `REQUIRE_2FA=false` globally. |
| `created_at`, `updated_at` | `UtcDateTime NOT NULL` | |
| `deleted_at`, `deleted_by` | nullable; `deleted_by` is `VARCHAR(36) FK → users(id)` | Soft-delete (self-FK) |

**Indexes**: `(login)`, `(email)`, plus `vendor_id`, `status`, `created_at`, `deleted_at`.

**Relationships**: `vendor_id → vendors.id`; self-FK `deleted_by → users.id`. Owns: `user_roles`, `user_permissions`, `project_members`, `comments` (`author_user_id`), `meeting_participants`, `meetings.created_by_id`, `revoked_tokens.user_id`, `project_audit_logs.actor_id`, `notification_log.user_id`, `otp_codes.user_id`, `password_reset_tokens.user_id`.

---

## 2. `roles`

**Doc 21B** dropped the JSON `permissions` column — grants live in `role_permissions`. **Doc 33 change 1** added a fourth seeded role, `vendor`.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `name` | `VARCHAR(255) UNIQUE NOT NULL` | Seeded: `admin`, `member`, `viewer`, **`vendor`** (doc 33) |
| `description` | `VARCHAR(1024) NULL` | **Doc 21B** |
| `builtin` | `BOOLEAN NOT NULL` | True for the seeded roles |
| `created_at`, `updated_at` | nullable timestamps | |

**Protections** (service layer): the `admin` role cannot be deleted, renamed, or have its permission set modified through the API. The other built-ins (`member` / `viewer` / `vendor`) remain editable.

---

## 3. `permissions`

Permission catalog for DB-driven RBAC (doc 21B). Codes look like `projects:create`, `master_data:manage`, `rbac:assign`. Built-in codes are upserted from [app/core/permissions.py](../app/core/permissions.py) on every boot.

| Column | Type | Notes |
|---|---|---|
| `code` | `VARCHAR(128) PK` | `module:action` |
| `name` | `VARCHAR(255) NOT NULL` | Human-readable |
| `description` | `VARCHAR(1024) NULL` | |
| `is_builtin` | `BOOLEAN NOT NULL` | Built-ins protected from delete |
| `created_at`, `updated_at` | timestamps | |

**Doc 33 change 2**: catalog browsing surface gained `GET /api/v3/master/permissions/by-module` (alphabetical module groups, codes sorted within each).

---

## 4. `role_permissions`

Composite-PK junction.

| Column | Type | Notes |
|---|---|---|
| `role_id` | `INTEGER PK FK → roles(id)` | |
| `permission_code` | `VARCHAR(128) PK FK → permissions(code)` | |
| `created_at` | timestamp | |

---

## 5. `user_roles`

Composite-PK junction. Membership = "user holds this role's permission set".

| Column | Type | Notes |
|---|---|---|
| `user_id` | `VARCHAR(36) PK FK → users(id)` | Doc 26 |
| `role_id` | `INTEGER PK FK → roles(id)` | |
| `created_at` | timestamp | |
| `created_by` | `VARCHAR(36) FK → users(id) NULL` | Actor who assigned |

**Lockout protection**: removing the last live user holding the seeded `admin` role returns 403.

---

## 6. `user_permissions`

Direct grants — additive on top of role-derived permissions. There is no deny semantics; to revoke, delete the row.

| Column | Type | Notes |
|---|---|---|
| `user_id` | `VARCHAR(36) PK FK → users(id)` | Doc 26 |
| `permission_code` | `VARCHAR(128) PK FK → permissions(code)` | |
| `created_at` | timestamp | |
| `created_by` | `VARCHAR(36) FK → users(id) NULL` | |

---

## 6a. `user_role_assignments` (doc 41)

Scoped role assignments (org / project / global). Replaces what `user_roles` (global-only) and `project_members.roles[]` (project-only) carried separately.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK autoincrement` | Synthetic — lets a user hold the same role on multiple projects. |
| `user_id` | `VARCHAR(36) NOT NULL FK → users(id)` | Indexed. |
| `role_id` | `INTEGER NOT NULL FK → roles(id)` | Indexed. |
| `organization_id` | `VARCHAR(36) NULL FK → vendors(id)` | Set ⇒ org-scope. Mutually exclusive with `project_id`. |
| `project_id` | `VARCHAR(36) NULL FK → projects(id)` | Set ⇒ project-scope. Mutually exclusive with `organization_id`. |
| `created_at` | timestamp NOT NULL | |
| `created_by` | `VARCHAR(36) FK → users(id) NULL` | Actor who created the assignment. |

**Constraints**:
- `ck_ura_single_scope`: `(organization_id IS NULL OR project_id IS NULL)` — a row is global, org-scoped, or project-scoped, never two-scope.
- `uq_user_role_assignment_scope`: `UNIQUE(user_id, role_id, organization_id, project_id)` — the same `(user, role, scope)` cannot be granted twice.

**Scope semantics**:
- Both columns NULL ⇒ global (legacy `user_roles` migrated here as global rows).
- `organization_id` set ⇒ org scope; the user holds the role within that vendor (= organization).
- `project_id` set ⇒ project scope; the user holds the role within that project only.

**Caller-vs-target authority** for grants is enforced in the user-mgmt service layer, not at the table level. See [RBAC_GUIDE.md §2a](RBAC_GUIDE.md#2a-scoped-rbac-doc-41).

**Lockout protection**: revoking the last global `super_admin` row returns 403 — the canonical-bootstrap path requires at least one super_admin always exist.

**Backfill (alembic `d0c41a55145d`, deployed 2026-05-08)**:
- Every row in `user_roles` was copied here as `(user, role, NULL, NULL)`.
- Every `project_members.roles[]` JSON entry whose name matches an existing role was copied here as `(user, role, NULL, project_id)`.

---

## 7. `revoked_tokens`

JWT JTI blacklist. Logout adds the access-token JTI here; the auth middleware checks it on every request.

| Column | Type | Notes |
|---|---|---|
| `jti` | `VARCHAR(64) PK` | |
| `user_id` | `VARCHAR(36) FK → users(id) NULL` | Doc 26 |
| `revoked_at` | `UtcDateTime NOT NULL` | |
| `expires_at` | `UtcDateTime NOT NULL` | Used by housekeeping to prune expired rows |

---

## 8. `vendors`

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `vendor_code` | `VARCHAR(50) UNIQUE NULL` | **Doc 25** — `VN-XXXX-YYMMDDHHMMSS` |
| `name` | `VARCHAR(255) UNIQUE NOT NULL` | |
| `description` | `TEXT NULL` | |
| `active` | `BOOLEAN NOT NULL` | |
| `email` | `VARCHAR(255) NULL` | |
| `contact_person` | `VARCHAR(255) NULL` | |
| `phone_number` | `VARCHAR(50) NULL` | **Doc 23** — required at the wire on create |
| `created_at`, `updated_at` | timestamps | |
| `deleted_at`, `deleted_by` | nullable; `deleted_by` is `VARCHAR(36) FK → users(id)` | Soft-delete |

**Relationships**: `project_vendors` (M-N projects), `milestone_vendors` (M-N milestones), `users.vendor_id`.

---

## 9. `divisions`

**Doc 20** — catalog moved under `/api/v3/master/divisions`. Built-ins (`tmd1` / `tmd2` / `others`) seeded and protected from delete. **Doc 36** flipped `email` and `phone_number` to NOT NULL with seed-row backfill via `DIVISION_DEFAULT_EMAIL` / `DIVISION_DEFAULT_PHONE` env vars.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `code` | `VARCHAR(64) UNIQUE NOT NULL` | |
| `label` | `VARCHAR(255) NOT NULL` | |
| `is_builtin` | `BOOLEAN NOT NULL` | |
| `requires_other` | `BOOLEAN NOT NULL` | When true, callers must supply a `division_other` free-text |
| `active` | `BOOLEAN NOT NULL` | |
| `email` | `VARCHAR(255) NOT NULL` | **Doc 36** — required at the wire on create (was nullable pre-doc-36). Seeded rows backfilled from `DIVISION_DEFAULT_EMAIL`. |
| `phone_number` | `VARCHAR(50) NOT NULL` | **Doc 36** — required at the wire on create. Seeded rows backfilled from `DIVISION_DEFAULT_PHONE`. |
| `created_at`, `updated_at` | timestamps | |

---

## 10. `resource_types`

Catalog used by `activity_resources.type_of_resource_id`.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `code` | `VARCHAR(50) UNIQUE NOT NULL` | Lowercase: `rfp` / `asg` / `ccn` |
| `name` | `VARCHAR(255) NOT NULL` | Display name |
| `active` | `BOOLEAN NOT NULL` | |
| `created_at`, `updated_at` | timestamps | |

---

## 11. `project_status_transitions`

Drives the project state machine. Each row is one allowed `(from, to)` edge. The seed row has `from_status=NULL` for the initial state.

> **Doc 33 change 1**: the `version_only` column was dropped along with the versioning feature. The `suspended` status row is also gone.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `from_status` | `VARCHAR(50) NULL` | NULL = initial seed |
| `to_status` | `VARCHAR(50) NOT NULL` | |
| `requires_admin` | `BOOLEAN NOT NULL` | |
| `active` | `BOOLEAN NOT NULL` | Soft-deactivate via `set_active(False)` |
| `description` | `VARCHAR(500) NULL` | |
| `created_at`, `updated_at` | timestamps | |

**Constraint**: `UNIQUE (from_status, to_status)`. **Index**: `(to_status, active)`.

Live edges seeded: `null → new`, `new → draft`, `new → published`, `draft → published`, `draft → new`, `published → draft`, `new|draft|published → closed`.

---

## 12. `projects`

> **Doc 33 change 1**: the baseline / version split was REMOVED. The columns `is_version`, `version_of`, `baseline_id`, `version_no` and the partial unique index `ux_projects_active_version_per_baseline` are gone. Tasks/subtasks now live directly on the project. The `suspended` status was dropped.

**Doc 24 part 1** relaxed `start_date` (may now be in the past). **Doc 27** retyped every datetime column to `UtcDateTime` for IST/UTC equality safety.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID — public handle |
| `project_code` | `VARCHAR(30) UNIQUE NOT NULL` | Server-generated `UIDAI-PR<yymmddhhmmss-IST>` |
| `name` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `active`, `public` | `BOOLEAN NOT NULL` | |
| `status_explanation` | `TEXT NULL` | |
| `parent_id` | `VARCHAR(36) FK → projects(id) NULL` | Generic parent (legacy) |
| `status` | `VARCHAR(50) NOT NULL` | `new` / `draft` / `published` / `closed` (doc 33: no more `suspended`) |
| `owner` | `VARCHAR(255) NULL` | Strict division code — `tmd1` / `tmd2` / `others` |
| `owner_other` | `VARCHAR(255) NULL` | Required when `owner='others'` |
| `category` | `VARCHAR(50) NULL` | `MSAP` / `MSIP` / `BSP` / `others` |
| `category_other` | `VARCHAR(255) NULL` | Required when `category='others'` |
| `category_other_reason` | `VARCHAR(1000) NULL` | Required when `category='others'` (doc 15) |
| `start_date`, `end_date` | `UtcDateTime NULL` | Doc 24: `start_date` may be in the past |
| `actual_start_date`, `actual_end_date` | nullable `UtcDateTime` | |
| `created_by`, `updated_by`, `deleted_by` | `VARCHAR(36) FK → users(id)` | |
| `created_at`, `updated_at`, `deleted_at` | `UtcDateTime` / nullable | |

**Indexes**: `project_code`, `name`, `active`, `public`, `parent_id`, `status`, `owner`, `category`, `start_date`, `end_date`, `deleted_at`.

**Relationships**: `milestones` (1-N), `project_vendors` (M-N vendors), `project_members` (M-N users), `project_audit_logs`.

---

## 13. `project_members`

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `user_id` | `VARCHAR(36) FK → users(id) NOT NULL` | Doc 26 |
| `roles` | `JSON NOT NULL` | Project-scoped roles list (separate from global `user_roles`) |
| `created_at`, `updated_at` | timestamps | |

**Constraint**: `UNIQUE (project_id, user_id)`. **Indexes**: `project_id`, `user_id`, `created_at`.

---

## 14. `project_vendors`

Composite-PK junction.

| Column | Type | Notes |
|---|---|---|
| `project_id` | `VARCHAR(36) PK FK → projects(id)` | |
| `vendor_id` | `VARCHAR(36) PK FK → vendors(id)` | |
| `created_at` | timestamp | |

---

## 15. `project_audit_logs`

Append-only audit trail. **Doc 33 change 1** added `actor_role` so the audit row records the role bucket (admin / member / vendor / viewer) the actor occupied at write time, plus expanded coverage to T/S create+delete + dep-edge changes.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `actor_id` | `VARCHAR(36) FK → users(id) NULL` | Doc 26 |
| `actor_role` | `VARCHAR(50) NULL` | **Doc 33** — `admin` / `member` / `vendor` / `viewer` |
| `action` | `VARCHAR(64) NOT NULL` | E.g. `milestone.create`, `task.delete`, `*.dep_change`, `project.vendor.*`, `project.member.*` |
| `before` | `JSON NULL` | Pre-state snapshot |
| `after` | `JSON NULL` | Post-state snapshot |
| `created_at` | `UtcDateTime` | |

**Indexes**: `project_id`, `created_at`, `action`, `actor_id`, `actor_role`.

---

## 16. `milestones`

**Doc 22** dropped the legacy `depends` JSON column — milestone deps now live in `milestone_dependencies`. **Doc 22** added the per-project live-position partial-unique index. **Doc 33 change 1** dropped `cloned_from_id` (versioning lineage gone).

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `name` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `start_date`, `end_date` | `UtcDateTime NOT NULL` | |
| `position` | `INTEGER NOT NULL` | |
| `status` | `VARCHAR(32) NOT NULL` | `not_completed` / `completed` |
| `created_by`, `updated_by` | `VARCHAR(36) FK → users(id) NULL` | |
| `created_at`, `updated_at` | timestamps | |
| `deleted_at` | nullable `UtcDateTime` | Soft-delete (no `deleted_by` here) |

**Constraints / indexes**: Partial unique `uq_milestones_project_position_live` on `(project_id, position) WHERE deleted_at IS NULL` — drives `M{m}` label rank.

**Relationships**: `activities` (1-N), `milestone_dependencies` (M-N self), `milestone_vendors` (M-N vendors).

---

## 17. `milestone_dependencies`

**Doc 21A**. Same shape as the activity / task / subtask edge tables.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | Surrogate UUID — multiple historical rows per pair coexist |
| `source_milestone_id` | `VARCHAR(36) FK → milestones(id) NOT NULL` | |
| `target_milestone_id` | `VARCHAR(36) FK → milestones(id) NOT NULL` | |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | Denormalized for fast scoping |
| `created_at` | timestamp | |
| `deleted_at`, `deleted_by` | nullable | Soft-delete; `deleted_by` is `VARCHAR(36) FK → users(id)` |

**Constraint**: Partial unique `uq_milestone_deps_pair_live` on `(source, target) WHERE deleted_at IS NULL`.

**Service rules**: same project, no self-edge, acyclic. **Dep-date rules — doc 31**: `source.start >= target.start` (equality OK) AND `source.end > target.end` (strict). Status-completion gate: cannot mark `completed` while any target is incomplete.

> **Doc 33 change 1 cleanup**: the `propagate_milestone_dependency_change` baseline → version propagation was removed when versioning was dropped. Edits stay scoped to the single project.

---

## 18. `milestone_vendors`

Composite-PK junction.

| Column | Type | Notes |
|---|---|---|
| `milestone_id` | `VARCHAR(36) PK FK → milestones(id)` | |
| `vendor_id` | `VARCHAR(36) PK FK → vendors(id)` | |
| `created_at` | timestamp | |

---

## 19. `activities`

Children of milestones. **Doc 33 change 1** dropped `cloned_from_id`.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | Denormalized root project |
| `milestone_id` | `VARCHAR(36) FK → milestones(id) NOT NULL` | |
| `name` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `type` | `VARCHAR(20) NOT NULL` | `standard` / `resource` / `transactional` (CHECK) |
| `start_date`, `end_date` | `UtcDateTime NOT NULL` | |
| `actual_start_date`, `actual_end_date` | nullable `UtcDateTime` | |
| `position` | `INTEGER NOT NULL` | |
| `resource_mode` | `VARCHAR(10) NULL` | `count` / `details` (CHECK) — only when `type='resource'` |
| `resource_count` | `INTEGER NULL` | ≥ 1 (CHECK), only with `resource_mode='count'` |
| `status` | `VARCHAR(32) NULL` | `not_completed` / `completed`, standard-only |
| `created_by`, `updated_by` | `VARCHAR(36) FK → users(id) NULL` | |
| `created_at`, `updated_at` | timestamps | |
| `deleted_at` | nullable | |

**Constraints**: CHECKs on `type`, `resource_mode`, `resource_count`. Per-milestone live-position uniqueness.

**Relationships**: `tasks` (1-N), `activity_dependencies` (M-N self), `activity_resources` (1-1 live).

---

## 20. `activity_dependencies`

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `source_activity_id` | `VARCHAR(36) FK → activities(id) NOT NULL` | |
| `target_activity_id` | `VARCHAR(36) FK → activities(id) NOT NULL` | |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `created_at` | timestamp | |
| `deleted_at`, `deleted_by` | nullable; `deleted_by` is `VARCHAR(36) FK → users(id)` | |

**Constraint**: Partial unique on `(source, target) WHERE deleted_at IS NULL`.

**Service rules**: same project, no self-edge, acyclic. **Dep-date — doc 30**: `source.start >= target.end` (equality allowed). Forward + reverse directions guarded.

---

## 21. `activity_resources`

Soft-deleted; unique-live by `activity_id`.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | |
| `activity_id` | `VARCHAR(36) FK → activities(id) NOT NULL` | |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `resource_name` | `VARCHAR(255) NOT NULL` | |
| `onboard_date`, `actual_onboard_date`, `offboard_date`, `actual_offboard_date` | nullable `UtcDateTime` | |
| `position` | `VARCHAR(255) NULL` | Job position label |
| `designation`, `job_role`, `qualification` | nullable strings | |
| `experience_years` | `NUMERIC(4,1) NULL` | |
| `type_of_resource_id` | `VARCHAR(36) FK → resource_types(id) NULL` | Activity-only classification |
| `division`, `division_other` | nullable | Same `tmd1/tmd2/others` enum + free-text |
| `created_at`, `updated_at`, `deleted_at` | timestamps / nullable | |

**Constraint**: `uq_activity_resources_activity_live` on `(activity_id) WHERE deleted_at IS NULL`.

---

## 22. `tasks`

> **Doc 33 change 1**: the version-only writability rule was dropped. Tasks live directly under the project's M/A subtree on any live project.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `activity_id` | `VARCHAR(36) FK → activities(id) NOT NULL` | |
| `name` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `type` | `VARCHAR(20) NOT NULL` | CHECK (`standard`/`resource`/`transactional`) — derived from parent activity at create time |
| `start_date`, `end_date` | `UtcDateTime NOT NULL` | |
| `actual_start_date`, `actual_end_date` | nullable `UtcDateTime` | |
| `position` | `INTEGER NOT NULL` | |
| `resource_mode`, `resource_count` | nullable + CHECKs | |
| `created_by`, `updated_by` | `VARCHAR(36) FK → users(id) NULL` | |
| `created_at`, `updated_at`, `deleted_at` | timestamps / nullable | |

**Constraint**: `uq_tasks_activity_position_live` on `(activity_id, position) WHERE deleted_at IS NULL`.

---

## 23. `task_dependencies`

Same shape as activity edges. **Doc 24 part 3** dropped the parent-activity hierarchy rule — service rules are now identical to activity deps.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | |
| `source_task_id` | `VARCHAR(36) FK → tasks(id) NOT NULL` | |
| `target_task_id` | `VARCHAR(36) FK → tasks(id) NOT NULL` | |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `created_at` | timestamp | |
| `deleted_at`, `deleted_by` | nullable; `deleted_by` is `VARCHAR(36) FK → users(id)` | |

**Constraint**: Partial unique on `(source, target) WHERE deleted_at IS NULL`.

---

## 24. `task_resources`

Same shape as `activity_resources` minus the classification columns (no `type_of_resource_id`, no `division*`).

**Constraint**: `uq_task_resources_task_live` on `(task_id) WHERE deleted_at IS NULL`.

---

## 25. `subtasks`

> **Doc 33 change 1**: the version-only writability rule was dropped. **Doc 24 part 2** added `parent_subtask_id` (nullable self-FK) for nesting. Top-level subtasks have it `NULL`; nested ones point at their immediate parent. `task_id` always carries the **root task** so "all subtasks under this task" stays a one-column-filter query.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `task_id` | `VARCHAR(36) FK → tasks(id) NOT NULL` | Root task — always set |
| `parent_subtask_id` | `VARCHAR(36) FK → subtasks(id) NULL` | **Doc 24** — nullable self-FK |
| `name` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `type` | `VARCHAR(20) NOT NULL` | CHECK — derived from root task |
| `start_date`, `end_date` | `UtcDateTime NOT NULL` | |
| `actual_start_date`, `actual_end_date` | nullable `UtcDateTime` | |
| `position` | `INTEGER NOT NULL` | |
| `resource_mode`, `resource_count` | nullable + CHECKs | |
| `created_by`, `updated_by` | `VARCHAR(36) FK → users(id) NULL` | |
| `created_at`, `updated_at`, `deleted_at` | timestamps / nullable | |

**Constraints**
- `uq_subtasks_task_position_top_live` on `(task_id, position) WHERE deleted_at IS NULL AND parent_subtask_id IS NULL` — top-level siblings under a task.
- `uq_subtasks_subtask_position_live` on `(parent_subtask_id, position) WHERE deleted_at IS NULL AND parent_subtask_id IS NOT NULL` — children under one subtask.

**Operational notes**
- **Cascade-on-delete** is recursive: deleting a subtask soft-deletes every descendant subtask + their resource rows + every dep edge touching any descendant.
- **Depth cap** via `SUBTASK_MAX_NESTING_DEPTH` env var (`Optional[int]`, default `None` = unlimited).

---

## 26. `subtask_dependencies`

Same shape as task edges. **Doc 24 part 3** dropped the parent-task hierarchy rule — any subtask in the project can depend on any other.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | |
| `source_subtask_id` | `VARCHAR(36) FK → subtasks(id) NOT NULL` | |
| `target_subtask_id` | `VARCHAR(36) FK → subtasks(id) NOT NULL` | |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `created_at` | timestamp | |
| `deleted_at`, `deleted_by` | nullable; `deleted_by` is `VARCHAR(36) FK → users(id)` | |

---

## 27. `subtask_resources`

Same shape as `task_resources`. `uq_subtask_resources_subtask_live` on `(subtask_id) WHERE deleted_at IS NULL`.

---

## 28. `comments`

Polymorphic on M/A/T/S target. **Doc 35** unified comments + attachments: a row now represents a "send event" carrying body text, an attachments JSON array, or both. The separate `attachments` table was DROPPED. Comment-only, attachment-only, and combined rows all live here.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | |
| `target_kind` | `VARCHAR(20) NOT NULL` | `milestone` / `activity` / `task` / `subtask` |
| `target_id` | `VARCHAR(36) NOT NULL` | UUID of the target entity |
| `body` | `TEXT NULL` | **Doc 35**: nullable. Service layer enforces "body OR attachments must be present". |
| `attachments` | `JSON NULL` | **Doc 35** — array of `{url, filename, mimeType, sizeBytes, uploadedAt}`. URL points at external file server (or relative path served by the local fallback `GET /files/{key}`). |
| `author_user_id` | `VARCHAR(36) FK → users(id) NOT NULL` | Doc 26 |
| `created_at`, `updated_at`, `deleted_at` | timestamps / nullable | |
| `deleted_by` | `VARCHAR(36) FK → users(id) NULL` | |

**Indexes**: composite `(target_kind, target_id)` for "list comments on this target", `(target_kind, target_id, deleted_at)` for the active-only filter, plus `created_at`.

**Doc 35 migration**: every live attachment row was folded onto its parent comment's `attachments` array; standalone attachments became attachment-only comments (body NULL). Soft-deleted attachments were not migrated (effectively hidden under "deleted is gone").

---

## 29. `notification_log`

**Doc 33 change 3**. Every email/SMS/OTP dispatch is recorded here regardless of which `NotificationClient` backend handled it (mock writes the row as the terminal sink; http writes it pre-call so failures are visible).

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `user_id` | `VARCHAR(36) FK → users(id) NULL` | Nullable so deleted users don't break the audit trail |
| `channel` | `VARCHAR(16) NOT NULL` | `email` / `sms` |
| `recipient` | `VARCHAR(320) NOT NULL` | Email or phone at dispatch time (frozen — survives later contact-detail edits) |
| `template_kind` | `VARCHAR(64) NOT NULL` | `otp_login` / `password_reset_link` / `password_reset_otp` / … |
| `payload` | `JSON NULL` | Free-form. **Never stores secrets** — codes are kept hashed in their own tables. |
| `status` | `VARCHAR(16) NOT NULL DEFAULT 'queued'` | `queued` / `sent` / `failed` |
| `error` | `VARCHAR(500) NULL` | Backend-reported error |
| `created_at` | `UtcDateTime NOT NULL` | |

**Indexes**: composite `(user_id, template_kind)`, `created_at`, plus per-column indexes on `channel`, `template_kind`, `status`.

**Doc 33 follow-up**: when the live HTTP client is wired to PMIS-notification-service, the row's `payload._dispatch` carries the upstream provider + `message_id` for cross-service correlation.

---

## 30. `otp_codes`

**Doc 33 change 3** — 2FA OTP rows. Codes are **hashed** at rest (HMAC-SHA256 with `OTP_HASH_PEPPER`, falling back to `SECRET_KEY`).

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `user_id` | `VARCHAR(36) FK → users(id) NOT NULL` | |
| `channel` | `VARCHAR(16) NOT NULL` | `email` / `sms` |
| `code_hash` | `VARCHAR(128) NOT NULL` | HMAC-SHA256(pepper, plaintext) |
| `ephemeral_token_hash` | `VARCHAR(128) NOT NULL` | Hash of the opaque token returned at `/login` stage 1 |
| `generated_at` | `UtcDateTime NOT NULL` | |
| `expires_at` | `UtcDateTime NOT NULL` | TTL = `OTP_TTL_SECONDS` (default 300) |
| `consumed_at` | `UtcDateTime NULL` | Set on successful verify (single-use) |
| `attempt_count` | `INTEGER NOT NULL DEFAULT 0` | Wrong-code submits; after `OTP_MAX_ATTEMPTS` the row is auto-consumed |
| `last_sent_at` | `UtcDateTime NOT NULL` | For the `OTP_RESEND_COOLDOWN_SECONDS` cooldown check |

**Indexes**: composite `(user_id, consumed_at)` (active OTPs), plus `ephemeral_token_hash`, `expires_at`, `consumed_at`.

**Lookup**: `/login/verify-otp` resolves the row by `ephemeral_token_hash` (latest non-consumed). Sentinel rows are written at `/login` stage 1 to bind `ephemeral_token → user`; subsequent `/login/send-otp` calls add new rows with their own `code_hash` + `last_sent_at`.

---

## 31. `password_reset_tokens`

**Doc 33 change 3**. Single-use, hashed reset tokens issued by `/forgot-password`.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `user_id` | `VARCHAR(36) FK → users(id) NOT NULL` | |
| `channel` | `VARCHAR(16) NOT NULL` | `email` (URL-token) / `sms` (numeric OTP) |
| `token_hash` | `VARCHAR(128) UNIQUE NOT NULL` | HMAC-SHA256(pepper, plaintext) |
| `generated_at` | `UtcDateTime NOT NULL` | |
| `expires_at` | `UtcDateTime NOT NULL` | TTL = `PASSWORD_RESET_TTL_SECONDS` (default 3600) |
| `consumed_at` | `UtcDateTime NULL` | Single-use — set on successful reset |

**Indexes**: composite `(user_id, consumed_at)`, plus `token_hash` (UNIQUE), `expires_at`, `consumed_at`.

**Anti-enumeration**: `/forgot-password` always returns 200 with a generic message; only inserts a row when the user actually exists. The two-channel scheme (URL token vs 6-digit OTP) accommodates SMS lacking reliable URL rendering.

---

## 32. `notification_templates`

**Doc 36** — DB-backed email + SMS template catalog. Replaces the hardcoded if/elif/else blocks that used to live in `app/shared/notifications.py::_render_email` / `_render_sms`. Renderers look up the active row by `(template_kind, channel)` and `str.format(**placeholders)` over the stored copy. Computed placeholders (`ttl_minutes` from `ttl_seconds`, `reset_url` from `FRONTEND_BASE_URL` + `token`) are derived at render time before substitution.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `template_kind` | `VARCHAR(64) NOT NULL` | `otp_login` / `password_reset_link` / `password_reset_otp` (seeded built-ins). Free-form so admins can register kinds for new dispatch sites added in code. |
| `channel` | `VARCHAR(16) NOT NULL` | `email` or `sms`. |
| `subject` | `VARCHAR(500) NULL` | Email subject (NOT NULL via service rule when `channel='email'`); NULL on SMS rows. |
| `body` | `TEXT NOT NULL` | HTML body (email) or plaintext (SMS). |
| `is_html` | `BOOLEAN NOT NULL DEFAULT TRUE` | Forwarded to the notification microservice's `is_html` field on email send. |
| `is_builtin` | `BOOLEAN NOT NULL` | TRUE for the six seeded rows; protected from hard delete (subject + body ARE editable). |
| `active` | `BOOLEAN NOT NULL DEFAULT TRUE` | Soft-deactivate without delete. Renderer falls back to a generic body when no active row matches. |
| `description` | `VARCHAR(1024) NULL` | Free-form ops note. |
| `created_at`, `updated_at` | `UtcDateTime` | |

**Indexes**:
- Composite `(template_kind, channel, active)` for the renderer's hot lookup.
- Postgres only: partial unique `uq_notification_templates_kind_channel_active` on `(template_kind, channel) WHERE active = TRUE` so the at-most-one-active-row-per-pair invariant the renderer relies on is enforced at the DB level. SQLite uses a service-layer guard (the active-uniqueness check in `POST /api/v3/master/notification_templates/create` and `/restore`).

**Placeholder spec** (validated on create + update at the schema layer for the well-known kinds; unknown kinds skip the check):

| Template kind | Channel | Allowed placeholders |
|---|---|---|
| `otp_login` | email + sms | `{code}`, `{ttl_minutes}` |
| `password_reset_link` | email | `{reset_url}`, `{token}`, `{ttl_minutes}` |
| `password_reset_link` | sms | `{token}`, `{ttl_minutes}` |
| `password_reset_otp` | email + sms | `{code}`, `{ttl_minutes}` |

**API**: `/api/v3/master/notification_templates/*` — list, get, create, update, delete (soft), restore. All gated by `master_data:view` / `master_data:manage`.

---

## 33. `meetings`

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `title` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `scheduled_at` | `UtcDateTime NOT NULL` | |
| `duration_minutes` | `INTEGER NULL` | |
| `location` | `VARCHAR(255) NULL` | |
| `created_by_id` | `VARCHAR(36) FK → users(id) NOT NULL` | Doc 26 |
| `created_at`, `updated_at` | timestamps | |

---

## 34. `meeting_participants`

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `meeting_id` | `INTEGER FK → meetings(id) NOT NULL` | |
| `user_id` | `VARCHAR(36) FK → users(id) NOT NULL` | Doc 26 |
| `created_at` | timestamp | |

**Constraint**: `UNIQUE (meeting_id, user_id)`.

---

## 35. `meeting_agenda_items`

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `meeting_id` | `INTEGER FK → meetings(id) NOT NULL` | |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `title` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `position` | `INTEGER NOT NULL` | |
| `work_package_id` | `INTEGER FK → work_packages(id) NULL` | Optional cross-link |
| `created_at`, `updated_at` | timestamps | |

---

## 36. `work_package_types`

Catalog for the `work_packages` module. Built-ins seeded at boot: Task, Bug, Feature, Story, Milestone, Activity.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | |
| `name` | `VARCHAR(255) NOT NULL` | |
| `internal_name` | `VARCHAR(100) UNIQUE NOT NULL` | |
| `is_builtin` | `BOOLEAN NOT NULL` | |
| `is_active` | `BOOLEAN NOT NULL` | |
| `position` | `INTEGER NOT NULL` | |
| `created_at`, `updated_at` | timestamps | |

---

## 37. `work_packages`

OpenProject-style work-package entity. Surfaced via `/api/v3/projects/{id}/work_packages` and `/api/v3/work_packages/{id}` — independent of the M/A/T/S flow but live in the API surface.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `subject` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `parent_id` | `INTEGER FK → work_packages(id) NULL` | Self-FK (parent/child WPs) |
| `type_id` | `INTEGER FK → work_package_types(id) NULL` | |
| `assignee_id` | `VARCHAR(36) FK → users(id) NULL` | Doc 26 |
| `status`, `priority` | `VARCHAR(100) NOT NULL` | |
| `done_ratio` | `INTEGER NOT NULL` | 0-100 |
| `start_date`, `end_date` | nullable `UtcDateTime` | |
| `created_at`, `updated_at` | timestamps | |

---

## Relationship summary diagram

```
users (id is VARCHAR(36) UUID — doc 26; user_code US-… display ID — doc 25;
       two_factor_enabled — doc 33) ────────────────────────────────────────
  ├─ user_roles ── roles ── role_permissions ── permissions
  ├─ user_permissions ─────────────────────────── permissions
  ├─ revoked_tokens
  ├─ vendor_id → vendors (id UUID + vendor_code VN-…)
  ├─ project_members → projects
  ├─ comments (author_user_id; doc 35 — body OR attachments JSON list)
  ├─ notification_log / otp_codes / password_reset_tokens (doc 33 ch 3)
  └─ meetings / meeting_participants

projects (single-tier — versioning REMOVED in doc 33) ─────────────────────
  ├─ project_vendors ── vendors
  ├─ project_members → users
  ├─ project_audit_logs (with actor_role — doc 33)
  └─ milestones
        ├─ milestone_dependencies (M-N self; dep-date rules — doc 31)
        ├─ milestone_vendors ── vendors
        └─ activities
              ├─ activity_dependencies (M-N self; dep-date rules — doc 30)
              ├─ activity_resources → resource_types
              └─ tasks
                    ├─ task_dependencies
                    ├─ task_resources
                    └─ subtasks (nested via parent_subtask_id — doc 24)
                          ├─ subtask_dependencies
                          └─ subtask_resources

meetings → projects
  ├─ meeting_participants → users
  └─ meeting_agenda_items → work_packages (optional)

work_packages → work_package_types

divisions, resource_types, project_status_transitions,
notification_templates (doc 36) ── catalog tables
```

---

## Migration trail

| Doc | Schema impact |
|-----|---------------|
| 17 | Inclusive date validation; `actualStartDate` |
| 18 | `divisions` table; `vendor.email/contact_person/phone_number`; strict-division `owner` |
| 19 | `users.previous_refresh_token_jti` + `…_valid_until` (refresh-token grace window) |
| 20 | Drop `project_owners` table; consolidate catalog CRUD under `/master/*` |
| 21A | Add `milestone_dependencies` table |
| 21B | Drop `users.admin`; drop `roles.permissions` JSON; add `roles.description`; add `permissions`, `role_permissions`, `user_roles`, `user_permissions` |
| 22 | Drop `milestones.depends`; add per-parent live-position partial-unique indexes on M/A/T/S |
| 23 | Add `users.phone_number`; require `vendors.phone_number` at the wire |
| 24 | Add `subtasks.parent_subtask_id`; replace single position-uniqueness index with two partial-unique indexes (top-level vs nested); drop dependency hierarchy rules at task/subtask level (service-layer only) |
| 25 | Add `vendors.vendor_code` + `users.user_code` (`VN-…` / `US-…`); polymorphic lookup |
| 26 | **Flip `users.id` from `INTEGER` to `VARCHAR(36)` UUID.** Every FK column referencing `users.id` retyped to `String(36)`; pre-doc-26 JWTs invalidated |
| 27 | Retype every datetime column to `UtcDateTime` (TIMESTAMP WITH TIME ZONE on Postgres) so cross-format date comparisons land on the same calendar instant; pre-doc-26 stale JWT 401-not-500 |
| 28 | Nested subtask listing fix (no schema change — service-layer query) |
| 29 | IST calendar-date input normalization (no schema change — pydantic serializer) |
| 30 | Dep-date enforcement (no schema change — service-layer guards); publish-time structural-completeness gate |
| 31 | Milestone-specific dep-date rules + status-completion gate (no schema change) |
| 32 | M/A/T/S create endpoints accept multipart; `_normalize` IST-midnight tolerance for legacy rows; position auto-bump (no schema change) |
| 33 change 1 | **Versioning removed.** Drop `projects.is_version` / `version_of` / `baseline_id` / `version_no`; drop `milestones.cloned_from_id`, `activities.cloned_from_id`; drop `project_status_transitions.version_only`; drop `suspended` status row + every `version_only=true` row; remove `ux_projects_active_version_per_baseline` partial unique index. Add `project_audit_logs.actor_role` + `idx_project_audit_logs_action`. Seed `vendor` role |
| 33 change 2 | RBAC catalog grouping endpoint (no schema change); dead RBAC code removed from `app/core/rbac.py` |
| 33 change 3 | Add `users.two_factor_enabled`; add tables `notification_log`, `otp_codes`, `password_reset_tokens` |
| 33 hotfix | `MIGRATIONS_AUTORUN` / `MIGRATIONS_REQUIRED` boot flags + `DATABASE_URL_MIGRATIONS` for deploys where the runtime DB role lacks DDL ownership; PG boolean literal fix in `two_factor_enabled` backfill |
| 33 follow-up | Live `HttpNotificationClient` wired to PMIS-notification-service (`POST /api/v1/notifications/email/send` + `/sms/send`); `notification_log` row lifecycle (queued → sent / failed) with provider + `message_id` stashed under `payload._dispatch` |
| 34 | Cascade soft-delete of comments + attachments under M/A/T/S delete; external-dep block on M/A/T/S delete (`dependency_block`); cascade-restore via uniform cascade timestamp (no schema change — repo-layer) |
| 35 | **Comments + attachments unified.** Add `comments.attachments` JSON column; relax `comments.body` to NULL; **DROP the `attachments` table** after data migration (live rows folded onto parent comments; standalone attachments became attachment-only comments). Local fallback `GET /files/{key}` route added for legacy storage keys |
| 36 | **DB-backed notification templates**: new `notification_templates` master table (email + SMS template content with `{placeholder}` substitution; built-in seed for `otp_login` / `password_reset_link` / `password_reset_otp` × email/sms); `/api/v3/master/notification_templates/*` CRUD endpoints; renderers in `app/shared/notifications.py` look up active rows by `(template_kind, channel)` with placeholder validation at write time. **Division contact required**: `divisions.email` + `phone_number` flipped to NOT NULL after env-driven seed-row backfill (`DIVISION_DEFAULT_EMAIL` / `DIVISION_DEFAULT_PHONE`). Alembic head: `c2d4e7f9a1b3`. |
| 37 part 1 | **Static-data master tables**. Four new catalogs — `project_categories` (seed: MSAP/MSIP/BSP/others), `activity_types` (seed: standard/resource/transactional), `milestone_statuses` + `activity_statuses` (each seed: not_completed/completed). In-code tuples (`PROJECT_CATEGORY_CHOICES`, `ACTIVITY_TYPES`, `MILESTONE_STATUS_CHOICES`, `ACTIVITY_STATUS_CHOICES`) become **fallbacks** consulted only when the DB catalog is empty (matches the doc-20 `project_status_transitions` precedent). New shared helper `app/shared/static_catalog.py` does the DB-first lookup. `/api/v3/master/{project_categories,activity_types,milestone_statuses,activity_statuses}/*` CRUD endpoints (24 routes total) gated by `master_data:view`/`master_data:manage`. Built-ins protected from delete; structural flags (`requires_other`, `is_terminal`) locked on built-ins. Alembic head: `d3e5f7a9b1c2`. |
| 37 part 2 | **User-service microservice extraction (SHIPPED).** PMIS-user-management (port 8001) brought to monolith parity (commits `f840fde` + `19a30e5`). Monolith proxies `/api/v3/users/*` + `/api/v3/master/{roles,permissions,notification_templates}/*` to port 8001 via `USER_SERVICE_PROXY_ENABLED` flag (default off). Fail-closed 503 when user-service unreachable. Same SECRET_KEY, shared Postgres. No schema additions on this end — all touched tables already exist from earlier docs; doc 37 part 2 is a service-boundary refactor only. See [planned_changes/37](../planned_changes/37.%20Static%20data%20to%20master%20endpoints%20%2B%20user-service%20microservice%20extraction.md) for cutover runbook. |
