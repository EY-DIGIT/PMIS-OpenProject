# PMIS Database Schema

**Last refresh**: 2026-05-04 (post-doc 26)
**Source of truth**: SQLAlchemy models under [app/infrastructure/db/models/](../app/infrastructure/db/models/) → regenerated DDL at [scripts/ddl/](../scripts/ddl/) (`schema_postgres.sql`, `schema_sqlite.sql`).
**Tables on `Base.metadata`**: 34.

This doc inventories every table, its columns, indexes, FKs, and relationships. The DDL files are the authoritative type / index detail; this doc explains *intent* — what each table holds, how it links to its neighbours, and which docs introduced or reshaped it.

> **Migration management.** PostgreSQL runs `alembic upgrade head` on every boot. SQLite uses `Base.metadata.create_all` plus a column-drift healer. The latest Alembic head is `b3c4d5e6f7a8` (doc 26 — `users.id` flipped to UUID).

---

## Table of contents

| # | Table | Purpose |
|---|-------|---------|
| 1 | [`users`](#1-users) | User accounts (with refresh-token rotation slots, vendor + division mapping) |
| 2 | [`roles`](#2-roles) | Named permission bundles |
| 3 | [`permissions`](#3-permissions) | Permission catalog (string codes) |
| 4 | [`role_permissions`](#4-role_permissions) | Many-to-many: role ↔ permission |
| 5 | [`user_roles`](#5-user_roles) | Many-to-many: user ↔ role |
| 6 | [`user_permissions`](#6-user_permissions) | Direct user-level permission grants (additive) |
| 7 | [`revoked_tokens`](#7-revoked_tokens) | JWT JTI blacklist |
| 8 | [`vendors`](#8-vendors) | Vendor catalog |
| 9 | [`divisions`](#9-divisions) | Division catalog (`tmd1` / `tmd2` / `others` + custom) |
| 10 | [`resource_types`](#10-resource_types) | Resource-type catalog (RFP / ASG / CCN + custom) |
| 11 | [`project_status_transitions`](#11-project_status_transitions) | Allowed `(from_status, to_status)` edges + flags |
| 12 | [`projects`](#12-projects) | Projects + versions (`is_version` + lineage) |
| 13 | [`project_members`](#13-project_members) | Per-project member assignments (with project-scoped roles) |
| 14 | [`project_vendors`](#14-project_vendors) | Project ↔ vendor mapping |
| 15 | [`project_audit_logs`](#15-project_audit_logs) | Audit trail for project / M / A writes |
| 16 | [`milestones`](#16-milestones) | Milestones under a project |
| 17 | [`milestone_dependencies`](#17-milestone_dependencies) | Milestone → milestone edges (doc 21A) |
| 18 | [`milestone_vendors`](#18-milestone_vendors) | Milestone ↔ vendor mapping |
| 19 | [`activities`](#19-activities) | Activities under a milestone |
| 20 | [`activity_dependencies`](#20-activity_dependencies) | Activity → activity edges |
| 21 | [`activity_resources`](#21-activity_resources) | Resource rows for resource-type activities |
| 22 | [`tasks`](#22-tasks) | Tasks under an activity (version-only) |
| 23 | [`task_dependencies`](#23-task_dependencies) | Task → task edges |
| 24 | [`task_resources`](#24-task_resources) | Resource rows for tasks |
| 25 | [`subtasks`](#25-subtasks) | Subtasks under a task or another subtask (nested per doc 24) |
| 26 | [`subtask_dependencies`](#26-subtask_dependencies) | Subtask → subtask edges |
| 27 | [`subtask_resources`](#27-subtask_resources) | Resource rows for subtasks |
| 28 | [`comments`](#28-comments) | Polymorphic comments on M/A/T/S |
| 29 | [`attachments`](#29-attachments) | File attachments (per-comment OR direct on M/A/T/S) |
| 30 | [`meetings`](#30-meetings) | Project meetings |
| 31 | [`meeting_participants`](#31-meeting_participants) | Meeting ↔ user |
| 32 | [`meeting_agenda_items`](#32-meeting_agenda_items) | Agenda lines per meeting |
| 33 | [`work_package_types`](#33-work_package_types) | Reserved — built-in WP types catalog |
| 34 | [`work_packages`](#34-work_packages) | Reserved — generic OpenProject-style work packages |

---

## Universal conventions

- **Primary keys**: `INTEGER` autoincrement on remaining catalog/admin tables (`roles`, `divisions`, `meetings`, `meeting_participants`, `meeting_agenda_items`, `project_status_transitions`, `project_audit_logs`, `project_members`, `work_packages`, `work_package_types`); **`VARCHAR(36)` UUID** on every product-facing entity — projects, M/A/T/S, vendors, resource_types, dep edges, comments, attachments, **and `users` as of doc 26**.
- **Soft-delete**: `deleted_at TIMESTAMP NULL` on every entity that supports it; reads filter `deleted_at IS NULL` unless `include_deleted=True` is explicitly passed. Where applicable, `deleted_by INTEGER FK→users(id)` records the actor.
- **Audit timestamps**: `created_at`, `updated_at` (auto-set on insert / update), `created_by`, `updated_by` where the column exists.
- **Position uniqueness**: per-parent live-position partial-unique indexes on M/A/T/S guarantee labels (`M{m}`, `A{m}.{a}`, `T{m}.{a}.{t}`, `S{m}.{a}.{t}.{s1}[.{s2}…]`) are unambiguous (doc 22, doc 24).
- **Edge tables** (`*_dependencies`): surrogate UUID PK + partial unique on `(source, target) WHERE deleted_at IS NULL` so historical (soft-deleted) rows can coexist with a fresh live row for the same pair.
- **All FK columns referencing `users.id` are `VARCHAR(36)` post-doc-26.** This affects every `created_by` / `updated_by` / `deleted_by` / `actor_id` / `assignee_id` / `created_by_id` / `author_user_id` / `uploaded_by_user_id` / `user_id` column across the schema. The per-table sections below note column nullability without re-stating the type each time.

---

## 1. `users`

**Doc 26 flipped `users.id` from `INTEGER` autoincrement to `VARCHAR(36)` UUID.** Every FK column referencing `users.id` (~30 across the schema) was retyped to `String(36)` in the same migration. Doc 25 added the human-readable `user_code` display identifier. Doc 21B dropped the `admin BOOLEAN` column — superuser status comes from membership in the seeded `admin` role via `user_roles`. Doc 19 added the refresh-token grace slot. Doc 23 added `phone_number`.

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
| `refresh_token_expires_at` | `TIMESTAMP NULL` | |
| `previous_refresh_token_jti` | `VARCHAR(64) NULL` | **Doc 19** — grace slot |
| `previous_refresh_token_jti_valid_until` | `TIMESTAMP NULL` | **Doc 19** — grace expiry |
| `vendor_id` | `VARCHAR(36) FK → vendors(id) NULL` | Single vendor per user |
| `division` | `VARCHAR(32) NULL` | One of `tmd1` / `tmd2` / `others` (required at the wire) |
| `division_other` | `VARCHAR(255) NULL` | Required when `division='others'` |
| `phone_number` | `VARCHAR(50) NULL` | **Doc 23** — required at the wire on create |
| `created_at`, `updated_at` | `TIMESTAMP NOT NULL` | |
| `deleted_at`, `deleted_by` | nullable; `deleted_by` is `VARCHAR(36)` post-doc-26 | Soft-delete (self-FK to users.id) |

**Relationships**
- `vendor_id` → `vendors.id`
- `deleted_by` → `users.id` (self-FK)
- Owns: `user_roles`, `user_permissions`, `project_members`, `comments` (`author_user_id`), `attachments` (`uploaded_by_user_id`), `meeting_participants`, `meetings.created_by_id`, `revoked_tokens.user_id`, `project_audit_logs.actor_id`.

**Indexes** include the unique pair `(login)`, `(email)`, plus `vendor_id`, `status`, `created_at`, `deleted_at`.

---

## 2. `roles`

Doc 21B dropped the JSON `permissions` column — grants now live in `role_permissions`. Doc 21B added `description`.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `name` | `VARCHAR(255) UNIQUE NOT NULL` | `admin`, `member`, `viewer` are seeded |
| `description` | `VARCHAR(1024) NULL` | **Doc 21B** |
| `builtin` | `BOOLEAN NOT NULL` | True for the seeded roles |
| `created_at`, `updated_at` | nullable timestamps | |

**Relationships**: `role_permissions` (M-N to permissions), `user_roles` (M-N to users).

**Protections** (service layer): the `admin` role cannot be deleted, renamed, or have its permission set modified through the API. Member/viewer remain editable.

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

**Relationships**: `role_permissions.permission_code`, `user_permissions.permission_code`.

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

Composite-PK junction. Direct membership = "user holds this role's permission set".

| Column | Type | Notes |
|---|---|---|
| `user_id` | `INTEGER PK FK → users(id)` | |
| `role_id` | `INTEGER PK FK → roles(id)` | |
| `created_at` | timestamp | |
| `created_by` | `INTEGER FK → users(id) NULL` | Actor who assigned |

**Lockout protection**: removing the last live user holding the seeded `admin` role returns 403.

---

## 6. `user_permissions`

Direct grants — additive on top of role-derived permissions. There is no deny semantics; to revoke, delete the row.

| Column | Type | Notes |
|---|---|---|
| `user_id` | `INTEGER PK FK → users(id)` | |
| `permission_code` | `VARCHAR(128) PK FK → permissions(code)` | |
| `created_at` | timestamp | |
| `created_by` | nullable FK → users(id) | |

---

## 7. `revoked_tokens`

JWT JTI blacklist. Logout adds the access-token JTI here; the auth middleware checks it on every request.

| Column | Type | Notes |
|---|---|---|
| `jti` | `VARCHAR(64) PK` | |
| `user_id` | `INTEGER FK → users(id) NULL` | |
| `revoked_at` | `TIMESTAMP NOT NULL` | |
| `expires_at` | `TIMESTAMP NOT NULL` | Used by housekeeping to prune expired rows |

---

## 8. `vendors`

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `vendor_code` | `VARCHAR(50) UNIQUE NULL` | **Doc 25** — human-readable display ID `VN-XXXX-YYMMDDHHMMSS` |
| `name` | `VARCHAR(255) UNIQUE NOT NULL` | |
| `description` | `TEXT NULL` | |
| `active` | `BOOLEAN NOT NULL` | Soft-deactivate via `set_active(False)` |
| `email` | `VARCHAR(255) NULL` | |
| `contact_person` | `VARCHAR(255) NULL` | |
| `phone_number` | `VARCHAR(50) NULL` | **Doc 23 made this required at the wire on create** |
| `created_at`, `updated_at` | timestamps | |
| `deleted_at`, `deleted_by` | nullable; `deleted_by` is `VARCHAR(36) FK → users(id)` post-doc-26 | Soft-delete |

**Relationships**: `project_vendors` (M-N projects), `milestone_vendors` (M-N milestones), `users.vendor_id`.

---

## 9. `divisions`

Doc 20: catalog moved under `/api/v3/master/divisions`. Built-ins (`tmd1` / `tmd2` / `others`) are seeded and protected from delete.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `code` | `VARCHAR(64) UNIQUE NOT NULL` | |
| `label` | `VARCHAR(255) NOT NULL` | |
| `is_builtin` | `BOOLEAN NOT NULL` | |
| `requires_other` | `BOOLEAN NOT NULL` | When true, callers must supply a `division_other` free-text |
| `active` | `BOOLEAN NOT NULL` | |
| `created_at`, `updated_at` | timestamps | |

---

## 10. `resource_types`

Catalog used by `activity_resources.type_of_resource_id`.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `code` | `VARCHAR(50) UNIQUE NOT NULL` | Lowercase: `rfp` / `asg` / `ccn` (doc 22 rename) |
| `name` | `VARCHAR(255) NOT NULL` | Display name |
| `active` | `BOOLEAN NOT NULL` | |
| `created_at`, `updated_at` | timestamps | |

---

## 11. `project_status_transitions`

Drives the project state machine. Each row is one allowed `(from, to)` edge. The seed row has `from_status=NULL` for the initial state.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `from_status` | `VARCHAR(50) NULL` | NULL = initial seed |
| `to_status` | `VARCHAR(50) NOT NULL` | |
| `requires_admin` | `BOOLEAN NOT NULL` | |
| `version_only` | `BOOLEAN NOT NULL` | E.g. `suspend` |
| `active` | `BOOLEAN NOT NULL` | Soft-deactivate via `set_active(False)` |
| `description` | `VARCHAR(500) NULL` | |
| `created_at`, `updated_at` | timestamps | |

**Constraint**: `UNIQUE (from_status, to_status)`.

---

## 12. `projects`

Holds both baseline projects and version projects. `is_version` plus `version_of` / `baseline_id` carry the lineage. Doc 24 part 1 relaxed `start_date` (may now be in the past).

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID — public handle |
| `project_code` | `VARCHAR(30) UNIQUE NOT NULL` | Server-generated `UIDAI-PR<timestamp>` |
| `name` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `active`, `public` | `BOOLEAN NOT NULL` | |
| `status_explanation` | `TEXT NULL` | |
| `parent_id` | `VARCHAR(36) FK → projects(id) NULL` | Generic parent (legacy) |
| `version_of` | `VARCHAR(36) FK → projects(id) NULL` | The baseline this version forked from |
| `baseline_id` | `VARCHAR(36) FK → projects(id) NULL` | Self on baselines, baseline-id on versions |
| `version_no` | `INTEGER NULL` | Per-baseline version counter |
| `status` | `VARCHAR(50) NOT NULL` | `new` / `draft` / `published` / `closed` / `suspended` |
| `owner` | `VARCHAR(255) NULL` | Strict division code (doc 18) — `tmd1` / `tmd2` / `others` |
| `owner_other` | `VARCHAR(255) NULL` | Required when `owner='others'` |
| `category` | `VARCHAR(50) NULL` | `MSAP` / `MSIP` / `BSP` / `others` |
| `category_other` | `VARCHAR(255) NULL` | Required when `category='others'` |
| `category_other_reason` | `VARCHAR(1000) NULL` | Required when `category='others'` (doc 15) |
| `start_date`, `end_date` | nullable timestamps | Doc 24 part 1: `start_date` may be in the past |
| `actual_start_date`, `actual_end_date` | nullable | |
| `is_version` | `BOOLEAN NOT NULL` | |
| `created_by`, `updated_by`, `deleted_by` | nullable FK → users(id) | |
| `created_at`, `updated_at`, `deleted_at` | timestamps / nullable timestamp | |

**Constraints**
- Partial unique `ux_projects_active_version_per_baseline` on `(version_of) WHERE is_version=true AND status != 'suspended' AND deleted_at IS NULL` — at most one active version per baseline.

**Relationships**: parents M/A/T/S, vendors via `project_vendors`, members via `project_members`, audit via `project_audit_logs`.

---

## 13. `project_members`

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `user_id` | `INTEGER FK → users(id) NOT NULL` | |
| `roles` | `JSON NOT NULL` | Project-scoped roles list (separate from global `user_roles`) |
| `created_at`, `updated_at` | timestamps | |

**Constraint**: `UNIQUE (project_id, user_id)`.

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

Append-only audit trail.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `actor_id` | `INTEGER FK → users(id) NULL` | |
| `action` | `VARCHAR(64) NOT NULL` | E.g. `milestone.create`, `activity.update.cascade_from_baseline`, `milestone.depends_on.cascade_from_baseline` |
| `before` | `JSON NULL` | Pre-state snapshot |
| `after` | `JSON NULL` | Post-state snapshot |
| `created_at` | timestamp | |

---

## 16. `milestones`

Doc 22 dropped the legacy `depends` JSON column — milestone deps now live in `milestone_dependencies`. Doc 22 added the per-project live-position unique index.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `name` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `start_date`, `end_date` | `TIMESTAMP NOT NULL` | |
| `position` | `INTEGER NOT NULL` | |
| `status` | `VARCHAR(32) NOT NULL` | `not_completed` / `completed` |
| `cloned_from_id` | `VARCHAR(36) FK → milestones(id) NULL` | Lineage to the baseline twin |
| `created_by`, `updated_by` | nullable FK → users(id) | |
| `created_at`, `updated_at` | timestamps | |
| `deleted_at` | nullable | Soft-delete (no `deleted_by` here) |

**Constraints / indexes**
- Partial unique `uq_milestones_project_position_live` on `(project_id, position) WHERE deleted_at IS NULL` — drives `M{m}` label rank.

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
| `deleted_at`, `deleted_by` | nullable | Soft-delete |

**Constraint**: Partial unique `uq_milestone_deps_pair_live` on `(source, target) WHERE deleted_at IS NULL`.

**Service rules**: same project, no self-edge, acyclic. **Propagates** from baseline to active versions via `propagate_milestone_dependency_change` (doc 21A — diverges from activity/task/subtask deps which are version-local).

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

Children of milestones. Carry a `status` only when `type='standard'`.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | Denormalized root project |
| `milestone_id` | `VARCHAR(36) FK → milestones(id) NOT NULL` | |
| `name` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `type` | `VARCHAR(20) NOT NULL` | `standard` / `resource` / `transactional` (CHECK) |
| `start_date`, `end_date` | `TIMESTAMP NOT NULL` | |
| `actual_start_date`, `actual_end_date` | nullable | |
| `position` | `INTEGER NOT NULL` | |
| `resource_mode` | `VARCHAR(10) NULL` | `count` / `details` (CHECK) — only when `type='resource'` |
| `resource_count` | `INTEGER NULL` | ≥ 1 (CHECK), only with `resource_mode='count'` |
| `status` | `VARCHAR(32) NULL` | `not_completed` / `completed`, standard-only |
| `cloned_from_id` | `VARCHAR(36) FK → activities(id) NULL` | Version twin lineage |
| `created_by`, `updated_by` | nullable FK → users(id) | |
| `created_at`, `updated_at` | timestamps | |
| `deleted_at` | nullable | |

**Constraints**: CHECKs on `type`, `resource_mode`, `resource_count`. Per-milestone position uniqueness (live).

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
| `deleted_at`, `deleted_by` | nullable | |

**Constraint**: Partial unique on `(source, target) WHERE deleted_at IS NULL`.

**Service rules**: same project, no self-edge, acyclic. Version-local (cloned at version-create time, evolves independently afterwards).

---

## 21. `activity_resources`

Soft-deleted; unique-live by `activity_id` (one resource row per activity at a time).

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | |
| `activity_id` | `VARCHAR(36) FK → activities(id) NOT NULL` | |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `resource_name` | `VARCHAR(255) NOT NULL` | |
| `onboard_date`, `actual_onboard_date`, `offboard_date`, `actual_offboard_date` | nullable timestamps | |
| `position` | `VARCHAR(255) NULL` | Job position label |
| `designation`, `job_role`, `qualification` | nullable strings | |
| `experience_years` | `NUMERIC(4,1) NULL` | |
| `type_of_resource_id` | `VARCHAR(36) FK → resource_types(id) NULL` | Activity-only classification |
| `division`, `division_other` | nullable | Same `tmd1/tmd2/others` enum + free-text |
| `created_at`, `updated_at`, `deleted_at` | timestamps / nullable | |

**Constraint**: `uq_activity_resources_activity_live` on `(activity_id) WHERE deleted_at IS NULL` — one live resource per activity.

---

## 22. `tasks`

**Version-only** (writes blocked on baseline by `assert_task_subtask_writable`).

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `activity_id` | `VARCHAR(36) FK → activities(id) NOT NULL` | |
| `name` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `type` | `VARCHAR(20) NOT NULL` | CHECK (`standard`/`resource`/`transactional`) — derived from parent activity at create time |
| `start_date`, `end_date` | `TIMESTAMP NOT NULL` | |
| `actual_start_date`, `actual_end_date` | nullable | |
| `position` | `INTEGER NOT NULL` | |
| `resource_mode`, `resource_count` | nullable + CHECKs | |
| `created_by`, `updated_by` | nullable FK → users(id) | |
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
| `deleted_at`, `deleted_by` | nullable | |

**Constraint**: Partial unique on `(source, target) WHERE deleted_at IS NULL`.

---

## 24. `task_resources`

Same shape as `activity_resources` minus the classification columns (no `type_of_resource_id`, no `division*`).

**Constraint**: `uq_task_resources_task_live` on `(task_id) WHERE deleted_at IS NULL`.

---

## 25. `subtasks`

**Version-only.** **Doc 24 part 2** added `parent_subtask_id` (nullable self-FK) for nesting. Top-level subtasks have it `NULL`; nested ones point at their immediate parent. `task_id` always carries the **root task** so "all subtasks under this task" stays a one-column-filter query, and the soft-delete cascade tied to the parent task still finds every descendant.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | UUID |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `task_id` | `VARCHAR(36) FK → tasks(id) NOT NULL` | Root task — always set |
| `parent_subtask_id` | `VARCHAR(36) FK → subtasks(id) NULL` | **Doc 24** — nullable self-FK |
| `name` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `type` | `VARCHAR(20) NOT NULL` | CHECK — derived from root task |
| `start_date`, `end_date` | `TIMESTAMP NOT NULL` | |
| `actual_start_date`, `actual_end_date` | nullable | |
| `position` | `INTEGER NOT NULL` | |
| `resource_mode`, `resource_count` | nullable + CHECKs | |
| `created_by`, `updated_by` | nullable FK → users(id) | |
| `created_at`, `updated_at`, `deleted_at` | timestamps / nullable | |

**Constraints**
- `uq_subtasks_task_position_top_live` on `(task_id, position) WHERE deleted_at IS NULL AND parent_subtask_id IS NULL` — top-level siblings under a task.
- `uq_subtasks_subtask_position_live` on `(parent_subtask_id, position) WHERE deleted_at IS NULL AND parent_subtask_id IS NOT NULL` — children under one subtask.
- Together they keep `S{m}.{a}.{t}.{s1}[.{s2}.{s3}…]` labels unambiguous at every nesting depth.

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
| `deleted_at`, `deleted_by` | nullable | |

---

## 27. `subtask_resources`

Same shape as `task_resources`. `uq_subtask_resources_subtask_live` on `(subtask_id) WHERE deleted_at IS NULL`.

---

## 28. `comments`

Polymorphic on M/A/T/S target.

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | |
| `target_kind` | `VARCHAR(20) NOT NULL` | `milestone` / `activity` / `task` / `subtask` |
| `target_id` | `VARCHAR(36) NOT NULL` | UUID of the target entity |
| `body` | `TEXT NOT NULL` | |
| `author_user_id` | `INTEGER FK → users(id) NOT NULL` | |
| `created_at`, `updated_at`, `deleted_at` | timestamps / nullable | |
| `deleted_by` | nullable FK → users(id) | |

**Indexes** include composite `(target_kind, target_id, deleted_at)` for fast "live comments on this target" reads.

---

## 29. `attachments`

Either attached to a comment (`comment_id` set) or directly to a target (`target_kind` + `target_id` set).

| Column | Type | Notes |
|---|---|---|
| `id` | `VARCHAR(36) PK` | |
| `comment_id` | `VARCHAR(36) FK → comments(id) NULL` | |
| `target_kind`, `target_id` | nullable | |
| `original_filename` | `VARCHAR(500) NOT NULL` | |
| `storage_key` | `VARCHAR(500) UNIQUE NOT NULL` | Disk path |
| `mime_type` | `VARCHAR(100) NOT NULL` | |
| `size_bytes` | `BIGINT NOT NULL` | |
| `uploaded_by_user_id` | `INTEGER FK → users(id) NOT NULL` | |
| `uploaded_at` | timestamp NOT NULL | |
| `deleted_at`, `deleted_by` | nullable | |

---

## 30. `meetings`

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `title` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `scheduled_at` | `TIMESTAMP NOT NULL` | |
| `duration_minutes` | `INTEGER NULL` | |
| `location` | `VARCHAR(255) NULL` | |
| `created_by_id` | `INTEGER FK → users(id) NOT NULL` | |
| `created_at`, `updated_at` | timestamps | |

---

## 31. `meeting_participants`

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `meeting_id` | `INTEGER FK → meetings(id) NOT NULL` | |
| `user_id` | `INTEGER FK → users(id) NOT NULL` | |
| `created_at` | timestamp | |

**Constraint**: `UNIQUE (meeting_id, user_id)`.

---

## 32. `meeting_agenda_items`

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

## 33. `work_package_types` (reserved)

Catalog kept for the reserved `work_packages` module. Built-ins seeded at boot: Task, Bug, Feature, Story, Milestone, Activity.

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

## 34. `work_packages` (reserved)

Generic OpenProject-style work-package entity. **Not part of the doc-19+ M/A/T/S flow.** Kept for compatibility with the legacy `/api/v3/work_packages` module and the agenda-item cross-link.

| Column | Type | Notes |
|---|---|---|
| `id` | `INTEGER PK` | Autoincrement |
| `subject` | `VARCHAR(255) NOT NULL` | |
| `description` | `TEXT NULL` | |
| `project_id` | `VARCHAR(36) FK → projects(id) NOT NULL` | |
| `parent_id` | `INTEGER FK → work_packages(id) NULL` | Self-FK |
| `type_id` | `INTEGER FK → work_package_types(id) NULL` | |
| `assignee_id` | `INTEGER FK → users(id) NULL` | |
| `status`, `priority` | `VARCHAR(100) NOT NULL` | |
| `done_ratio` | `INTEGER NOT NULL` | 0-100 |
| `start_date`, `end_date` | nullable | |
| `created_at`, `updated_at` | timestamps | |

---

## Relationship summary diagram (textual)

```
users (id is VARCHAR(36) UUID — doc 26; user_code VN-... display ID — doc 25) ─
  └─ user_roles ── roles ── role_permissions ── permissions
  └─ user_permissions ─────────────────────────── permissions
  └─ revoked_tokens
  └─ vendor_id → vendors (id UUID + vendor_code VN-... — doc 25)
  └─ project_members → projects
  └─ comments / attachments (author / uploader)

projects (baseline + version) ─────────────────────────────────────────────────
  ├─ version_of / baseline_id → projects (lineage)
  ├─ project_vendors ── vendors
  ├─ project_audit_logs
  ├─ project_status_transitions (catalog, no FK)
  └─ milestones
        ├─ milestone_dependencies (M-N self, propagates baseline → versions)
        ├─ milestone_vendors ── vendors
        └─ activities
              ├─ activity_dependencies (M-N self)
              ├─ activity_resources → resource_types
              └─ tasks (version-only)
                    ├─ task_dependencies
                    ├─ task_resources
                    └─ subtasks (version-only; nested via parent_subtask_id)
                          ├─ subtask_dependencies
                          └─ subtask_resources

meetings → projects
  ├─ meeting_participants → users
  └─ meeting_agenda_items → work_packages (optional)

divisions, resource_types, project_status_transitions ── catalog tables
work_package_types, work_packages ── reserved
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
| 24 | Add `subtasks.parent_subtask_id`; replace single position-uniqueness index with two partial-unique indexes (top-level vs nested); relax `start_date` future check on projects (no schema change, validator only); remove dependency hierarchy rules at task/subtask level (no schema change, service-layer only) |
| 25 | Add `vendors.vendor_code` + `users.user_code` (human-readable display IDs `VN-XXXX-YYMMDDHHMMSS` / `US-XXXX-YYMMDDHHMMSS`). Lookup endpoints accept either UUID/int OR the new code; cross-entity vendor-id inputs (user create, project create, milestone create) accept either form. Backfill is deterministic from `(name|login, created_at)` |
| 26 | **Flip `users.id` from `INTEGER` to `VARCHAR(36)` UUID.** Every FK column referencing `users.id` (~30 across the schema, including the self-FK `users.deleted_by` and composite-PK columns on `user_roles` / `user_permissions`) is retyped to `String(36)` in the same migration. JWT `user_id` claim now carries a UUID string — tokens minted before the migration become invalid (users re-log in once). Other integer-PK tables (meetings, work_packages, project_members, roles, divisions, …) intentionally left as `INTEGER` |
