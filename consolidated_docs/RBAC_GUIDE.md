# PMIS RBAC Guide

**Last refresh**: 2026-05-06 (post-doc 36)
**Scope**: how authorization works today, what's legacy / pending cleanup, and how to extend.

This document was written to clear up confusion between the **DB-driven 4-role model** the team designed (admin / member / viewer / vendor) and the **OpenProject-era artifacts** that came in with the upstream import. If you're reading source and seeing both `app/core/rbac.py` and `app/core/permissions.py`, both `/api/v3/roles` and `/api/v3/master/roles`, and a `Permission` enum next to permission strings — start here.

---

## 1. The current model (one paragraph)

A user holds a set of **string permission codes** (`projects:create`, `master_data:manage`, …). The set is the **union** of permissions from every role they're assigned PLUS any **direct grants** from `user_permissions`. The auth middleware loads the set into `request.state.user_permissions` per request. Each route declares the code it needs via `require_permission("module:action")` and FastAPI returns 401 (no token) or 403 (token good, code missing) if the check fails.

There are **four seeded roles**: `admin`, `member`, `viewer`, `vendor` (the last added in doc 33 change 1). The `admin` role is **auto-synced** to hold every registered code on every boot, and is **protected** from being deleted, renamed, or having its permission set modified through the API.

The catalog itself (permissions, roles, role-permission grants) is **DB-driven** as of doc 21B — runtime additions through `POST /api/v3/master/permissions/create` show up immediately without a redeploy. The only thing that **must** be in code is the string of a permission referenced by a route decorator (because the decorator is evaluated at import time).

---

## 2. The four seeded roles

| Role | What they can do | What they can't |
|------|-----------------|-----------------|
| `admin` | Everything. Auto-synced to hold every registered permission code on every boot. | Nothing — they hold everything. (Some lifecycle protections still bite admin, e.g. last-admin lockout — see §6.) |
| `member` | Default contributor: read/update users, full CRUD on projects + M/A/T/S, work_packages CRUD, meetings CRUD, comments, attachments. Read-only on master data + vendor catalog. | Cannot publish/close/delete projects, cannot manage RBAC (`rbac:assign`, `roles:*`, `permissions:*`), cannot manage master data (`master_data:manage`), cannot read all soft-deleted records (`*_all` flavors). |
| `viewer` | Read-only across projects + master data. Can download attachments. | Anything that mutates state. |
| `vendor` (doc 33 change 1) | External collaborator. Full CRUD on M/A/T/S + comments + attachments + own-user update. Read-only on project + master data + vendor catalog. View-only on meetings. | Cannot create / publish / close / delete projects, cannot manage RBAC, cannot touch master data, cannot create / edit / delete meetings, no work_packages access. |

The seeded permission lists for member / viewer / vendor live in [`app/core/permissions.py`](../app/core/permissions.py) at the bottom (`MEMBER_ROLE_PERMISSIONS`, `VIEWER_ROLE_PERMISSIONS`, `VENDOR_ROLE_PERMISSIONS`). The seed loop in `RbacRepository.sync_builtin_permissions` upserts them on every boot — if you add a new role-bundle entry there, restart the app and the seeded role gains the code.

The four role names live as constants: `ADMIN_ROLE_NAME`, `MEMBER_ROLE_NAME`, `VIEWER_ROLE_NAME`, `VENDOR_ROLE_NAME`. The `admin` constant is also the name the lockout protections (§6) check against.

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

## 6. Lockout protections

These are baked into the service layer (not into route decorators) so they fire regardless of who triggers them — including admins:

| Guard | Trigger | Response |
|---|---|---|
| Last-admin removal | Removing the `admin` role from the only user who holds it (via `DELETE /users/{id}/roles/{admin_role_id}`, soft-delete of that user, or status flip to inactive). | 403 / 422 with explanatory message. |
| Admin role mutation | Trying to delete, rename, change description, replace permissions, grant a permission, or revoke a permission on the seeded `admin` role. | 403. |
| Self-demote on sole admin | Sole admin demoting themselves. | 422. |
| Admin role hard delete | `DELETE /api/v3/master/roles/{admin_role_id}`. | 403. |

The intent is **belt-and-braces**: the goal is that `admin` is always reachable. Even an admin with the `rbac:assign` permission can't paint themselves into a corner by misclicking.

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
- **Future** (no doc yet): make project-scoped role assignment (`project_members.roles`) actually drive permission scoping. Today it's a JSON array that's saved but not consulted by `require_permission`. Effective-permission resolution is purely global.

---

## 12. Quick reference — common errors

| Status | Likely cause |
|---|---|
| 401 + "Authentication required" | Token missing or expired. Login again. |
| 401 + "Invalid token" | Wrong signature, malformed, blacklisted (revoked), or pre-doc-26 integer-id. |
| 403 + "Insufficient permissions" | Token good, but the route's required code is not in the user's effective set. Check `GET /users/me/permissions`. |
| 403 + "Built-in role 'admin' cannot be modified" | Trying to delete / rename / mutate `admin` role permissions. Use a custom role. |
| 403 + "Cannot remove last admin" / "Cannot demote last admin" | Lockout protection. Add another admin first, then retry. |
| 422 + "Sole admin cannot be deactivated" | Same as above, on user soft-delete / status flip. |
