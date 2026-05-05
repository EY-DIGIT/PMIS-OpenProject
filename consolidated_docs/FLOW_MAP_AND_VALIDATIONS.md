# PMIS API — Flow Map & Validations Reference

Scope: Users (incl. RBAC user-side), Projects (incl. versions, audit, baseline-version sync), Master data (`/api/v3/master/*` — divisions, project_status_transitions, resource_types, vendors, roles, permissions), Milestones (incl. dep edges), Activities, Tasks, Subtasks (incl. nested), Project Tree.
Excluded: project_members, work_packages, work_package_types, meetings, comments, attachments. (See [ARCHITECTURE_AND_API_REFERENCE.md](./ARCHITECTURE_AND_API_REFERENCE.md) for the complete endpoint catalog.)

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
     │ middleware/auth.py  (DB-driven RBAC, doc 21B)  │
     │   parses Authorization: Bearer <jwt>           │
     │   sets request.state:                          │
     │     user_id, user_login, token_jti, token_exp  │
     │     user_permissions: Set[str]  ← 1 DB query   │
     │     is_admin: bool  ← admin-role membership    │
     │   public endpoints bypass: login, introspect   │
     └────────────────────────────────────────────────┘
                        │
                        ▼
     ┌────────────────────────────────────────────────┐
     │ middleware/rbac.py                             │
     │   require_permission("module:action") (string) │
     │   401 if no user_id                            │
     │   403 if code not in user_permissions          │
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
| `assert_milestone_activity_writable` | Live project (any) | `NotFoundError` (404) on deleted/missing |
| `assert_task_subtask_writable` | Live project (any) | `NotFoundError` (404) on deleted/missing |

> **Doc 33 change 1**: the baseline/version split was removed. The two writability helpers no longer enforce a baseline-only or version-only rule — every M/A/T/S write succeeds on any live project (subject to RBAC + state-machine + dep-rule guards). The helpers are retained for the deleted-project 404 check.

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

Statuses (post-doc-33 change 1): `new`, `draft`, `published`, `closed`. The `suspended` status was removed along with versioning.

Legal edges (subset rules apply):
- `new ↔ draft` — `new→draft` triggered by the `Save Project` endpoint; `draft→new` allowed by admin
- `new → published`, `draft → published` — **admin only**
- `new → closed`, `draft → closed`, `published → closed` — **admin only**

**Editable-fields whitelist** per state:
- Unpublished project: `name`, `description`, `owner`, `start_date`, `end_date`, `public`, `active`, `status_explanation`
- Published project: same as unpublished (post-Doc-12 change)

> **Doc 33 change 1**: the "version" project type is gone, so the version-only editable list and the version-only suspended transition were removed. There is one project type now.

> Doc 24 part 1: `start_date` is no longer required to be in the future.
> Only `end_date` carries the future-only Pydantic check; `start_date`
> may be in the past so a project that's already in progress can be
> entered post-hoc.

Requests that include fields outside the whitelist return 422 `invalid_field` with the `rejected` list in `_embedded.details`.

**Doc 30 publish gate.** Before flipping status to `published`, the publish service runs two structural-completeness checks (in [`app/api/v3/projects/services/publish.py`](app/api/v3/projects/services/publish.py)):

1. **Zero-milestones** — if the project has no live milestones, returns 422 `invalid_publish` with `_embedded.details.errorIdentifier = "no_milestones"`.
2. **Empty milestone(s)** — if any live milestone has zero live activities, returns 422 `invalid_publish` with `_embedded.details.errorIdentifier = "milestone_without_activity"` plus `details.milestoneIds` and `details.milestoneNames` (full lists, not capped) so the FE can highlight every offender.

Both gates apply uniformly to baselines and versions (the helper queries by `project_id`, which is the version's own id when publishing a version). The save-to-draft path enforces the ≥1-milestone rule independently; the publish gate is the belt-and-braces version that also catches post-draft deletions.

### 2.4 Baseline → active-version propagation — REMOVED (doc 33 change 1)

The entire `baseline_version_sync` module + propagation flow was deleted along with the versioning feature. Projects now own their M/A/T/S directly; there is no twin to propagate to.

Audit-row generation moved into the per-entity write services. The `actor_role` column was added to `project_audit_logs` (doc 33 change 1) capturing the role bucket (`admin` / `member` / `vendor` / `viewer`) the actor occupied at write time.

### 2.5 Soft-delete cascades

Every cascade path is a soft-delete: stamps `deleted_at` (+ `deleted_by` where the column exists) and never physically removes rows. Reads filter `deleted_at IS NULL` everywhere.

- Project delete → every M/A/T/S + resource row under it (`milestones/services/cascade.py::cascade_soft_delete_project`). **Doc 33 change 1**: there's no longer a separate "baseline delete also wipes live versions" step — versioning was removed, so a project delete is one cascade.
- Milestone delete → descendants A/T/S + their resources, **plus every milestone/A/T/S dependency edge touching the subtree (as source or target) is soft-deleted** via `cascade_remove_for_deleted_milestone_subtree` (doc 21A added milestone-level edge wipe alongside the existing A/T/S sweep).
- Activity delete → descendants T/S + their resources, **plus every activity/task/subtask dependency edge touching the subtree is soft-deleted** via `cascade_remove_for_deleted_activity_subtree`.
- Task delete → descendant subtasks + their resources, **plus every task/subtask dependency edge touching the subtree is soft-deleted** via `cascade_remove_for_deleted_task_subtree`.
- Subtask delete → **doc 24: now BFS over `parent_subtask_id` and soft-deletes the entire descendant subtree of subtasks** (top-level subtask delete cascades to all nested children; nested subtask delete cascades to its own descendants). Resource rows under each soft-deleted subtask are wiped, and `cascade_remove_subtask_targets` is called per descendant id so every dependency edge touching any deleted subtask is soft-deleted.

Dependency edges in `activity_dependencies` / `task_dependencies` / `subtask_dependencies` carry their own `deleted_at` / `deleted_by` columns and a surrogate UUID `id` PK so history is preserved. A partial unique index on `(source, target) WHERE deleted_at IS NULL` enforces one live edge per pair while allowing any number of dead rows to coexist for audit.

### 2.5b Authentication state machines (doc 33 change 3)

**2FA login state machine** — three calls, anchored on the ephemeral session token.

```
   ┌──────────────────────────────────────────────────┐
   │  POST /users/login {login, password}             │
   │  ↓ password OK + 2FA required                    │
   │  ↓ server:                                       │
   │     - mints ephemeral_token (random)             │
   │     - inserts sentinel otp_codes row keyed by    │
   │       ephemeral_token_hash (links token→user)    │
   │  ↓ returns {requires_otp:true, ephemeral_token,  │
   │             channels_available, message}         │
   └──────────────────────────────────────────────────┘
                       │
                       ▼
   ┌──────────────────────────────────────────────────┐
   │  POST /users/login/send-otp                      │
   │      {ephemeral_token, channel}                  │
   │  ↓ resolve user by ephemeral_token_hash          │
   │  ↓ enforce OTP_RESEND_COOLDOWN_SECONDS (429)     │
   │  ↓ generate code, hash with HMAC-SHA256(pepper)  │
   │  ↓ insert otp_codes row + notification_log row   │
   │  ↓ dispatch via Mock | Http NotificationClient   │
   │  ↓ returns {message, code?} (code only in mock)  │
   └──────────────────────────────────────────────────┘
                       │
                       ▼
   ┌──────────────────────────────────────────────────┐
   │  POST /users/login/verify-otp                    │
   │      {ephemeral_token, code}                     │
   │  ↓ resolve OTP row; check not consumed/expired   │
   │  ↓ verify code via constant-time HMAC compare    │
   │  ↓ wrong → attempt_count++; if >= OTP_MAX_       │
   │     ATTEMPTS, mark consumed and return 401       │
   │  ↓ right → mark consumed, mint JWT pair          │
   │  ↓ same shape as single-stage /login response    │
   └──────────────────────────────────────────────────┘
```

Settings: `REQUIRE_2FA` (global), `OTP_TTL_SECONDS` (default 300), `OTP_RESEND_COOLDOWN_SECONDS` (default 60), `OTP_MAX_ATTEMPTS` (default 5), `OTP_CODE_LENGTH` (default 6), `OTP_HASH_PEPPER` (falls back to `SECRET_KEY`). Per-user opt-out via `users.two_factor_enabled=false` (PATCH `/users/{id}` with `users:update`).

Service layer: [`app/api/v3/users/services/two_factor.py`](app/api/v3/users/services/two_factor.py). Tables: `otp_codes`, `notification_log`.

**Password-reset state machine** — two calls, anti-enumeration on step 1.

```
   ┌──────────────────────────────────────────────────┐
   │  POST /users/forgot-password                     │
   │      {login_or_email, channel}                   │
   │  ↓ ALWAYS returns 200 (anti-enumeration)         │
   │  ↓ if user exists:                               │
   │     - email channel: random URL-safe token       │
   │     - sms channel:   6-digit OTP                 │
   │     - hash with HMAC-SHA256(pepper)              │
   │     - insert password_reset_tokens row           │
   │     - dispatch via NotificationClient            │
   │  ↓ if user doesn't exist: skip insert, same 200  │
   └──────────────────────────────────────────────────┘
                       │
              (out-of-band: email or SMS delivery)
                       │
                       ▼
   ┌──────────────────────────────────────────────────┐
   │  POST /users/reset-password                      │
   │      {token_or_code, new_password}               │
   │  ↓ hash incoming value, lookup row by hash       │
   │  ↓ check not consumed / not expired              │
   │  ↓ update users.hashed_password (Argon2)         │
   │  ↓ mark token row consumed (single-use)          │
   │  ↓ clear refresh slots → existing sessions die   │
   │  ↓ returns {message: "Password reset successfully."}│
   └──────────────────────────────────────────────────┘
```

Settings: `PASSWORD_RESET_TTL_SECONDS` (default 3600s / 1 hour), shared `OTP_HASH_PEPPER`.

Service layer: [`app/api/v3/users/services/password_reset.py`](app/api/v3/users/services/password_reset.py). Table: `password_reset_tokens` (column `token_hash` unique).

### 2.6 Dependency system (milestones / activities / tasks / subtasks)

Four association tables — [`milestone_dependencies`](app/infrastructure/db/models/milestone_dependency.py), [`activity_dependencies`](app/infrastructure/db/models/activity_dependency.py), [`task_dependencies`](app/infrastructure/db/models/task_dependency.py), [`subtask_dependencies`](app/infrastructure/db/models/subtask_dependency.py) — model `source → target` edges. Each table has:

- Surrogate UUID `id` primary key (so history rows for the same pair can coexist).
- `source_*_id`, `target_*_id`, denormalized `project_id` (all FK).
- `created_at`, `deleted_at`, `deleted_by` — full soft-delete lifecycle.
- Partial unique index on `(source, target) WHERE deleted_at IS NULL` — enforces at-most-one live edge per ordered pair, any number of dead rows allowed.

**Doc 21A:** Milestones gained an edge table mirroring the activity/task/subtask shape. The legacy `milestones.depends` JSON column is gone (doc 22). Activities lost the old JSON `dependency` column long ago; doc 21A only added the milestone level.

All writes go through [`DependencyRepository`](app/infrastructure/db/repositories/dependency_repository.py). Every removal is a **soft-delete**: stamps `deleted_at` / `deleted_by` on the live row. Re-adding a previously-removed edge inserts a fresh row (new `id`) rather than clearing the old one's `deleted_at`, so the audit trail is preserved. The partial unique index allows the two rows (one dead, one live) to coexist for the same pair. Reads always filter `deleted_at IS NULL`.

The API surfaces dependencies through a `dependsOn` field (alias of `depends_on` in the schemas):
- `None` (omitted) → leave the list unchanged
- `[]` → clear all edges (soft-deletes every live one)
- `[...]` → replace the list — targets missing from the new list are soft-deleted; targets new to the list get fresh rows; unchanged targets keep their existing live row

**Validation rules (service layer):**

Doc 24 part 3 dropped the parent-activity hierarchy rule from tasks and the parent-task hierarchy rule from subtasks. All four levels now follow the same set of rules.

| Rule | Enforcement |
|---|---|
| Self-edge | 422 `"An <kind> cannot depend on itself."` — checked on update only (create has no id yet). |
| Target exists and is live | 422 `"Unknown or out-of-project ... dependency target(s): …"` |
| Target belongs to the same project | same 422 — verified via `existing_target_*_ids` scoped to the project |
| No cycle | 422 `"Adding dependency on 'X' would create a cycle."` — DFS against **live edges only** in `would_create_cycle_*` |
| **Dep-date forward — activities/tasks/subtasks (doc 30)** | 422 `"<kind> '<label>' cannot start on YYYY-MM-DD — the following dependency target(s) end after that date: 'A1.1' (ends YYYY-MM-DD), …"` — applied on create + update for every (source, target) pair. **Equality allowed** (same-day handoff). Helper at [`app/shared/dep_date_rules.py`](app/shared/dep_date_rules.py); wired into the six create/update services across activities, tasks, and subtasks. |
| **Dep-date reverse — activities/tasks/subtasks (doc 30)** | 422 `"<kind> '<label>' cannot end on YYYY-MM-DD — the following dependent(s) would then start before this target ends: 'A1.2' (starts YYYY-MM-DD), …"` — fires when an entity's `end_date` is moved forward and an existing successor's `start_date` would now be violated. Lists every offender by label. |
| **Milestone dep-date — start floor (doc 31)** | 422 `"Milestone '<label>' cannot start on YYYY-MM-DD — it must start on or after every milestone it depends on: 'M1' (starts YYYY-MM-DD), …"` — `source.start >= target.start` (equality allowed). Replaces the doc 30 generic rule for milestones only; activities/tasks/subtasks keep doc 30. |
| **Milestone dep-date — strict end (doc 31)** | 422 `"Milestone '<label>' cannot end on YYYY-MM-DD — it must end strictly after every milestone it depends on: 'M1' (ends YYYY-MM-DD), …"` — `source.end > target.end` (strict, equality REJECTED). Combined with the start floor, both rules can fire together and the response lists every offender for both. Reverse direction also guarded: editing a target milestone's start or end re-validates every existing source. Side-effect: a date-valid milestone cycle is now structurally impossible, so the cycle check is unreachable for milestones (the strict-end rule fires first). |
| **Milestone status-completion gate (doc 31, rule 2c)** | 422 `"Cannot mark this milestone as completed — the following dependency target(s) are not yet completed: 'M1', 'M2' (+N more)."` — fires only on forward transition (`status='completed'`). Reverting from `completed` to `not_completed` is unguarded. Mirrors the activity-side gate. |

**Inputs accept UUIDs OR display labels** (`M1`, `A1.2`, `T1.2.3`, `S1.2.3.4`, and `S1.2.3.4.5…` for nested subtasks). The service resolves labels at write time via `resolve_labels_to_ids` (doc 22 + doc 24).

**Status-completion gate (activities only).** Because activities carry a `status` field, flipping it to `completed` is blocked when any dependency target is not yet `completed`. The gate fires on update only (create doesn't expose completed-from-zero as a user flow — the default is `not_completed`). Returns 403 with `"Cannot mark this activity as completed — the following dependency target(s) are not yet completed: 'A', 'B' (+N more)."`. When the patch also replaces `dependsOn`, the gate evaluates the **new** (live-only) target set.

**Version clone.** When `/projects/{u}/versions/create` clones the M/A tree, `DependencyRepository.clone_milestone_dependencies_for_version` and `clone_activity_dependencies_for_version` copy only the baseline's **live** edges, with both source and target ids rewritten to the version's new ids. Historical (soft-deleted) baseline edges are not carried forward. Activity dep edges are **version-local** — each version's graph evolves independently after the clone. Milestone dep edges, however, **propagate from baseline to active versions** on later edits (doc 21A): when a baseline milestone's `dependsOn` set is modified, `propagate_milestone_dependency_change` mirrors the new edge set onto each active version twin via the `cloned_from_id` lookup.

**Cascade cleanup.** See Section 2.5 — every M/A/T/S soft-delete soft-deletes the dep edges in the subtree through the dedicated repository methods (`cascade_remove_for_deleted_*_subtree`). Source and target directions are both covered so no dead edges dangle after the parent is gone.

---

## 3. Endpoint catalog

### 3.1 Users — [`app/api/v3/users/routes.py`](app/api/v3/users/routes.py)

| Endpoint | Auth | Permission | Body schema | Notes |
|---|---|---|---|---|
| `POST /users/introspect` | public | — | `IntrospectRequest` | Token introspection. `isAdmin` resolved from DB (doc 21B). |
| `POST /users/login` | public | — | `LoginRequest` | Argon2 password check. **Doc 33 change 3:** when `REQUIRE_2FA=true` AND `users.two_factor_enabled=true`, returns `{requires_otp:true, ephemeral_token, channels_available}` instead of the JWT pair; client follows up with `/login/send-otp` + `/login/verify-otp`. Otherwise returns the JWT pair directly (single-stage). Inactive users rejected. |
| `POST /users/login/send-otp` | public (ephemeral_token) | — | `OtpSendRequest` | **Doc 33 change 3** — generate + dispatch a 6-digit OTP for an in-progress 2FA session. Body `{ephemeral_token, channel}`. Cooldown enforced via `OTP_RESEND_COOLDOWN_SECONDS` (default 60s) — earlier resends → 429. Mock backend echoes the code in the response; HTTP backend doesn't. |
| `POST /users/login/verify-otp` | public (ephemeral_token + code) | — | `OtpVerifyRequest` | **Doc 33 change 3** — verify OTP and mint real JWT pair. Wrong codes consume an attempt up to `OTP_MAX_ATTEMPTS` (default 5); correct code consumes the row (single-use). 401 on wrong / expired / consumed / max-attempts-reached. |
| `POST /users/forgot-password` | public | — | `ForgotPasswordRequest` | **Doc 33 change 3** — self-service password reset request. Body `{login_or_email, channel}`. **Always 200** (anti-enumeration) with a generic message. Email channel sends URL token via `password_reset_link` template; SMS channel sends 6-digit OTP via `password_reset_otp`. TTL `PASSWORD_RESET_TTL_SECONDS` (default 3600s). |
| `POST /users/reset-password` | public (reset token) | — | `ResetPasswordRequest` | **Doc 33 change 3** — complete password reset. Body `{token_or_code, new_password}`. Single-use; clears the user's refresh slots so existing sessions are killed. 401 on expired/invalid/consumed. |
| `POST /users/refresh` | public (refresh token) | — | `RefreshRequest` | Rotates the access token; refresh-token grace window of 120s applies (doc 19). |
| `POST /users/logout` | JWT | `require_authenticated` | — | Revokes the current access JTI + clears all 4 refresh slots. |
| `GET /users/me` | JWT | `require_authenticated` | — | Current user (now includes `phoneNumber`, `vendor`, `division`, `projects`). |
| `GET /users/me/permissions` | JWT | `require_authenticated` | — | **Doc 21B:** caller's effective permission set + `isAdmin` flag — FE uses for UI gating. |
| `POST /users/create` | JWT | `users:create` | `UserCreateRequest` | login 3-50 alphanum/underscore/hyphen; email valid; password ≥ 8; **`vendorId` + `division` + `projectIds` + `phoneNumber` required**. login + email unique. `vendorId` accepts a vendor UUID **or** `VN-XXXX-YYMMDDHHMMSS` `vendorCode` (doc 25). `admin=true` assigns the seeded `admin` role. Created row is returned with `id` (UUID — doc 26) and `userCode` (doc 25). |
| `GET /users` | JWT | `users:read_all` | — | `offset≥1`, `pageSize∈[1,100]`, optional `status`. Newest-first. |
| `GET /users/{user_id}` | JWT | `users:read` | — | Path param accepts the UUID `users.id` (doc 26) **or** the `US-XXXX-YYMMDDHHMMSS` `userCode` (doc 25 — auto-detected by the `US-` prefix). Members can read themselves + active users; admins read all. |
| `PATCH /users/{user_id}` | JWT | `users:update` | `UserUpdateRequest` | UUID **or** `US-` code. Members can't change `admin` or `status`; admins can. Last-admin protection on demote/deactivate. |
| `PATCH /users/{user_id}/password` | JWT | `users:update` | `UserPasswordUpdateRequest` | UUID **or** `US-` code. Password ≥ 8. Self-service or admin-for-any. |
| `DELETE /users/{user_id}` | JWT | `users:delete_all` | — | UUID **or** `US-` code. Soft-delete (sets `deleted_at`, `status='inactive'`). Project_members rows preserved. Last-admin lockout. |
| `POST /users/{user_id}/restore` | JWT | `users:delete_all` | — | UUID **or** `US-` code. Clears `deleted_at`, `status='active'`. Idempotent on already-active. |

**RBAC user-side endpoints (doc 21B):**

| Endpoint | Permission | Notes |
|---|---|---|
| `GET /users/{id}/permissions` | `permissions:read` | Effective permissions + direct grants for a user. |
| `POST /users/{id}/permissions/{code}` | `rbac:assign` | Direct grant (additive). |
| `DELETE /users/{id}/permissions/{code}` | `rbac:assign` | Revoke direct grant. |
| `GET /users/{id}/roles` | `permissions:read` | List user's roles. |
| `POST /users/{id}/roles/{role_id}` | `rbac:assign` | Assign role. |
| `DELETE /users/{id}/roles/{role_id}` | `rbac:assign` | Unassign role; **last-admin lockout fires** on the seeded `admin` role. |

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
| `POST /projects/{uuid}/publish` | JWT | `PROJECTS_PUBLISH` (admin) | — | Transition `{new,draft} → published`. 409 if already published. **Doc 30**: rejects publish (422 `invalid_publish`) if the project has zero milestones (`no_milestones`) or any milestone has zero live activities (`milestone_without_activity` — names every empty milestone). Locks out PATCH of non-whitelisted fields but published baselines remain editable on the whitelisted set. |
| `POST /projects/{uuid}/close` | JWT | `PROJECTS_CLOSE` (admin) | `ProjectCloseRequest` (optional) | Transition `{new,draft,published} → closed`. `reason` ≤ 5000 chars. |
| `POST /projects/{uuid}/suspend` | JWT | `PROJECTS_UPDATE` | — | **Version only** (state-machine guard). |
| `POST /projects/{uuid}/versions/create` | JWT | `PROJECTS_CREATE` | — | Source must be `is_version=False AND status='published'`. Only **one active version per baseline**; returns 409 if one already exists. Enforced by partial unique index `ux_projects_active_version_per_baseline` + service check. Cloned tree stamps `cloned_from_id` on every M/A. |

**`ProjectCreateRequest` validations** (schema-level):
- `name` 1-255 chars
- `description` ≤ 5000 chars
- **`startDate` may be in the past** (doc 24); `endDate` must be in the future; `endDate >= startDate` (equal allowed)
- `status` ∈ `{new, draft, published, closed, suspended}` (default `new`)
- `category` ∈ `{MSAP, MSIP, BSP, others}` if supplied
- `categoryOther` required (non-empty ≤ 255 chars) **iff** `category='others'`; rejected otherwise
- `categoryOtherReason` required (non-empty ≤ 1000 chars) **iff** `category='others'`; rejected otherwise (added in doc 15 — captures *why* "others" was chosen)
- `vendorIds` list of vendor UUIDs **or** `VN-XXXX-YYMMDDHHMMSS` codes (doc 25 — mixed lists allowed; the persisted FKs are always canonical UUIDs)

**Service-layer additions on create:**
- Every vendor id must exist and be `active=True`.
- `status` is verified against the `project_status_transitions` catalog (see §3.3a). Returns `invalid_status` on a typo.
- `owner` is now a strict division code (`tmd1` / `tmd2` / `others`) rather than a user-login lookup; the per-user `project_owners` whitelist was removed in doc 20.

### 3.3 Project tree — [`app/api/v3/tree/routes.py`](app/api/v3/tree/routes.py)

| Endpoint | Auth | Permission | Notes |
|---|---|---|---|
| `GET /projects/{uuid}/tree` | JWT | `PROJECTS_READ` | Nested M → A → T → S with resource blocks inlined on resource-type rows. Every A/T/S node carries a `dependsOn` list of target ids (pre-fetched in three bulk queries; no N+1). `includeDeleted=true` admin-practice; default filters soft-deleted. |

### 3.3a Master data — `/api/v3/master/*` (doc 20 + 21B follow-up)

All catalog CRUD lives under the consolidated `/api/v3/master/` router and is gated by **`master_data:view`** / **`master_data:manage`** permissions. The legacy per-catalog endpoints (`/divisions`, `/project_status_transitions`, `/resource_types`, `/vendors/*`, `/roles/*`, `/permissions/*`) keep responding for FE compatibility but stamp `Deprecation: true` + `Link: <successor>; rel="successor-version"`.

| Endpoint | Permission | Notes |
|---|---|---|
| `GET /master/divisions` | `master_data:view` | `?include_inactive=true` for admin view |
| `POST /master/divisions/create` | `master_data:manage` | New custom division; built-ins protected from delete/patch |
| `PATCH /master/divisions/{code}` | `master_data:manage` | |
| `DELETE /master/divisions/{code}` | `master_data:manage` | Soft-deactivate (`active=false`) |
| `POST /master/divisions/{code}/restore` | `master_data:manage` | |
| `GET /master/project_status_transitions` | `master_data:view` | Drives the FE next-step dropdown. Each row carries `requiresAdmin`, `versionOnly`. |
| `POST/PATCH/DELETE /master/project_status_transitions[/…]` | `master_data:manage` | Edit the state-machine catalog |
| `GET /master/resource_types` | `master_data:view` | RFP / ASG / CCN seeded; soft-delete supported |
| `POST/PATCH/DELETE /master/resource_types[/…]` | `master_data:manage` | |
| `GET /master/vendors` | `master_data:view` | Delegates to existing handlers; embedded mapped projects |
| `POST/PATCH/DELETE /master/vendors[/…]` | `master_data:manage` | Vendor `phoneNumber` is **required** on create (doc 23) |
| `GET /master/roles` | `master_data:view` | Roles catalog |
| `POST/PATCH/DELETE /master/roles[/…]` | `master_data:manage` | `admin` role is locked — cannot be deleted, renamed, or have permissions modified |
| `GET/PUT /master/roles/{id}/permissions` | `master_data:view` / `master_data:manage` | List or replace a role's permission set |
| `POST/DELETE /master/roles/{id}/permissions/{code}` | `master_data:manage` | Grant / revoke a single code on a role |
| `GET /master/permissions` | `master_data:view` | Permission catalog (built-ins + custom) |
| `POST/PATCH/DELETE /master/permissions[/{code}]` | `master_data:manage` | Custom permissions; built-ins protected from delete |

**Validator wiring on project create:** the service consults the project_status_transitions catalog for `status` (`invalid_status` on a value not in the catalog). The legacy per-user `project_owners` whitelist was removed in doc 20 — `owner` is now a strict division code.

### 3.4 Vendors — legacy `/api/v3/vendors/*` (DEPRECATED — use `/master/vendors/*`)

These endpoints remain functional but stamp `Deprecation: true` + `Link: rel="successor-version"`. Doc 23 made `phoneNumber` **required** on create; existing callers must include it.

### 3.5 Resource types — legacy `/api/v3/resource_types/*` (DEPRECATED — use `/master/resource_types/*`)

Same deprecation pattern. Built-ins (RFP, ASG, CCN) are protected from delete.

### 3.6 Milestones — [`app/api/v3/milestones/routes.py`](app/api/v3/milestones/routes.py)

| Endpoint | Auth | Permission | Body | Guards |
|---|---|---|---|---|
| `POST /projects/{uuid}/milestones/create` | JWT | `MILESTONES_CREATE` | `MilestoneCreateRequest` (JSON or multipart) | `assert_milestone_activity_writable` (baseline only). **Doc 32**: accepts multipart with optional `body` (comment) + `files` (uploads); same URL/auth/permission. |
| `GET /projects/{uuid}/milestones` | JWT | `MILESTONES_READ` | — | Paginated list. |
| `GET /milestones/{id}` | JWT | `MILESTONES_READ` | — | Single read. |
| `PATCH /milestones/{id}` | JWT | `MILESTONES_UPDATE` | `MilestoneUpdateRequest` | `assert_milestone_activity_writable` + propagation cascade. |
| `DELETE /milestones/{id}` | JWT | `MILESTONES_DELETE` | — | `assert_milestone_activity_writable` + subtree cascade + version cascade. |
| `POST /milestones/{id}/restore` | JWT | `MILESTONES_RESTORE` (admin) | — | `assert_project_editable` (permissive — no baseline/version rule). |

**Schema validations:** `name` 1-255, `startDate < endDate`, `status ∈ MILESTONE_STATUS_CHOICES` (`not_completed`, `completed`), `dependsOn: List[str]` (UUIDs or labels — doc 21A + doc 22; replaces the legacy JSON `depends` column dropped in doc 22), `vendors` list (renamed from `vendorIds` in doc 15; the legacy `vendorIds` and `vendor_ids` aliases are still accepted on the input side via Pydantic `AliasChoices`).

**Doc 32 multipart shape:** when `Content-Type: multipart/form-data`, the body adds two optional fields:
- `body` — free-text comment to attach to the just-created milestone.
- `files` — one or more file uploads to attach. Pre-validated (count, size, mime) BEFORE the milestone insert so a rejected file doesn't leave behind an orphan milestone.

If `body` is set with no `files`, a comment is created. If `files` are set with no `body`, standalone attachments are created. Both can be present. JSON contract is unchanged. Same shape applies to all 7 M/A/T/S create endpoints (4 activity variants, task, top-level subtask, nested subtask).

**Doc 32 followup — position auto-bump:** caller-supplied `position` colliding with an existing live row no longer 500s on the unique-index. Service auto-bumps to the next free slot (Swagger UI auto-fills `position=0` on multipart, which used to crash the second create).

**Service validations:**
- `start_date ≥ project.start_date`
- `end_date ≥ start_date`
- Parent project must have `start_date` set
- `vendorIds` must be a **subset** of the project's vendor list (each vendor must also exist + be active). Each entry can be a vendor UUID **or** `VN-XXXX-YYMMDDHHMMSS` code (doc 25).
- `dependsOn` targets must be live milestones in the same project; no self-edge; cycle detection via `would_create_cycle_milestone`.

**Cascade:** create / update / delete each propagate to active-version twins with their own audit entries. Milestone dep-edge changes also propagate via `propagate_milestone_dependency_change` (doc 21A).

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

**Shape rules:** same `type / resourceMode / resource` matrix as activities, **minus** `status` (tasks don't carry that). Date floor is `activity.start_date`. **Doc 24 part 3:** `dependsOn` follows the same rules as activities — same project, no self-edge, no cycle. The legacy parent-activity hierarchy rule was dropped; tasks may depend on any task in the same project regardless of parent activity linkage. See §2.6.

**Type field removed from create body (doc 15).** `TaskCreateRequest` no longer accepts a `type` field — the service derives the type from the parent activity (`activity.type`). The resource-mode shape (`resourceMode` / `resourceCount` / `resource`) is still validated against the inherited type: a task under a non-resource activity must omit them; a task under a resource activity must include `resourceMode` and the matching count/details body. The `type` column on the model is preserved, and `PATCH /tasks/{id}` still accepts an explicit `type` so a future cross-type-mapping endpoint can override the inheritance.

**Tasks do NOT propagate** — they live only in versions. Task dependency edges live on the version alongside them.

### 3.9 Subtasks — [`app/api/v3/subtasks/routes.py`](app/api/v3/subtasks/routes.py)

**Doc 24 part 2: subtasks can nest under other subtasks (unlimited depth).**

| Endpoint | Auth | Permission | Body | Guards |
|---|---|---|---|---|
| `POST /tasks/{id}/subtasks/create` | JWT | `subtasks:create` | `SubtaskCreateRequest` | `assert_task_subtask_writable`; creates a top-level subtask under the task. |
| `POST /subtasks/{parent_subtask_id}/subtasks/create` | JWT | `subtasks:create` | `SubtaskCreateRequest` | **New (doc 24).** Creates a nested child of the parent subtask; the root `task_id` is inferred from the parent. |
| `GET /tasks/{id}/subtasks` | JWT | `subtasks:read` | — | Paginated. Returns top-level + nested rows under the task (via the shared root `task_id`). |
| `GET /subtasks/{id}` | JWT | `subtasks:read` | — | Response includes `parentSubtaskId` (NULL for top-level). |
| `PATCH /subtasks/{id}` | JWT | `subtasks:update` | `SubtaskUpdateRequest` | `assert_task_subtask_writable`. |
| `DELETE /subtasks/{id}` | JWT | `subtasks:delete` | — | **Cascades soft-delete recursively** through every nested descendant + their dep edges + their resource rows. |
| `POST /subtasks/{id}/restore` | JWT | `subtasks:restore` | — | `assert_project_editable`. |

**Shape rules:** same `type / resourceMode / resource` matrix. Date floor is `parent.start_date` (the immediate parent — task for top-level, parent subtask for nested). Classification columns (`typeOfResourceId`, `division`, `divisionOther`) currently scoped to **activity** resources only; subtask resources accept the base `ResourcePayload` shape without classification.

**`dependsOn` rules (doc 24 part 3):** same as activities — same project, no self-edge, no cycle. The legacy parent-task hierarchy rule was dropped. Subtasks may depend on any subtask in the same project at any nesting depth.

**Type field removed from create body (doc 15).** The subtask create body no longer accepts `type`; the service derives it from the root task's type. PATCH still accepts `type` for the future cross-type-mapping case. **Resource subtasks may have child subtasks** — there is no leaf-only restriction (doc 24).

**Nesting depth cap (doc 24 part 2):** env var `SUBTASK_MAX_NESTING_DEPTH` (`Optional[int]`, default `None` = unlimited). When set, creates that would push the path past the configured cap return 422. The check counts ancestors plus the new row.

**Position uniqueness:** two partial-unique indexes — `(task_id, position) WHERE deleted_at IS NULL AND parent_subtask_id IS NULL` for top-level siblings under a task and `(parent_subtask_id, position) WHERE deleted_at IS NULL AND parent_subtask_id IS NOT NULL` for siblings under one parent subtask. Together they guarantee labels are unambiguous at every depth.

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
| Task / Subtask write | ❌ 403 | ❌ 403 | ❌ 403 | ✅ (no parent-hierarchy rule on deps — doc 24) | ❌ 403 (project-lock still fires) | ❌ 404 |
| Subtask nesting (doc 24) | n/a | n/a | n/a | ✅ unlimited depth (cap via `SUBTASK_MAX_NESTING_DEPTH` env) | ❌ 403 | ❌ 404 |
| Milestone / Activity restore | ✅ admin | ✅ admin | ✅ admin | ✅ admin | ✅ admin | ✅ admin (only way in) |

Notes:
- "Propagates to versions" fires only for **active** versions (`is_version=True AND status NOT IN ('suspended','closed') AND deleted_at IS NULL`).
- The "one active version per baseline" invariant is enforced at both the service layer and the database (partial unique index). A new version can be minted once the previous one is suspended, closed, or deleted.
- Schemas still run Pydantic validation before any of the above, so shape errors (missing required fields, out-of-range values, bad enum) fail at 422 without reaching the service layer.
