# PMIS API — Flow Map & Validations Reference

Scope: Users, Projects, Vendors, Resource Types, Milestones, Activities, Tasks, Subtasks, Project Tree.
Excluded: project_members, roles, work_packages, work_package_types, meetings.

---

## 1. Request lifecycle

Every request — except `POST /users/login` and `POST /users/introspect` — traverses the same pipeline. Understanding these layers up front makes each per-endpoint section below short:

```
     ┌────────────────────────────────────────────────┐
     │ FastAPI TestClient / HTTP client               │
     └────────────────────────────────────────────────┘
                        │
                        ▼
     ┌────────────────────────────────────────────────┐
     │ middleware/logging.py                          │
     │   stamps request_id, logs method+path          │
     └────────────────────────────────────────────────┘
                        │
                        ▼
     ┌────────────────────────────────────────────────┐
     │ middleware/auth.py                             │
     │   parses Authorization: Bearer <jwt>           │
     │   populates request.state.user                 │
     │   public endpoints bypass: login, introspect   │
     └────────────────────────────────────────────────┘
                        │
                        ▼
     ┌────────────────────────────────────────────────┐
     │ middleware/rbac.py — require_permission(PERM)  │
     │   401 if no user                               │
     │   403 if user lacks the permission             │
     └────────────────────────────────────────────────┘
                        │
                        ▼
     ┌────────────────────────────────────────────────┐
     │ Pydantic schema validation                     │
     │   body/query/path parsed + coerced             │
     │   schema-level validators fire                 │
     │   422 on any failure                           │
     └────────────────────────────────────────────────┘
                        │
                        ▼
     ┌────────────────────────────────────────────────┐
     │ Route handler → Controller                     │
     │   resolves path params, injects current_user   │
     └────────────────────────────────────────────────┘
                        │
                        ▼
     ┌────────────────────────────────────────────────┐
     │ Service layer                                  │
     │   project_lock guards                          │
     │   state-machine checks (transitions.py)        │
     │   cross-field + date rules (date_rules.py)     │
     │   catalog/referential checks                   │
     │   owns the transaction boundary                │
     └────────────────────────────────────────────────┘
                        │
                        ▼
     ┌────────────────────────────────────────────────┐
     │ Repository layer                               │
     │   flush-only; no commit (except upsert_by_id)  │
     └────────────────────────────────────────────────┘
                        │
                        ▼
     ┌────────────────────────────────────────────────┐
     │ Cascades (when applicable)                     │
     │   soft-delete cascade (cascade.py)             │
     │   baseline → active-version propagation        │
     │     (baseline_version_sync.py)                 │
     │   audit rows (project_audit_logs)              │
     └────────────────────────────────────────────────┘
                        │
                        ▼
     ┌────────────────────────────────────────────────┐
     │ Response formatter (HAL+JSON envelope)         │
     │   data: {...}, error: null, message: null      │
     │   camelCase field names                        │
     └────────────────────────────────────────────────┘
```

**Error envelope.** Failures from service layer return `{ "data": null, "error": { "errorIdentifier": "...", "message": "...", "_embedded": {...} }, "status": NNN }`. Pydantic validation failures return FastAPI's default `{ "detail": [...] }` shape (422).

---

## 2. Cross-cutting rules

These rules apply across multiple endpoint groups; they are referenced by name below rather than repeated.

### 2.1 Level-write guards — [`app/core/project_lock.py`](app/core/project_lock.py)

| Guard | Allows | Raises when violated |
|---|---|---|
| `assert_project_editable` | Any live (non-deleted) project | `NotFoundError` (404) |
| `assert_milestone_activity_writable` | Live **baseline** only | `AuthorizationError` (403) on versions; `NotFoundError` (404) on deleted/missing |
| `assert_task_subtask_writable` | Live **version** only | `AuthorizationError` (403) on baselines |

Used to enforce the rule: **M/A writes on baselines only, T/S writes on versions only, project-level writes on either.**

### 2.2 Date rules — [`app/shared/date_rules.py`](app/shared/date_rules.py)

`validate_entity_dates` is the shared hierarchical floor check called by M/A/T/S create and update:

- `entity.start_date >= parent.start_date` (project floor for milestones; milestone floor for activities; activity floor for tasks; task floor for subtasks)
- `entity.end_date >= entity.start_date`
- `actual_start_date >= project.start_date` when present
- `actual_end_date >= actual_start_date OR project.start_date` when present

`validate_resource_dates` for `activity_resources` / `task_resources` / `subtask_resources`:
- `onboard_date >= project.start_date`
- `offboard_date >= onboard_date`
- `actual_onboard / actual_offboard` follow same floors

Schema-level validation (Pydantic) also enforces `end_date >= start_date` without DB lookup so basic shape errors fail at 422 before the service runs.

### 2.3 Project state machine — [`app/api/v3/projects/services/transitions.py`](app/api/v3/projects/services/transitions.py)

Statuses: `new`, `draft`, `published`, `closed`, `suspended`.

Legal edges (subset rules apply):
- `new ↔ draft` — `new→draft` triggered by the `Save Project` endpoint; `draft→new` allowed by admin
- `new → published`, `draft → published` — **admin only**
- `new → closed`, `draft → closed`, `published → closed` — **admin only**
- `new → suspended`, `draft → suspended`, `published → suspended` — **version only**

**Editable-fields whitelist** per state:
- Unpublished baseline: `name`, `description`, `owner`, `start_date`, `end_date`, `public`, `active`, `status_explanation`
- Published baseline: same as unpublished (post-Doc-12 change)
- Version (any status): `owner`, `public`, `actual_end_date`, `status_explanation`

Requests that include fields outside the whitelist return 422 `invalid_field` with the `rejected` list in `_embedded.details`.

### 2.4 Baseline → active-version propagation — [`app/api/v3/projects/services/baseline_version_sync.py`](app/api/v3/projects/services/baseline_version_sync.py)

After a baseline M/A write commits, the service calls `propagate_*`. Rules:

- Targets only **active versions**: `is_version=True AND deleted_at IS NULL AND status NOT IN ('suspended','closed')`.
- Milestones: `cloned_from_id` lineage → locate version twins.
- Activities: resolve version's parent milestone first (via M's lineage), then attach.
- Fields cascaded: `name`, `description`, `start_date`, `end_date`, `position` (milestones); plus `type`, `resource_mode`, `resource_count` (activities).
- Fields **not** cascaded: `status`, `depends`, `dependency` (version-local progress tracking).
- Each version affected gets an audit row `*.cascade_from_baseline` with `cloned_from_baseline_*_id` in the payload.

### 2.5 Soft-delete cascades

Every cascade path is a soft-delete: stamps `deleted_at` (+ `deleted_by` where the column exists) and never physically removes rows. Reads filter `deleted_at IS NULL` everywhere.

- Project delete → every M/A/T/S + resource row under it (`milestones/services/cascade.py::cascade_soft_delete_project`).
- Baseline delete → additionally soft-deletes every live version (recursively cascading each).
- Milestone delete → descendants A/T/S + their resources, **plus every A/T/S dependency edge touching the subtree (as source or target) is soft-deleted** via `DependencyRepository.cascade_remove_for_deleted_milestone_subtree`.
- Activity delete → descendants T/S + their resources, **plus every activity/task/subtask dependency edge touching the subtree is soft-deleted** via `cascade_remove_for_deleted_activity_subtree`.
- Task delete → descendant subtasks + their resources, **plus every task/subtask dependency edge touching the subtree is soft-deleted** via `cascade_remove_for_deleted_task_subtree`.
- Subtask delete → only its resource (leaf of tree), **plus every subtask dependency edge where this subtask is source or target is soft-deleted** via `cascade_remove_subtask_targets`.

Dependency edges in `activity_dependencies` / `task_dependencies` / `subtask_dependencies` carry their own `deleted_at` / `deleted_by` columns and a surrogate UUID `id` PK so history is preserved. A partial unique index on `(source, target) WHERE deleted_at IS NULL` enforces one live edge per pair while allowing any number of dead rows to coexist for audit.

### 2.6 Dependency system (activities / tasks / subtasks)

Three association tables — [`activity_dependencies`](app/infrastructure/db/models/activity_dependency.py), [`task_dependencies`](app/infrastructure/db/models/task_dependency.py), [`subtask_dependencies`](app/infrastructure/db/models/subtask_dependency.py) — model `source → target` edges. Each table has:

- Surrogate UUID `id` primary key (so history rows for the same pair can coexist).
- `source_*_id`, `target_*_id`, denormalized `project_id` (all FK).
- `created_at`, `deleted_at`, `deleted_by` — full soft-delete lifecycle.
- Partial unique index on `(source, target) WHERE deleted_at IS NULL` — enforces at-most-one live edge per ordered pair, any number of dead rows allowed.

**Replaces the old activity JSON `dependency` column.** (Milestone `depends` is still a plain JSON pass-through — dependency graphs on milestones are not enforced.)

All writes go through [`DependencyRepository`](app/infrastructure/db/repositories/dependency_repository.py). Every removal is a **soft-delete**: stamps `deleted_at` / `deleted_by` on the live row. Re-adding a previously-removed edge inserts a fresh row (new `id`) rather than clearing the old one's `deleted_at`, so the audit trail is preserved. The partial unique index allows the two rows (one dead, one live) to coexist for the same pair. Reads always filter `deleted_at IS NULL`.

The API surfaces dependencies through a `dependsOn` field (alias of `depends_on` in the schemas):
- `None` (omitted) → leave the list unchanged
- `[]` → clear all edges (soft-deletes every live one)
- `[...]` → replace the list — targets missing from the new list are soft-deleted; targets new to the list get fresh rows; unchanged targets keep their existing live row

**Validation rules (service layer):**

| Rule | Enforcement |
|---|---|
| Self-edge | 422 `"An activity/task/subtask cannot depend on itself."` — checked on update only (create has no id yet). |
| Target exists and is live | 422 `"Unknown or out-of-project ... dependency target(s): …"` |
| Target belongs to the same project | same 422 — verified via `existing_target_*_ids` scoped to the project |
| No cycle | 422 `"Adding dependency on 'X' would create a cycle."` — DFS against **live edges only** in `would_create_cycle_*` |
| Task hierarchy | 422 `"Cannot add task dependency on task 'X': the source's parent activity does not depend on that task's parent activity. Add the activity-level dependency first."` Tasks in the same activity are always free to reference each other. The hierarchy check reads live activity edges only. |
| Subtask hierarchy | 422 `"Cannot add subtask dependency on subtask 'X': the source's parent task does not depend on that subtask's parent task. Add the task-level dependency first."` Same-task references are always allowed. |

**Status-completion gate (activities only).** Because activities carry a `status` field, flipping it to `completed` is blocked when any dependency target is not yet `completed`. The gate fires on update only (create doesn't expose completed-from-zero as a user flow — the default is `not_completed`). Returns 403 with `"Cannot mark this activity as completed — the following dependency target(s) are not yet completed: 'A', 'B' (+N more)."`. When the patch also replaces `dependsOn`, the gate evaluates the **new** (live-only) target set.

**Version clone.** When `/projects/{u}/versions/create` clones the M/A/T/S tree, `DependencyRepository.clone_activity_dependencies_for_version` (+task/subtask variants) copies only the baseline's **live** edges, with both source and target ids rewritten to the version's new ids. Historical (soft-deleted) baseline edges are not carried forward. Dep edges are **version-local** — each version's graph evolves independently after the clone.

**Cascade cleanup.** See Section 2.5 — every M/A/T/S soft-delete soft-deletes the dep edges in the subtree through the dedicated repository methods (`cascade_remove_for_deleted_*_subtree`). Source and target directions are both covered so no dead edges dangle after the parent is gone.

---

## 3. Endpoint catalog

### 3.1 Users — [`app/api/v3/users/routes.py`](app/api/v3/users/routes.py)

| Endpoint | Auth | Permission | Body schema | Notes |
|---|---|---|---|---|
| `POST /users/introspect` | public | — | `IntrospectRequest` | Token introspection. Returns validity + user claims. |
| `POST /users/login` | public | — | `LoginRequest` | Argon2 password check. Returns JWT access token + refresh token. Inactive users rejected. |
| `GET /users/me` | JWT | `require_authenticated` | — | Current user. |
| `POST /users/create` | JWT | `USERS_CREATE` (admin) | `UserCreateRequest` | login 3-50 chars, email valid, password min 8; login + email must be unique. |
| `GET /users` | JWT | `USERS_READ_ALL` (admin) | — | `offset≥1`, `pageSize∈[1,100]`, optional `status`. |
| `GET /users/{user_id}` | JWT | `USERS_READ` | — | Members can read themselves + active users; admins read all. |
| `PATCH /users/{user_id}` | JWT | `USERS_UPDATE` | `UserUpdateRequest` | Members can't change `admin` or `status`; admins can. |
| `PATCH /users/{user_id}/password` | JWT | `USERS_UPDATE` | `UserPasswordUpdateRequest` | password min 8. Self-service or admin-for-any. |
| `DELETE /users/{user_id}` | JWT | `USERS_DELETE_ALL` (admin) | — | Hard delete. |

### 3.2 Projects — [`app/api/v3/projects/routes.py`](app/api/v3/projects/routes.py)

| Endpoint | Auth | Permission | Body | Notes |
|---|---|---|---|---|
| `POST /projects/create` | JWT | `PROJECTS_CREATE` | `ProjectCreateRequest` | See schema validations below. Server mints `id` (UUID) + `projectCode` (`UIDAI-PR<yymmddhhmmss-IST>`). |
| `PUT /projects/{uuid}` | JWT | `PROJECTS_CREATE` | `ProjectUpsertRequest` | Idempotent by uuid. 201 on insert, 200 on update. On update: ownership check. Commits internally (unlike other writes). |
| `GET /projects` | JWT | `PROJECTS_READ` | — | `offset≥1`, `pageSize∈[1,100]`, optional `active`/`public` bool filters. |
| `GET /projects/{uuid}` | JWT | `PROJECTS_READ` | — | 404 if soft-deleted. |
| `PATCH /projects/{uuid}` | JWT | `PROJECTS_UPDATE` | `ProjectUpdateRequest` | `assert_project_editable` + `editable_fields_for(project)` whitelist per state. Dates must be in future (schema). `vendorIds: []` clears list; omit to leave alone. |
| `DELETE /projects/{uuid}` | JWT | `PROJECTS_DELETE_ALL` | — | Soft-delete + cascade to M/A/T/S. If baseline: also soft-delete every live version. |
| `POST /projects/{uuid}/save` | JWT | `PROJECTS_UPDATE` | — | `new → draft` iff ≥ 1 live milestone. 422 on zero milestones. Idempotent past `draft`. |
| `POST /projects/{uuid}/publish` | JWT | `PROJECTS_PUBLISH` (admin) | — | Transition `{new,draft} → published`. 409 if already published. Locks out PATCH of non-whitelisted fields but published baselines remain editable on the whitelisted set. |
| `POST /projects/{uuid}/close` | JWT | `PROJECTS_CLOSE` (admin) | `ProjectCloseRequest` (optional) | Transition `{new,draft,published} → closed`. `reason` ≤ 5000 chars. |
| `POST /projects/{uuid}/suspend` | JWT | `PROJECTS_UPDATE` | — | **Version only** (state-machine guard). |
| `POST /projects/{uuid}/versions/create` | JWT | `PROJECTS_CREATE` | — | Source must be `is_version=False AND status='published'`. Only **one active version per baseline**; returns 409 if one already exists. Enforced by partial unique index `ux_projects_active_version_per_baseline` + service check. Cloned tree stamps `cloned_from_id` on every M/A. |

**`ProjectCreateRequest` validations** (schema-level):
- `name` 1-255 chars
- `description` ≤ 5000 chars
- `startDate` / `endDate` must be in the future; `endDate > startDate`
- `status` ∈ `{new, draft, published, closed, suspended}` (default `new`)
- `category` ∈ `{MSAP, MSIP, BSP, others}` if supplied
- `categoryOther` required (non-empty ≤ 255 chars) **iff** `category='others'`; rejected otherwise
- `categoryOtherReason` required (non-empty ≤ 1000 chars) **iff** `category='others'`; rejected otherwise (added in doc 15 — captures *why* "others" was chosen)
- `vendorIds` list of UUID strings

**Service-layer additions on create:**
- Every vendor id must exist and be `active=True`.
- `status` is verified against the `project_status_transitions` catalog (see §3.3a). Returns `invalid_status` on a typo.
- `owner` must reference an existing user login **and** be in the `project_owners` whitelist (when the whitelist is populated).

### 3.3 Project tree — [`app/api/v3/tree/routes.py`](app/api/v3/tree/routes.py)

| Endpoint | Auth | Permission | Notes |
|---|---|---|---|
| `GET /projects/{uuid}/tree` | JWT | `PROJECTS_READ` | Nested M → A → T → S with resource blocks inlined on resource-type rows. Every A/T/S node carries a `dependsOn` list of target ids (pre-fetched in three bulk queries; no N+1). `includeDeleted=true` admin-practice; default filters soft-deleted. |

### 3.3a Catalogs — project_status_transitions + project_owners (added in doc 15)

| Endpoint | Auth | Permission | Body | Notes |
|---|---|---|---|---|
| `GET /project_status_transitions` | JWT | authenticated | — | Lists every active `(from_status, to_status)` edge from the `project_status_transitions` table. Includes the seed row `from_status=NULL, to_status=new` marking the initial status. Each row has `requiresAdmin` and `versionOnly` flags so the FE can build a context-aware next-step dropdown. |
| `GET /project_owners` | JWT | authenticated | — | Lists active rows from the `project_owners` whitelist with backing `userId`, `login`, `email`, names, optional `displayName`. |
| `POST /project_owners/create` | JWT | `PROJECTS_CREATE` (admin) | `{ userId? \| login?, displayName? }` | Adds a user to the owner whitelist. 404 if the user doesn't exist. Idempotent: re-adding an existing row reactivates it (sets `active=True`). |
| `DELETE /project_owners/{user_id}` | JWT | `PROJECTS_CREATE` (admin) | — | Soft-deactivates the row (`active=False`); never hard-deletes — keeps the FK chain to historical projects intact. |

**Validator wiring.** The create-project service now consults both catalogs:
- `status` is checked against `ProjectStatusTransitionRepository.known_to_statuses()`. Returns `error_type="invalid_status"` on a value not in the catalog. Falls back to the in-code `PROJECT_STATUS_CHOICES` set when the catalog is empty (covers fresh in-memory test DBs).
- `owner` is checked against `ProjectOwnerRepository.is_login_an_active_owner()`. Rejected as `validation_error` with a "not in the project_owners whitelist" message if the catalog has any rows but the owner isn't in it. Skipped silently when the catalog is empty.

### 3.4 Vendors — [`app/api/v3/vendors/routes.py`](app/api/v3/vendors/routes.py)

| Endpoint | Auth | Permission | Body | Notes |
|---|---|---|---|---|
| `GET /vendors` | JWT | `VENDORS_READ` | — | Lists active vendors. No pagination (small catalog). |
| `POST /vendors/create` | JWT | `VENDORS_MANAGE` (admin) | `VendorCreateRequest` | `name` unique; description ≤ 5000; `active` default true. `AlreadyExistsError → 409` on duplicate. |
| `PATCH /vendors/{id}` | JWT | `VENDORS_MANAGE` (admin) | `VendorUpdateRequest` | All fields optional. |

### 3.5 Resource types — [`app/api/v3/resource_types/routes.py`](app/api/v3/resource_types/routes.py)

| Endpoint | Auth | Permission | Body | Notes |
|---|---|---|---|---|
| `GET /resource_types` | JWT | `RESOURCE_TYPES_READ` | — | Lists active types. |
| `POST /resource_types/create` | JWT | `RESOURCE_TYPES_MANAGE` (admin) | `ResourceTypeCreateRequest` | `code` unique case-insensitive, 1-50 chars; `name` 1-255. |

### 3.6 Milestones — [`app/api/v3/milestones/routes.py`](app/api/v3/milestones/routes.py)

| Endpoint | Auth | Permission | Body | Guards |
|---|---|---|---|---|
| `POST /projects/{uuid}/milestones/create` | JWT | `MILESTONES_CREATE` | `MilestoneCreateRequest` | `assert_milestone_activity_writable` (baseline only). |
| `GET /projects/{uuid}/milestones` | JWT | `MILESTONES_READ` | — | Paginated list. |
| `GET /milestones/{id}` | JWT | `MILESTONES_READ` | — | Single read. |
| `PATCH /milestones/{id}` | JWT | `MILESTONES_UPDATE` | `MilestoneUpdateRequest` | `assert_milestone_activity_writable` + propagation cascade. |
| `DELETE /milestones/{id}` | JWT | `MILESTONES_DELETE` | — | `assert_milestone_activity_writable` + subtree cascade + version cascade. |
| `POST /milestones/{id}/restore` | JWT | `MILESTONES_RESTORE` (admin) | — | `assert_project_editable` (permissive — no baseline/version rule). |

**Schema validations:** `name` 1-255, `startDate < endDate`, `status ∈ MILESTONE_STATUS_CHOICES` (`not_completed`, `completed`), `depends` list (pass-through), `vendors` list (renamed from `vendorIds` in doc 15; the legacy `vendorIds` and `vendor_ids` aliases are still accepted on the input side via Pydantic `AliasChoices`).

**Service validations:**
- `start_date ≥ project.start_date`
- `end_date ≥ start_date`
- Parent project must have `start_date` set
- `vendorIds` must be a **subset** of the project's vendor list (each vendor must also exist + be active).

**Cascade:** create / update / delete each propagate to active-version twins with their own audit entries.

### 3.7 Activities — [`app/api/v3/activities/routes.py`](app/api/v3/activities/routes.py)

| Endpoint | Auth | Permission | Body | Guards |
|---|---|---|---|---|
| `POST /milestones/{id}/activities/create` | JWT | `ACTIVITIES_CREATE` | `ActivityCreateRequest` | `assert_milestone_activity_writable`. |
| `GET /milestones/{id}/activities` | JWT | `ACTIVITIES_READ` | — | Paginated. |
| `GET /activities/{id}` | JWT | `ACTIVITIES_READ` | — | Resource block inlined. |
| `PATCH /activities/{id}` | JWT | `ACTIVITIES_UPDATE` | `ActivityUpdateRequest` | `assert_milestone_activity_writable`. Handles full type transition matrix. |
| `DELETE /activities/{id}` | JWT | `ACTIVITIES_DELETE` | — | Cascade to T/S + resources. |
| `POST /activities/{id}/restore` | JWT | `ACTIVITIES_RESTORE` (admin) | — | `assert_project_editable`. |

**Type/mode matrix (schema + service):**
- `type ∈ {standard, resource, transactional}`
- `standard`: `status` default `not_completed`. Flipping to `completed` is blocked by the dependency completion gate (see §2.6).
- `resource, mode=count`: `resourceCount ≥ 1`, no inline `resource` block.
- `resource, mode=details`: inline `resource` block required with `resourceName`, plus `typeOfResourceId` (must be active in catalog) and `division` (∈ `tmd1, tmd2, others`). `divisionOther` required iff `division='others'`.
- `transactional`: no `status`, no `resourceMode`, no `resource`, no `resourceCount`.

**`dependsOn`** is cross-type (applies to any activity type). Validated per §2.6: live targets in the same project, no self-edge, no cycles. On update, `None` = no change, `[]` = clear, `[...]` = replace. The relational `activity_dependencies` edges replace the old JSON `dependency` column.

**Date service validations (`validate_entity_dates`):**
- `start_date ≥ milestone.start_date`; `end_date ≥ start_date`
- `actual_start_date ≥ project.start_date` if present
- `actual_end_date ≥ actual_start_date OR project.start_date` if present
- Resource dates: `onboard/offboard` floors at `project.start_date`

**Update type-transition behavior:** Flipping `type` from standard to non-standard clears `status`. `dependsOn` edges persist across type flips — nothing type-specific about a dependency edge. Flipping mode from `count` to `details` requires a resource block. Flipping from resource to non-resource soft-deletes any live resource row.

**Cascade:** create/update/delete propagate to version twins. Shape columns only (`name`, `description`, `type`, dates, `position`, `resource_mode`, `resource_count`); `status` and `dependsOn` edges are version-local. Dep edges on the baseline side are never retroactively copied to versions — they're cloned once at version creation time, then each side evolves independently.

### 3.8 Tasks — [`app/api/v3/tasks/routes.py`](app/api/v3/tasks/routes.py)

| Endpoint | Auth | Permission | Body | Guards |
|---|---|---|---|---|
| `POST /activities/{id}/tasks/create` | JWT | `TASKS_CREATE` | `TaskCreateRequest` | `assert_task_subtask_writable` (version only). |
| `GET /activities/{id}/tasks` | JWT | `TASKS_READ` | — | Paginated. |
| `GET /tasks/{id}` | JWT | `TASKS_READ` | — | |
| `PATCH /tasks/{id}` | JWT | `TASKS_UPDATE` | `TaskUpdateRequest` | `assert_task_subtask_writable`. |
| `DELETE /tasks/{id}` | JWT | `TASKS_DELETE` | — | Cascade to subtasks + resources. |
| `POST /tasks/{id}/restore` | JWT | `TASKS_RESTORE` (admin) | — | `assert_project_editable`. |

**Shape rules:** same `type / resourceMode / resource` matrix as activities, **minus** `status` (tasks don't carry that). Date floor is `activity.start_date`. `dependsOn` is available on tasks with the extra **hierarchy rule**: the source's parent activity must already depend on the target's parent activity (per `activity_dependencies`), unless both tasks live under the same activity (which is always allowed). See §2.6.

**Type field removed from create body (doc 15).** `TaskCreateRequest` no longer accepts a `type` field — the service derives the type from the parent activity (`activity.type`). The resource-mode shape (`resourceMode` / `resourceCount` / `resource`) is still validated against the inherited type: a task under a non-resource activity must omit them; a task under a resource activity must include `resourceMode` and the matching count/details body. The `type` column on the model is preserved, and `PATCH /tasks/{id}` still accepts an explicit `type` so a future cross-type-mapping endpoint can override the inheritance.

**Tasks do NOT propagate** — they live only in versions. Task dependency edges live on the version alongside them.

### 3.9 Subtasks — [`app/api/v3/subtasks/routes.py`](app/api/v3/subtasks/routes.py)

| Endpoint | Auth | Permission | Body | Guards |
|---|---|---|---|---|
| `POST /tasks/{id}/subtasks/create` | JWT | `SUBTASKS_CREATE` | `SubtaskCreateRequest` | `assert_task_subtask_writable`. |
| `GET /tasks/{id}/subtasks` | JWT | `SUBTASKS_READ` | — | Paginated. |
| `GET /subtasks/{id}` | JWT | `SUBTASKS_READ` | — | |
| `PATCH /subtasks/{id}` | JWT | `SUBTASKS_UPDATE` | `SubtaskUpdateRequest` | `assert_task_subtask_writable`. |
| `DELETE /subtasks/{id}` | JWT | `SUBTASKS_DELETE` | — | No subtree (leaf) — only resource row cascades. |
| `POST /subtasks/{id}/restore` | JWT | `SUBTASKS_RESTORE` (admin) | — | `assert_project_editable`. |

**Shape rules:** same `type / resourceMode / resource` matrix. Date floor is `task.start_date`. Classification columns (`typeOfResourceId`, `division`, `divisionOther`) currently scoped to **activity** resources only; subtask resources accept the base `ResourcePayload` shape without classification. `dependsOn` mirrors task behavior one level down: source's parent task must depend on target's parent task, unless both subtasks live under the same task. See §2.6.

**Type field removed from create body (doc 15).** Same change as tasks — the subtask create body no longer accepts `type`; the service derives it from `task.type`. PATCH still accepts `type` for the future cross-type-mapping case.

---

## 4. Situational restriction matrix

The common questions expressed as a decision table:

| Action | Baseline `new/draft` | Baseline `published` | Baseline `closed` | Version `new/draft/published` | Version `suspended` | Soft-deleted any |
|---|---|---|---|---|---|---|
| `PATCH /projects/{uuid}` | ✅ full whitelist | ✅ full whitelist (cascades nothing; project-level edits stay scoped) | ✅ full whitelist | ✅ version whitelist | ✅ version whitelist | ❌ 404 |
| `POST /projects/{uuid}/save` | ✅ if ≥ 1 milestone | ✅ no-op | ❌ (no transition) | ❌ | ❌ | ❌ 404 |
| `POST /projects/{uuid}/publish` | ✅ admin | ❌ 409 already published | ❌ 400 illegal | ✅ admin | ❌ | ❌ 404 |
| `POST /projects/{uuid}/close` | ✅ admin | ✅ admin | ❌ | ✅ admin | ❌ | ❌ 404 |
| `POST /projects/{uuid}/suspend` | ❌ 400 version-only | ❌ 400 | ❌ | ✅ | ❌ already suspended | ❌ 404 |
| `POST /projects/{uuid}/versions/create` | ❌ 409 (not published) | ✅ iff no active version exists; 409 otherwise | ❌ 409 | ❌ 409 | ❌ 409 | ❌ 404 |
| `DELETE /projects/{uuid}` | ✅ admin — cascades M/A/T/S + active versions | ✅ admin | ✅ admin | ✅ admin — version-only | ✅ admin | ❌ 404 |
| Milestone / Activity write | ✅ | ✅ (propagates to versions) | ✅ (propagates) | ❌ 403 | ❌ 403 | ❌ 404 |
| Task / Subtask write | ❌ 403 | ❌ 403 | ❌ 403 | ✅ | ❌ 403 (project-lock still fires) | ❌ 404 |
| Milestone / Activity restore | ✅ admin | ✅ admin | ✅ admin | ✅ admin | ✅ admin | ✅ admin (only way in) |

Notes:
- "Propagates to versions" fires only for **active** versions (`is_version=True AND status NOT IN ('suspended','closed') AND deleted_at IS NULL`).
- The "one active version per baseline" invariant is enforced at both the service layer and the database (partial unique index). A new version can be minted once the previous one is suspended, closed, or deleted.
- Schemas still run Pydantic validation before any of the above, so shape errors (missing required fields, out-of-range values, bad enum) fail at 422 without reaching the service layer.
