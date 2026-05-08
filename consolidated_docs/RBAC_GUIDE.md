# PMIS RBAC Guide

**Last refresh**: 2026-05-08 (post-doc-43 round 3 — admin demotion + bootstrap super_admin + F1-F4 + G1/G2/G3 (SA peer takeover) + G4/G5 (admin peer takeover) live in production)
**Scope**: how authorization works today, what's legacy / pending cleanup, and how to extend.

This document was written to clear up confusion between the **DB-driven 4-role model** the team designed (admin / member / viewer / vendor) and the **OpenProject-era artifacts** that came in with the upstream import. If you're reading source and seeing both `app/core/rbac.py` and `app/core/permissions.py`, both `/api/v3/roles` and `/api/v3/master/roles`, and a `Permission` enum next to permission strings — start here.

---

## 1. The current model (one paragraph)

A user holds a set of **string permission codes** (`projects:create`, `master_data:manage`, …). The set is the **union** of permissions from every role they're assigned PLUS any **direct grants** from `user_permissions`. The auth middleware loads two views into request state every authenticated request: the flat union (`request.state.user_permissions: Set[str]`) and the per-scope view (`request.state.scoped_permissions: Dict[(scope_kind, scope_id), Set[str]]`). Routes declare what they need via `require_permission("module:action")` for global gates, or `require_project_permission("...")` / `require_org_permission("...")` for scoped gates (doc 41).

There are **nine seeded roles** as of doc 41: the legacy four (`admin`, `member`, `viewer`, `vendor`) plus five doc-41 scoped roles (`super_admin`, `org_admin`, `project_admin`, `project_member`, `division_member`). The `admin` and `super_admin` roles are **auto-synced** to hold every registered code on every boot, and `admin` is **protected** from being deleted, renamed, or having its permission set modified through the API. **Scope** is carried on assignment rows in `user_role_assignments` (`organization_id?` or `project_id?`, exclusive of each other; both NULL means global).

The catalog itself (permissions, roles, role-permission grants) is **DB-driven** as of doc 21B — runtime additions through `POST /api/v3/master/permissions/create` show up immediately without a redeploy. The only thing that **must** be in code is the string of a permission referenced by a route decorator (because the decorator is evaluated at import time).

---

## 2. The nine seeded roles

| Role | Tier | What they can do | What they can't |
|------|------|-----------------|-----------------|
| `super_admin` (doc 41) | global | Everything `admin` does PLUS `users:grant_superadmin` (the gate for assigning `super_admin` itself). **Bootstrap path** (doc 43): a `super_admin / superadmin123` user is auto-created on first boot via `app/infrastructure/db/session.py` with a global row in `user_role_assignments` for the `super_admin` role. No API path lets a non-super-admin grant the role. | Lockout-protection refuses to revoke / deactivate / DELETE the last super_admin. **Post-G2/G3 (doc 43 round 2)**: a super_admin cannot change another super_admin's password or DELETE another super_admin without first revoking the target's super_admin role. |
| `admin` | global | Everything except granting `super_admin`. Auto-synced to hold every code in `ADMIN_FULL_ROLE_PERMISSIONS` (= every code minus `users:grant_superadmin`) on every boot. **Pre-doc-43 the bootstrap admin user was auto-created on every boot — that auto-create is GONE post-doc-43.** Existing admin rows are preserved; new deploys must promote operators via super_admin. | Cannot grant `super_admin` or `admin` (doc 43 caller-vs-target). Cannot PATCH / password-change / DELETE a super_admin user (F1 hierarchy gate). Cannot self-deactivate (G1, doc 43 round 2). **Cannot change another admin's password or DELETE another admin** without first revoking the target's admin role (G4/G5, doc 43 round 3). Admin role row is locked from delete / rename / permission-set mutation through the API. |
| `member` | global | Default contributor: read/update users, full CRUD on projects + M/A/T/S, work_packages CRUD, meetings CRUD, comments, attachments. Read-only on master data + vendor catalog. | Cannot publish/close/delete projects, cannot manage RBAC (`rbac:assign`, `roles:*`, `permissions:*`), cannot manage master data (`master_data:manage`), cannot read all soft-deleted records (`*_all` flavors). |
| `viewer` | global | Read-only across projects + master data. Can download attachments. | Anything that mutates state. |
| `vendor` (doc 33 change 1) | global | External collaborator. Full CRUD on M/A/T/S + comments + attachments + own-user update. Read-only on project + master data + vendor catalog. View-only on meetings. | Cannot create / publish / close / delete projects, cannot manage RBAC, cannot touch master data, cannot create / edit / delete meetings, no work_packages access. |
| `org_admin` (doc 41) | scope=org (vendor) | Manage user / project memberships within their owning vendor. `RBAC_ASSIGN` is granted, but the caller-vs-target gate restricts the assignments they can create to `project_admin` / `project_member` / `division_member` on projects whose owning vendor matches the org_admin's `organization_id`. | Cannot publish/close/delete projects, cannot edit project content, cannot grant org_admin or super_admin. |
| `project_admin` (doc 41) | scope=project | Manage tasks/subtasks + project-membership on **the specific project the assignment carries**. Caller-vs-target rules let them grant `project_member` (only) on that project. | Cannot create projects, cannot grant project_admin (only project_member), cannot touch master data or RBAC outside their project. |
| `project_member` (doc 41) | scope=project | Read project + its M/A/T/S, contribute task/subtask updates, comment, upload/download attachments. | Cannot delete project content, cannot grant any role, cannot manage milestones/activities create or delete. |
| `division_member` (doc 41) | scope=project | Read-only at this stage. Future workbox / approval workflow will add request/approve permissions. | Anything that mutates state. (Scoped to projects so the upcoming inbox can filter by membership.) |

The seeded permission lists for member / viewer / vendor / and the doc-41 scoped roles live in [`app/core/permissions.py`](../app/core/permissions.py) (`MEMBER_ROLE_PERMISSIONS`, `VIEWER_ROLE_PERMISSIONS`, `VENDOR_ROLE_PERMISSIONS`, `SUPER_ADMIN_ROLE_PERMISSIONS`, `ADMIN_FULL_ROLE_PERMISSIONS`, `ORG_ADMIN_ROLE_PERMISSIONS`, `PROJECT_ADMIN_ROLE_PERMISSIONS`, `PROJECT_MEMBER_ROLE_PERMISSIONS`, `DIVISION_MEMBER_ROLE_PERMISSIONS`). The seed loop in `RbacRepository.sync_builtin_permissions` upserts them on every boot — if you add a new role-bundle entry there, restart the app and the seeded role gains the code.

The role names live as constants: `ADMIN_ROLE_NAME`, `MEMBER_ROLE_NAME`, `VIEWER_ROLE_NAME`, `VENDOR_ROLE_NAME`, `SUPER_ADMIN_ROLE_NAME`, `ORG_ADMIN_ROLE_NAME`, `PROJECT_ADMIN_ROLE_NAME`, `PROJECT_MEMBER_ROLE_NAME`, `DIVISION_MEMBER_ROLE_NAME`. The `admin` and `super_admin` names are what the lockout protections (§6) check against.

---

## 2a. Scoped RBAC (doc 41)

The pre-doc-41 model granted roles globally — a `member` was a member of the **whole product**. Doc 41 added per-row scope so the same role can mean "X on project P, but not on project Q." Three layers:

1. **`user_role_assignments` table** — the new owner of the (user → role → scope) link. PK is a synthetic `id`; rows carry `user_id, role_id, organization_id?, project_id?` with a CHECK constraint that rejects two-scope rows. Both nullable ⇒ global; exactly one set ⇒ org or project.
2. **Per-scope permission view** — `RbacRepository.effective_permissions_by_scope(user_id)` returns `Dict[(scope_kind, scope_id), Set[str]]`. Auth middleware hydrates this onto `request.state.scoped_permissions`.
3. **Scope-aware route gates** —
   - `require_project_permission(code)` resolves project_id from path_params (`project_uuid` / `project_id` direct, or via M-A-T-S/membership/comment/attachment ancestor lookup) and checks the user holds `code` at scope `("project", project_id)` OR globally.
   - `require_org_permission(code)` resolves vendor_id (= organization_id) similarly and checks scope `("org", vendor_id)` OR global.

**Caller-vs-target gate** (enforced in `app/api/v3/role_assignments/services.can_caller_grant`, lives in user-mgmt; monolith doesn't expose role-assignment writes). **Symmetric for grant + revoke post-doc-43**: same matrix gates POST and DELETE on `/role-assignments`.

| Caller | Can grant / revoke |
|---|---|
| `super_admin` | any role at any scope (only role that can grant or revoke `super_admin` and `admin`) |
| `admin` | any role **except** `super_admin` and `admin` (post-doc-43 demotion — admin can no longer grant peers) |
| `org_admin` of vendor X | `project_admin` / `project_member` / `division_member` on projects whose owning vendor is X |
| `project_admin` of project P | `project_member` on P only |
| anyone else | nothing |

**Backwards compatibility — what stayed**: legacy `user_roles` rows continue to count as global-scope grants. The doc-41 alembic migration `d0c41a55145d` backfilled every legacy `user_roles` row into `user_role_assignments` (both scope columns NULL = global) and copied any `project_members.roles[]` entries into project-scoped rows. `user_roles` and `project_members.roles[]` are not yet dropped — that's a follow-up doc once the FE reads scope from the new table exclusively.

**Where the boundary is enforced today**: monolith routes that mutate project state (`PATCH /projects/{id}`, project lifecycle, M/A/T/S create/update/delete/restore, project_members add/update/delete) all use `require_project_permission`. **Comment + attachment writes intentionally still use the global union** — their `target_id` path param is target-kind-agnostic and would need a target-kind-aware decorator factory to scope cleanly. Tightening this is a follow-up.

**API surface** (all served by user-management on port 8001):

| Method | Path | Purpose | Reachable via :8000 (proxy)? |
|---|---|---|---|
| POST/GET/DELETE | `/api/v3/users/{id}/role-assignments` | Per-user assignment CRUD. | Yes (matches existing `/api/v3/users/*` proxy prefix). |
| POST/DELETE | `/api/v3/projects/{id}/role-assignments` | Per-project assignment CRUD (path's `project_id` is canonical). | **No** — FE must hit `:8001` directly. The monolith does not proxy `/projects/{id}/role-assignments` (would conflict with the heavily-used `/projects/*` namespace). |
| GET | `/api/v3/projects/{id}/role-assignments` | Per-project drill-down view, grouped by role bucket. Powers the FE Project-Mapping mock. | **No** — same reason. `:8001` only. |
| GET | `/api/v3/vendors/{id}/projects?expand=role-assignments` | Org-Mgmt landing view: every project owned by the vendor with optional role buckets inlined. | **No** — `:8001` only. Note: monolith has its own `/vendors/{id}/projects` legacy handler (different shape, no `roleAssignments`); FE picks based on need but the doc-41 shape lives only on `:8001`. |
| GET | `/api/v3/users/{id}/projects` | User-Mgmt landing view: every project the user is assigned to and the role names they hold there. | Yes (matches `/api/v3/users/*` proxy prefix). |

---

## 3. The permission catalog

**Source of truth**: `permissions` table. Codes are upserted from the in-code list `BUILTIN_PERMISSIONS` in [`app/core/permissions.py`](../app/core/permissions.py) on every boot. Adding a new built-in code is a code change (because routes reference the string from the same file); adding a custom permission for a future module is a runtime API call.

**Code shape**: every code is `module:action`. Common modules: `projects`, `users`, `milestones`, `activities`, `tasks`, `subtasks`, `comments`, `attachments`, `master_data`, `roles`, `permissions`, `rbac`, `meetings`, `work_packages`, `work_package_types`, `vendors`, `resource_types`, `project_members`.

**Built-in protection**: `is_builtin=True` rows cannot be deleted via the API (the route returns 422). Their `name` and `description` ARE editable so admins can rename a code's display label without forking source.

**Catalog endpoints** — both gated by `master_data:view` / `master_data:manage`:

| Endpoint | Purpose |
|---|---|
| `GET /api/v3/master/permissions` | Flat list, paginated. |
| `GET /api/v3/master/permissions/by-module` | Same content grouped by module prefix; modules sorted alphabetically; permissions per module sorted by code. **Doc 33 change 2** added this so the FE picker tree doesn't have to parse `module:action` strings. |
| `GET /api/v3/master/permissions/{code}` | Single read. |
| `POST /api/v3/master/permissions/create` | Add a custom code (built-ins are not creatable here — they're owned by source). |
| `PATCH /api/v3/master/permissions/{code}` | Edit name / description (built-ins protected from delete but editable on metadata). |
| `DELETE /api/v3/master/permissions/{code}` | Custom rows only. |

---

## 4. Roles + role-permission grants

**Tables**: `roles`, `role_permissions` (junction).

**Endpoints** under `/api/v3/master/roles/*`:

| Endpoint | Purpose |
|---|---|
| `GET /api/v3/master/roles` | List with pagination. |
| `GET /api/v3/master/roles/{id}` | Single read. |
| `POST /api/v3/master/roles/create` | Create a custom role. |
| `PATCH /api/v3/master/roles/{id}` | Rename / update description. **Admin role rejects any patch (403)**. |
| `DELETE /api/v3/master/roles/{id}` | Delete a custom role. **Admin role and any role currently held by a user with no other admin lose to lockout protections.** |
| `GET /api/v3/master/roles/{id}/permissions` | List the role's permission codes. |
| `PUT /api/v3/master/roles/{id}/permissions` | Replace the entire permission set in one call. **Admin role rejects (403).** |
| `POST /api/v3/master/roles/{id}/permissions/{code}` | Grant one code (idempotent — no-op if already granted). **Admin role rejects (403).** |
| `DELETE /api/v3/master/roles/{id}/permissions/{code}` | Revoke one code. **Admin role rejects (403).** |

The legacy paths (`/api/v3/roles`, `/api/v3/permissions`) keep responding for back-compat but stamp `Deprecation: true` + `Link: <successor>; rel="successor-version"` on every response — see §7.

---

## 5. User-side: assigning roles + direct grants

**Tables**: `user_roles` (many-to-many user ↔ role), `user_permissions` (direct user ↔ permission grants — additive).

**Endpoints** stay on `/api/v3/users/*` because they operate on a specific user, not on the catalog:

| Endpoint | Permission | Purpose |
|---|---|---|
| `GET /api/v3/users/me/permissions` | authenticated | Caller's own effective set + `isAdmin` flag — FE uses this to decide which buttons to render. |
| `GET /api/v3/users/{id}/permissions` | `permissions:read` | Effective set + direct grants for any user. |
| `POST /api/v3/users/{id}/permissions/{code}` | `rbac:assign` | Direct grant (additive on top of role-derived). |
| `DELETE /api/v3/users/{id}/permissions/{code}` | `rbac:assign` | Revoke a direct grant. Doesn't touch role-derived perms. |
| `GET /api/v3/users/{id}/roles` | `permissions:read` | List a user's roles. |
| `POST /api/v3/users/{id}/roles/{role_id}` | `rbac:assign` | Assign a role. |
| `DELETE /api/v3/users/{id}/roles/{role_id}` | `rbac:assign` | Unassign a role. **Last-admin lockout fires** if the target is the sole admin holder. |

**There is no deny semantics.** The effective set is `union(role_derived, direct_grants)`. To revoke, delete the source row.

---

## 6. Lockout protections + hierarchy guards (post-doc-43)

Doc 43 pivoted the protected tier from `admin` to `super_admin`. Round 2 (G1/G2/G3) added the self-deactivate guard and peer-takeover blocks on destructive ops. All guards sit in the service layer of the user-management service, so they fire regardless of which surface the caller arrives through.

| Guard | Trigger | Response | Source |
|---|---|---|---|
| **Last-super_admin role-revoke** | `DELETE /users/{id}/role-assignments/{aid}` on the only global super_admin assignment | 403 | doc 43 round 1 |
| **Last-super_admin user-DELETE** | DELETE on the only live super_admin user | 422 | doc 43 round 1 |
| **Last-super_admin deactivate** | PATCH `status=inactive` on the only live super_admin (defence-in-depth — preempted at route by G1 / F1) | 422 | doc 43 round 1 |
| **F1 hierarchy gate** | admin caller PATCH / password-change / DELETE on a super_admin user | 403 | doc 43 round 1 |
| **F2 reserved permission** | grant of `users:grant_superadmin` to anyone but the super_admin role; direct user-permission grant of the same code | 403 | doc 43 round 1 |
| **L1 / L2 role-row lock** | DELETE / PATCH / permission-set mutation on the seeded `admin` or `super_admin` role row | 403 | doc 43 round 1 |
| **G1 self-deactivate** | PATCH `status=inactive` where caller == target (any tier) | 403 "Cannot deactivate your own account." | doc 43 round 2 |
| **G2 peer-SA password change** | super_admin → another super_admin via `PATCH /users/{id}/password` | 403 | doc 43 round 2 |
| **G3 peer-SA DELETE** | super_admin → another super_admin via `DELETE /users/{id}` | 403 | doc 43 round 2 |
| **G4 peer-admin password change** | admin → another admin via `PATCH /users/{id}/password` (neither holds super_admin) | 403 | doc 43 round 3 |
| **G5 peer-admin DELETE** | admin → another admin via `DELETE /users/{id}` (neither holds super_admin) | 403 | doc 43 round 3 |
| **Self-delete guard** (legacy) | DELETE on caller == target | 403 | pre-doc-41 |
| **Self-demote-from-admin guard** | PATCH `admin=False` on caller's own row when they hold admin | 403 | pre-doc-41 |

Pre-doc-43 "last admin" guards have been **removed**. Admin is no longer protected — admin users can be freely demoted, deactivated, or deleted as long as a super_admin remains. The only system-required identity is super_admin.

**Universal-OTP backdoor warning**: when `UNIVERSAL_OTP_ENABLED=true`, both services emit a `SECURITY: ...` `WARNING` line at startup so deploy logs flag the backdoor before it carries into production.

---

## 7. Legacy paths and OpenProject artifacts (what you're seeing duplicated)

The codebase came in from an OpenProject upstream port and went through several RBAC iterations. This is what's currently live and what's transitional:

### 7a. Legacy paths under `/api/v3/{roles,permissions}` (DEPRECATED)

`app/api/v3/roles/` and `app/api/v3/permissions/` still exist and still respond. **Doc 21B follow-up** moved their content under `/api/v3/master/{roles,permissions}/*` but kept the legacy paths working so the FE migration could happen separately. Every legacy response now stamps:

```
Deprecation: true
Link: </api/v3/master/roles/...>; rel="successor-version"
```

The FE should switch to the master paths; the legacy ones will be removed in a future doc once FE has migrated.

### 7b. `app/core/rbac.py` — the `Permission` enum (TRANSITIONAL)

The file used to hold three things: a `Role` enum, a `ROLE_PERMISSIONS` dict, and a `Permission` enum. Doc 21B (followed by doc 33 change 2 cleanup) deleted the first two — they were vestiges of the in-memory RBAC the OpenProject template carried. **Only the `Permission` enum remains**, and only because every `app/api/v3/*/permissions.py` re-export shim imports it. The canonical form going forward is the string constants in `app/core/permissions.py`. The enum will go when those shims migrate to direct strings.

If you see code using `Permission.PROJECTS_CREATE`, that's the same value as the string `"projects:create"` — both are accepted by `require_permission`. New code should use the string constants from `app/core/permissions.py`.

### 7c. The `/api/v3/catalogs` router

`app/api/v3/catalogs/routes.py` is a holdover that bundled some master-data reads under `/api/v3/catalogs/*` before doc 20 consolidated everything under `/api/v3/master/*`. Currently it stamps deprecation headers. Same removal plan as §7a.

### 7d. OpenProject reporter / manager / member terminology

The upstream OpenProject codebase had a reporter / member / manager / admin role hierarchy. Some old comments and docs still reference those. **They are not in use.** Our four roles are `admin / member / viewer / vendor` — search and replace as you find them. Project-scoped role assignments live in `project_members.roles` (a JSON array stored per `(project_id, user_id)`) which is a separate concept from global `user_roles` and is currently underused.

### 7e. `Permission` enum vs string constants — which to use

Both work. `require_permission` accepts either. New code should prefer the string constants from `app/core/permissions.py` (e.g. `from ....core.permissions import PROJECTS_CREATE` then `require_permission(PROJECTS_CREATE)`). The enum is the bridge while shims migrate.

### 7f. The "permissions endpoint that has legal states for statuses" you might be remembering

You may be thinking of `project_status_transitions` — a runtime catalog (table + master endpoint) holding legal `(from_status, to_status)` edges for the project lifecycle. It's NOT the permissions catalog; it's the project state machine. The `assert_transition_allowed` helper in `app/api/v3/projects/services/transitions.py` consults the table first, falls back to in-code constants. **There is no equivalent partial implementation for milestone or activity status transitions** — those still use hardcoded enums, and **doc 37 part 1** is the planned change to extract them into master tables alongside `project_categories` and `activity_types`.

---

## 8. Per-request flow

Every protected request follows this pipeline (already documented in [FLOW_MAP_AND_VALIDATIONS.md](FLOW_MAP_AND_VALIDATIONS.md) §1; restated here as it's central to RBAC):

```
HTTP request
   │
   ▼
LoggingMiddleware  (X-Request-ID stamping)
   │
   ▼
AuthenticationMiddleware  (doc 21B)
   │  decode JWT (HS256)
   │  check revoked_tokens by jti
   │  if valid:
   │    user_id      = claim
   │    user_login   = claim
   │    token_jti    = claim
   │    token_exp    = claim
   │    user_permissions: Set[str]   ← RbacRepository.effective_permissions_for_user()
   │                                   ONE DB query for the union of role_perm + direct_perm
   │    is_admin: bool               ← True iff user holds the seeded admin role
   │  else: every field is None / empty set
   ▼
require_permission("module:action")  (FastAPI dependency)
   │  401 if user_id is None
   │  403 if code not in request.state.user_permissions
   ▼
Route handler → service → repository → response
```

The `effective_permissions_for_user` query joins `user_roles → role_permissions` UNION `user_permissions` and returns a flat set. The hydration is **one** DB roundtrip per request — no N+1.

---

## 9. JWT contents

Doc 21B + doc 26 settled the claim shape:

```json
{
  "sub":     "admin",
  "user_id": "8bd99f06-5f2a-424c-aaff-10ab163c3e42",
  "email":   "admin@example.com",
  "jti":     "...",
  "iat":     ...,
  "exp":     ...
}
```

- `user_id` is a UUID string (doc 26 — was an integer pre-doc-26; auth middleware rejects pre-doc-26 integer tokens with 401, not 500).
- `role` and `is_admin` are **NOT** in the JWT — they're resolved from the DB on every request. This was deliberate: the JWT is a stable identity claim, the **permissions** are looked up so they reflect current grants. Demoting a user takes effect on their next request, not at the next refresh boundary.
- Tokens issued before doc 21B that still carry `role` / `is_admin` keep working — those claims are simply ignored.

---

## 10. Adding a new permission / role / permission to a role

### Add a built-in permission code (available to every fresh boot)

1. Add a string constant + `PermissionDef(...)` entry to `BUILTIN_PERMISSIONS` in [`app/core/permissions.py`](../app/core/permissions.py).
2. Optionally add the code to `MEMBER_ROLE_PERMISSIONS` / `VIEWER_ROLE_PERMISSIONS` / `VENDOR_ROLE_PERMISSIONS` lists in the same file so the seeded roles pick it up automatically.
3. Reference the constant from a route: `require_permission(MY_NEW_CODE)`.
4. Restart the app — `init_db` upserts the new code into `permissions` and (re-)syncs role grants.

### Add a custom permission at runtime

`POST /api/v3/master/permissions/create` with `{code, name, description}`. The new code is immediately listable via the catalog endpoints. Custom permissions cannot drive route decorators (which are import-time strings) — they're useful for application-level features that look up permissions dynamically.

### Add a custom role

`POST /api/v3/master/roles/create` with `{name, description}`. Then either `PUT /api/v3/master/roles/{id}/permissions` to replace its permission set in one call, or `POST /api/v3/master/roles/{id}/permissions/{code}` to grant individual codes.

### Assign a role to a user

`POST /api/v3/users/{user_id}/roles/{role_id}`. Permission required: `rbac:assign`. Effective on the user's next request.

### Grant a single direct permission to a user

`POST /api/v3/users/{user_id}/permissions/{code}`. Same `rbac:assign` requirement. Direct grants are additive — they augment but never override role-derived permissions.

---

## 11. What's planned (doc 37 + later)

- **Doc 37 part 2 (SHIPPED)**: user-management is now a standalone microservice on port 8001 (`PMIS-user-management` dev `19a30e5`). JWT verification stays decentralized (every service uses the same `SECRET_KEY`); the permission catalog and effective-set lookup live in the user-service. Monolith proxies `/api/v3/users/*` and `/api/v3/master/{roles,permissions,notification_templates}/*` when `USER_SERVICE_PROXY_ENABLED=true` + `USER_SERVICE_URL` set, via `UserServiceProxyMiddleware` in `app/main.py`. Fail-closed on user-service unavailability (503 with `errorIdentifier="user_service_unavailable"`). See `planned_changes/37` for the cutover runbook.
- **Future** (no doc yet): drop `app/api/v3/roles/` and `app/api/v3/permissions/` legacy routers once the FE uses the master paths exclusively (§7a). Remove the `Permission` enum bridge once route shims switch to direct string constants (§7b). Remove `app/api/v3/catalogs/routes.py` (§7c).
- **Doc 41 (SHIPPED, 2026-05-08)**: scoped role assignments are now real (§2a). `user_role_assignments` is the canonical owner; legacy `user_roles` and `project_members.roles[]` continue to count as global / project-scoped grants during a migration window. `require_project_permission` and `require_org_permission` are now wired into all monolith write routes for projects + M/A/T/S + project_members.
- **Future** (post-doc 41): drop `user_roles` + `project_members.roles[]` once the FE reads exclusively from the new role-assignment surface. Tighten comments/attachments to scoped gating (left on union in doc 41 due to target-kind-agnostic path param).

---

## 12. Quick reference — common errors

| Status | Likely cause |
|---|---|
| 401 + "Authentication required" | Token missing or expired. Login again. |
| 401 + "Invalid token" | Wrong signature, malformed, blacklisted (revoked), or pre-doc-26 integer-id. |
| 403 + "Insufficient permissions" | Token good, but the route's required code is not in the user's effective set. Check `GET /users/me/permissions`. |
| 403 + "Built-in role '\<admin\|super_admin\>' cannot be modified" | Trying to delete / rename / mutate the seeded admin or super_admin role. Use a custom role. |
| 403 + "Cannot perform destructive actions (DELETE / password change) on another super_admin. Demote the target first by revoking their super_admin role assignment." | G2 / G3 peer-takeover guard (doc 43 round 2). Revoke target's `super_admin` role-assignment first, then retry. |
| 403 + "Cannot perform destructive actions (DELETE / password change) on another admin. Demote the target first by revoking their admin role assignment." | G4 / G5 peer-takeover guard (doc 43 round 3). Revoke target's `admin` role first, then retry. |
| 403 + "Cannot deactivate your own account." | G1 self-deactivate guard (doc 43 round 2). Have another user with appropriate authority deactivate the account instead. |
| 403 + "Cannot demote yourself from admin." | Pre-doc-41 self-demote guard. |
| 403 + "Cannot revoke last super_admin" | Last-super_admin role-assignment revoke lockout. Promote another user to super_admin first. |
| 422 + "Cannot deactivate the last active super_admin." | Last-super_admin deactivation lockout (typically preempted by F1 / G1 at route). |
| 403 + "users:grant_superadmin can only be held by the super_admin role." | F2 reserved-permission guard (doc 43 round 1). |
