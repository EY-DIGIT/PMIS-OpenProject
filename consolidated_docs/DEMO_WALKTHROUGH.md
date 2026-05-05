# PMIS API — End-to-End Demo Walkthrough

Scope: Users (incl. 2FA login + password reset), Vendors, Resource Types, Projects, Milestones, Activities, Tasks, Subtasks, Project Tree, Permissions catalog, Vendor role.
Excluded: project_members, work_packages, work_package_types, meetings.

This walkthrough takes a fresh environment from zero to a fully populated project — including 2FA login, forgot-password, the new vendor role, and the runtime permissions catalog endpoint shipped in doc 33. Each step shows the Swagger UI target, the request body (copy-paste ready), and the success signal to confirm before moving on.

> **Doc 33** removed the baseline/version split entirely. Tasks and subtasks now live directly under the project; there's no clone-and-twin step. If you remember an older walkthrough that involved `POST /projects/{id}/versions/create`, that endpoint is gone (404).

---

## Prerequisites

- Python 3.12 venv activated
- `pip install -r requirements.txt`
- Delete any stale `pmis.db` in the project root (fresh DB ensures seeded vendors + resource types + the new vendor role)
- Start the server: `uvicorn app.main:app --reload`
- Open Swagger UI at `http://127.0.0.1:8000/docs`

**On first boot**, `init_db()` creates the schema and seeds:

- One admin user: `login=admin`, `password=admin123`. **The bootstrap admin is forced single-stage on every boot** (`two_factor_enabled=false`) so the always-reachable break-glass account never gets locked out by an unconfigured notification channel. Other users follow the global `REQUIRE_2FA` + per-user flag normally. Step 0b below still shows the 2FA flow against a regular user you create yourself.
- Five vendors: Infosys, TCS, Wipro, Accenture, Capgemini
- Three resource types: rfp, asg, ccn
- Built-in work package types (not used in this demo)
- Four roles: `admin`, `member`, `viewer`, `vendor` (vendor seeded by doc 33 change 1)
- Permissions catalog (doc 21B + doc 33 change 2)

All the dates in the bodies below are set for **2026**. Replace them with dates in your own future if this document has aged.

For the notification flows (2FA OTP, forgot-password), the OTP code is **never echoed** in the `/send-otp` HTTP response. With `NOTIFICATION_CLIENT=mock` (default) the dispatched payload — including the plaintext code — lands in the `notification_log` table; read it via DB to complete the flow during dev. With `NOTIFICATION_CLIENT=http` the code goes to the real notification microservice.

---

## Demo storyline

We're the admin. We'll:

1. Log in (single-stage when `REQUIRE_2FA=false`, or two-stage OTP path).
2. Walk through the forgot-password / reset-password flow.
3. Browse the runtime permissions catalog grouped by module.
4. List the seeded vendors + resource types.
5. Create a project (`New Ingestion Pipeline`) with a vendor attached.
6. Add two milestones under it.
7. Add activities of all three types (standard, resource/count, resource/details).
8. Wire activity dependencies and exercise the cycle / self-edge / dep-date guards.
9. Save → `new → draft`, then publish → `draft → published`.
10. Add tasks + subtasks **directly under the project's M/A subtree** (no version twin).
11. Demonstrate the activity status-completion gate.
12. Create a vendor-role user and prove they can edit M/A/T/S but not publish.
13. Fetch the full project tree.
14. Soft-delete the project — cascade kills every M/A/T/S in one transaction.

Each section says **Expect** so you can confirm success before continuing.

---

## Step 0a — Log in (single-stage path)

Use this when `REQUIRE_2FA=false` is set in the environment, OR when you've patched the admin user with `twoFactorEnabled=false`.

**Swagger:** `Users ▸ POST /users/login`. Click **Try it out**, paste the body, **Execute**.

```json
{
  "login": "admin",
  "password": "admin123"
}
```

**Expect 200** with `data.access_token`. Click the green **Authorize** button at the top of Swagger, paste `Bearer <token>` (note the word `Bearer ` and the space), click Authorize, then Close. Every subsequent call now carries the header automatically.

If the response instead carries `requires_otp: true` and `ephemeral_token`, your environment has 2FA enforced — use Step 0b instead.

---

## Step 0b — Log in (two-stage 2FA path, doc 33 change 3)

The bootstrap admin is forced single-stage (`two_factor_enabled=false`) on every boot, so to exercise the 2FA flow you'll need a regular user with the flag on. Either:

- Create a new user via `POST /users/create` (admin needed) — `twoFactorEnabled` defaults to `true` for non-bootstrap users when `REQUIRE_2FA=true`. OR
- PATCH an existing test user to set `twoFactorEnabled=true`.

Once you have such a user, log in with their credentials.

### 0b.1 — POST /users/login

```json
{ "login": "<test_user_login>", "password": "<test_user_password>" }
```

**Expect 200** with this shape:

```json
{
  "data": {
    "_type": "LoginOtpRequired",
    "requires_otp": true,
    "ephemeral_token": "<long opaque string>",
    "channels_available": ["email", "sms"],
    "message": "Two-factor authentication required..."
  }
}
```

`channels_available` includes `sms` only if the user has a `phoneNumber` recorded; otherwise it's `["email"]` only.

Save `data.ephemeral_token` as `EPHEMERAL_TOKEN`. No JWT issued yet.

### 0b.2 — POST /users/login/send-otp

```json
{
  "ephemeral_token": "<EPHEMERAL_TOKEN>",
  "channel": "email"
}
```

**Expect 200** with this shape (the OTP code is NOT in the response):

```json
{
  "data": {
    "_type": "OtpSent",
    "channel": "email",
    "expires_in_seconds": 300,
    "resend_after_seconds": 60
  }
}
```

To get the actual OTP code:

- **`NOTIFICATION_CLIENT=mock`** (default) — read it from the `notification_log` table via DB:
  ```sql
  SELECT payload FROM notification_log
   WHERE template_kind = 'otp_login' AND user_id = '<user_uuid>'
   ORDER BY created_at DESC LIMIT 1;
  ```
  The `payload` JSON column carries `{ "code": "123456", "ttl_seconds": 300, "purpose": "login_2fa" }`.
- **`NOTIFICATION_CLIENT=http`** — the code went to the real notification microservice; read from email or wherever that service routes it.

A second call to `/login/send-otp` within `OTP_RESEND_COOLDOWN_SECONDS` (default 60) returns **429** — change `channel` or wait it out.

### 0b.3 — POST /users/login/verify-otp

```json
{
  "ephemeral_token": "<EPHEMERAL_TOKEN>",
  "code": "<OTP_CODE>"
}
```

**Expect 200** — same shape as the single-stage Shape A: `access_token`, `refresh_token`, the full `*ExpiresAt` block, and the `user` payload. Authorize Swagger with `Bearer <access_token>` as in Step 0a.

Wrong codes return **401** and increment a counter. After `OTP_MAX_ATTEMPTS` (default 5) the OTP row is consumed and `/verify-otp` returns 401 even for the right code — the user must restart from `/login`.

---

## Step 0c — Forgot password / reset password (doc 33 change 3)

This is independent of the live admin session — you can do it before or after logging in. We'll reset the admin's own password as a demo, then change it back.

### 0c.1 — POST /users/forgot-password

```json
{
  "login_or_email": "admin",
  "channel": "email"
}
```

**Expect 200** with the generic anti-enumeration message:
```json
{ "data": { "_type": "PasswordResetRequested", "message": "If the account exists, ..." } }
```

The response is **identical** even for a non-existent login — that's the anti-enumeration guarantee. To get the reset token in dev (`NOTIFICATION_CLIENT=mock`), read it from `notification_log`:
```sql
SELECT payload FROM notification_log
 WHERE template_kind IN ('password_reset_link', 'password_reset_otp')
 ORDER BY created_at DESC LIMIT 1;
```
The `payload` JSON column carries the URL token (email channel) or the 6-digit code (SMS channel). Copy it as `RESET_TOKEN`. In production with `NOTIFICATION_CLIENT=http` you'd read this from email/SMS instead.

### 0c.2 — POST /users/reset-password

```json
{
  "token_or_code": "<RESET_TOKEN>",
  "new_password": "tempPass123"
}
```

**Expect 200**. The user's existing refresh tokens are invalidated — log out + log in fresh with the new password to verify, then change it back via `PATCH /users/{id}/password` to `admin123` so the rest of the demo stays predictable.

Tokens are single-use: replaying the same `token_or_code` returns **401** with "already consumed".

---

## Step 1 — Sanity-check the catalogs

### 1a. List vendors

**`GET /api/v3/master/vendors`** — Execute.

**Expect 200** and an `_embedded.elements` list of 5 vendors. Each row carries both `id` (UUID) and `vendorCode` (`VN-XXXX-YYMMDDHHMMSS` — doc 25). Copy *either* identifier for "Infosys" — every cross-entity vendor input below accepts the UUID or the code interchangeably.

### 1b. List resource types

**`GET /api/v3/master/resource_types`** — Execute.

**Expect 200** with `rfp`, `asg`, `ccn`. Copy the `id` of `rfp` — you'll use it as `typeOfResourceId` on a resource activity later.

### 1c. List status transitions catalog

**`GET /api/v3/master/project_status_transitions`** — Execute.

**Expect 200**. Every `(fromStatus, toStatus)` edge plus the seed row (`fromStatus: null, toStatus: "new"`). The `suspended` status is no longer in the catalog — doc 33 dropped it along with the versioning feature. Each row carries `requiresAdmin` so the FE can render context-aware next-step dropdowns.

### 1d. Browse the permissions catalog by module (doc 33 change 2)

**`GET /api/v3/master/permissions/by-module`** — Execute. Permission: `master_data:view`.

**Expect 200** with this shape:

```json
{
  "data": {
    "_type": "PermissionsByModule",
    "_links": { "self": { "href": "/api/v3/master/permissions/by-module" } },
    "moduleCount": 13,
    "totalPermissions": 47,
    "_embedded": {
      "modules": [
        {
          "_type": "PermissionModule",
          "module": "activities",
          "count": 5,
          "permissions": [
            { "_type": "Permission", "code": "activities:create", "name": "...", ... },
            ...
          ]
        },
        { "_type": "PermissionModule", "module": "attachments", ... },
        { "_type": "PermissionModule", "module": "milestones", ... },
        { "_type": "PermissionModule", "module": "permissions", ... },
        { "_type": "PermissionModule", "module": "projects", ... },
        ...
      ]
    }
  }
}
```

Modules are sorted alphabetically; permissions within each module sorted by code. The legacy flat `GET /api/v3/master/permissions` still works — the by-module shape is purely a convenience for FE picker UIs that don't want to parse `module:action` strings.

### 1e. Owner is a division code (no project_owners catalog)

Doc 18 made `project.owner` a strict division code (`tmd1` / `tmd2` / `others`). Doc 20 dropped the per-user `project_owners` whitelist. Manage divisions via `GET/POST/PATCH /api/v3/master/divisions[/…]`.

---

## Step 2 — Create the project

**`POST /api/v3/projects/create`**:

```json
{
  "name": "New Ingestion Pipeline",
  "description": "Demo project for PMIS walkthrough",
  "owner": "tmd1",
  "active": true,
  "isPublic": false,
  "category": "MSIP",
  "startDate": "2026-05-01T09:00:00Z",
  "endDate": "2026-12-31T17:00:00Z",
  "vendors": ["<INFOSYS_VENDOR_ID>"]
}
```

> **Doc 24 part 1:** `startDate` may be in the past — entering an in-progress project no longer requires backdating "now". Only `endDate` keeps the future-only check.
> **Doc 18:** `owner` is a strict division code (`tmd1` / `tmd2` / `others`).
> **Doc 33 change 1:** the response no longer includes `isVersion`, `versionOf`, `baselineId`, or `versionNo` — those fields are gone for good.

**Expect 201.** The response shows a fresh UUID `data.id`, `data.projectCode` starting with `UIDAI-PR`, `data.status: "new"`, and `data.vendors` listing Infosys.

**Save `data.id` as `PROJECT_UUID`** — every subsequent request needs it.

### Optional: try the "others" category

The full "others" pattern needs three coordinated fields (`category` + `categoryOther` + `categoryOtherReason`):

1. `"category": "others"` alone → **expect 422** with `categoryOther is required`.
2. Add `"categoryOther": "Partnership Experiments"` → **expect 422** with `categoryOtherReason is required`.
3. Add `"categoryOtherReason": "Cross-SBU engagement that doesn't fit MSAP/MSIP/BSP."` → **expect 201**.
4. Symmetry: `"category": "MSIP"` with `"categoryOtherReason": "stray reason"` → **expect 422** because the reason field is forbidden when category is anything other than `others`.

Delete that project afterward; we focus on the first one.

---

## Step 3 — Add two milestones

**`POST /api/v3/projects/{project_uuid}/milestones/create`**:

### 3a. M1

```json
{
  "name": "M1 — Foundation",
  "description": "Auth, schemas, CRUD scaffolding",
  "startDate": "2026-05-05T09:00:00Z",
  "endDate": "2026-08-31T17:00:00Z",
  "status": "not_completed",
  "vendors": ["<INFOSYS_VENDOR_ID>"]
}
```

**Expect 201.** Copy `data.id` as `M1_ID`.

### 3b. M2

```json
{
  "name": "M2 — Rollout",
  "startDate": "2026-09-01T09:00:00Z",
  "endDate": "2026-12-15T17:00:00Z"
}
```

**Expect 201.** Copy as `M2_ID`.

**Doc 32**: every M/A/T/S create endpoint also accepts multipart on the same URL with optional `body` (comment) and `files` (uploads) fields, so the create + comment + attachments flow can be one round-trip. The JSON path above is unchanged.

---

## Step 4 — Add activities of all three types on M1

**`POST /api/v3/milestones/{milestone_id}/activities/standard/create`** (or `…/resource/count/create`, `…/resource/details/create`).

### 4a. Standard activity

```json
{
  "name": "A1 — Design REST schemas",
  "startDate": "2026-05-10T09:00:00Z",
  "endDate": "2026-06-30T17:00:00Z",
  "status": "not_completed"
}
```

**Expect 201.** Copy `data.id` as `A1_ID`.

### 4b. Resource activity in count mode

```json
{
  "name": "A2 — Need 3 engineers",
  "startDate": "2026-05-10T09:00:00Z",
  "endDate": "2026-07-31T17:00:00Z",
  "resourceCount": 3
}
```

Endpoint: `POST /api/v3/milestones/{M1_ID}/activities/resource/count/create`. **Expect 201.**

### 4c. Resource activity in details mode (full classification)

```json
{
  "name": "A3 — Onboard Designer Alice",
  "startDate": "2026-05-10T09:00:00Z",
  "endDate": "2026-07-31T17:00:00Z",
  "resource": {
    "resourceName": "Alice Kumar",
    "onboardDate": "2026-05-11T09:00:00Z",
    "offboardDate": "2026-07-25T17:00:00Z",
    "jobRole": "Backend Engineer",
    "experienceYears": 5,
    "typeOfResourceId": "<RFP_RESOURCE_TYPE_ID>",
    "division": "tmd1"
  }
}
```

Endpoint: `POST /api/v3/milestones/{M1_ID}/activities/resource/details/create`. **Expect 201.** Copy `data.id` as `A3_ID`.

### 4d. Wire `dependsOn` + exercise the guards

Make A3 depend on A1 + A2:

**`PATCH /api/v3/activities/{A3_ID}`**:
```json
{ "dependsOn": ["<A1_ID>", "<A2_ID>"] }
```
**Expect 200.**

Cycle test — try `PATCH /api/v3/activities/{A1_ID}` with `{ "dependsOn": ["<A3_ID>"] }`:
**Expect 422** "would create a cycle".

Self-edge test — `PATCH /api/v3/activities/{A1_ID}` with `{ "dependsOn": ["<A1_ID>"] }`:
**Expect 422** "An activity cannot depend on itself."

Dep-date test (doc 30) — try moving A3's start before A1's end:
```json
{ "startDate": "2026-06-01T09:00:00Z" }
```
With A1 ending 2026-06-30, **expect 422** with the offender enumeration `"A3 ... cannot start on 2026-06-01 — the following dependency target(s) end after that date: 'A1' (ends 2026-06-30)"`.

---

## Step 5 — Save → Publish

### 5a. Save

**`POST /api/v3/projects/{project_uuid}/save`** — no body. **Expect 200**, `data.status: "draft"`.

### 5b. Publish

**`POST /api/v3/projects/{project_uuid}/publish`** — admin only. **Expect 200**, `data.status: "published"`. Re-running returns **409** (already published).

**Doc 30 publish gate.** Publish rejects projects with structural gaps:
- Zero milestones → **422** with `_embedded.details.errorIdentifier = "no_milestones"`.
- Any milestone with zero live activities → **422** with `errorIdentifier = "milestone_without_activity"` and `details.milestoneNames` listing every empty milestone.

### 5c. PATCH a published project

```json
{ "description": "Rebranded: Ingestion 2.0" }
```

**Expect 200.** Published projects remain editable on whitelisted fields.

---

## Step 6 — Add tasks + subtasks directly on the project (doc 33)

Tasks now live directly under the project's activity subtree. **There is no version twin and no clone step** — that machinery was removed in doc 33 change 1.

### 6a. Add T1 under A1

**`POST /api/v3/activities/{A1_ID}/tasks/create`**:

```json
{
  "name": "T1 — Implement /versions endpoint",
  "startDate": "2026-05-15T09:00:00Z",
  "endDate": "2026-06-20T17:00:00Z"
}
```

> **Doc 15:** the task body no longer accepts `type` — the task inherits its parent activity's `type`. A1 is a `standard` activity, so T1 comes back with `type: "standard"`.

**Expect 201.** Copy `data.id` as `T1_ID`.

### 6b. Add T2 under A3 (resource activity)

**`POST /api/v3/activities/{A3_ID}/tasks/create`**:

```json
{
  "name": "T2 — Wire cascade helper",
  "startDate": "2026-05-20T09:00:00Z",
  "endDate": "2026-06-25T17:00:00Z",
  "resourceMode": "count",
  "resourceCount": 2
}
```

T2 inherits `type: "resource"` from A3, so `resourceMode` is required. **Expect 201.**

### 6c. Task `dependsOn`

```
PATCH /api/v3/tasks/{T1_ID}    body: { "dependsOn": ["<T2_ID>"] }
```
**Expect 200.** Same rules as activities: same project, no self, no cycle, no parent-hierarchy rule (doc 24 part 3). Display labels also accepted: `{ "dependsOn": ["T1.1.1.2"] }`.

### 6d. Add a subtask under T1

**`POST /api/v3/tasks/{T1_ID}/subtasks/create`**:

```json
{
  "name": "ST1 — Subtask for T1",
  "startDate": "2026-05-18T09:00:00Z",
  "endDate": "2026-06-18T17:00:00Z"
}
```

**Expect 201**. `parentSubtaskId: null`, `displayCode: "S1.1.1.1.1"`.

### 6e. Nest a subtask under ST1 (doc 24 part 2)

**`POST /api/v3/subtasks/{ST1_ID}/subtasks/create`**:

```json
{
  "name": "ST1.1 — Nested under ST1",
  "startDate": "2026-05-19T09:00:00Z",
  "endDate": "2026-06-15T17:00:00Z",
  "resourceMode": "count",
  "resourceCount": 2
}
```

**Expect 201**. `parentSubtaskId: <ST1_ID>`, `displayCode: "S1.1.1.1.1.1"`. Cap nesting via `SUBTASK_MAX_NESTING_DEPTH` env var (default unlimited).

### 6f. Activity status-completion gate

Try to mark A3 completed while A1 (a dep target) is still `not_completed`:

**`PATCH /api/v3/activities/{A3_ID}`** with `{ "status": "completed" }` → **Expect 403** with `"Cannot mark this activity as completed — the following dependency target(s) are not yet completed: 'A1 — Design REST schemas' ..."`.

Mark A1 completed first, then retry A3 → **expect 200**. The gate only passes once every dep is completed.

Reset A3 to `not_completed` before continuing.

---

## Step 7 — Vendor role demo (doc 33 change 1)

Doc 33 introduced a fourth seeded role, `vendor`, for external collaborators. They can mutate M/A/T/S, write comments, upload attachments, and read the project — but cannot create/publish/close projects, manage RBAC, or touch master data.

### 7a. Find the vendor role's id

**`GET /api/v3/master/roles`** — copy the `id` of the row with `name: "vendor"` as `VENDOR_ROLE_ID`.

### 7b. Create a vendor user

**`POST /api/v3/users/create`** (admin needed):

```json
{
  "login": "alicevendor",
  "email": "alice@infosys.example",
  "password": "vendorPass123",
  "firstName": "Alice",
  "lastName": "Vendor",
  "phoneNumber": "+919876543210",
  "vendorId": "<INFOSYS_VENDOR_ID>",
  "division": "others",
  "divisionOther": "External Vendor",
  "projectIds": ["<PROJECT_UUID>"],
  "twoFactorEnabled": false
}
```

**Expect 201.** Copy `data.id` as `VENDOR_USER_ID`. We set `twoFactorEnabled=false` so the demo can use Step 0a's single-stage login for this user.

### 7c. Assign the vendor role

**`POST /api/v3/users/{VENDOR_USER_ID}/roles/{VENDOR_ROLE_ID}`** — no body. Permission: `rbac:assign`. **Expect 201.**

### 7d. Verify effective permissions

**`GET /api/v3/users/{VENDOR_USER_ID}/permissions`** — permission: `permissions:read`.

**Expect 200**. The response lists CRUD on `milestones`, `activities`, `tasks`, `subtasks`, `comments`, `attachments`, plus `projects:read`. No `projects:create`, no `projects:publish`, no `rbac:*`, no `master_data:*`, no `users:*`.

### 7e. Log in as the vendor

Open a second Swagger tab (or use a fresh client) and log in as `alicevendor` / `vendorPass123` (single-stage path since `twoFactorEnabled=false`).

Now try:
- **`PATCH /api/v3/milestones/{M1_ID}`** with `{ "name": "M1 — Vendor edit" }` → **Expect 200**.
- **`POST /api/v3/projects/{PROJECT_UUID}/publish`** → **Expect 403** (`projects:publish` not in vendor's set).
- **`POST /api/v3/projects/create`** → **Expect 403** (`projects:create` not in vendor's set).

This proves the vendor role gates correctly. Switch back to the admin token before continuing.

---

## Step 8 — Fetch the full tree

**`GET /api/v3/projects/{project_uuid}/tree`** — admin token.

**Expect 200** with the project's full M → A → T → S hierarchy. Tasks T1 / T2 and subtasks ST1 / ST1.1 appear directly under their activities — there's no separate version subtree because versioning is gone (doc 33 change 1). Every A/T/S node carries `dependsOn` (live edges only); pass `?includeDeleted=true` to also see soft-deleted rows.

---

## Step 9 — Soft-delete the project

**`DELETE /api/v3/projects/{project_uuid}`** — admin only. **Expect 204.**

Verify the cascade:
- `GET /api/v3/projects/{project_uuid}` → **404**
- `GET /api/v3/projects/{project_uuid}/milestones` → **404**

Every M/A/T/S under the project is soft-deleted in one transaction. The audit log has per-row entries with the new `actor_role` column populated (doc 33 change 1).

The audit table is write-only at the API layer — there is no `GET /audit` endpoint. Inspect `project_audit_logs` directly via DB during dev or operational triage.

---

## Validation checklist

The happy path has demonstrated:

- **JWT auth** + admin permissions gate every write
- **Two-stage 2FA login (doc 33 change 3)** — `/login` returns `requires_otp` + `ephemeral_token`; `/login/send-otp` + `/login/verify-otp` complete the flow; per-user `twoFactorEnabled` flag overrides the global
- **Forgot-password / reset-password (doc 33 change 3)** — anti-enumeration on `/forgot-password` (always 200); single-use hashed tokens; reset clears refresh slots
- **Vendor role (doc 33 change 1)** — fourth seeded role with curated M/A/T/S CRUD; excludes lifecycle, RBAC management, master data
- **Permissions catalog grouped by module (doc 33 change 2)** — `GET /master/permissions/by-module` returns modules sorted alphabetically with each module's permissions sorted by code
- Server-generated UUID + projectCode on create
- Schema validation (422) for shape errors; service validation (422) for cross-field rules
- Category "others" + division "others" free-text pattern
- Vendor catalog + project/milestone subset rule
- Resource types catalog + resource classification columns
- Milestone status; activity status (standard-only)
- **Milestone `dependsOn`** (doc 21A) — typed edge table
- **Activity / task / subtask `dependsOn`** with existence check, self-edge rejection, cycle detection — same project, no parent-hierarchy rule (doc 24 part 3)
- **Display labels** (doc 22) — `M1` / `A1.2` / `T1.2.3` / `S1.2.3.4[.5.6…]` accepted on `dependsOn` input
- **Nested subtasks** (doc 24 part 2) — unlimited depth via `POST /api/v3/subtasks/{parent}/subtasks/create`
- **Human-readable codes** (doc 25) — `userCode` / `vendorCode`
- **`users.id` is a UUID** (doc 26)
- **Status-completion gate** on activities and milestones
- **Dep-date enforcement** (doc 30) on activities/tasks/subtasks; **milestone-specific dep-date rules** (doc 31)
- **No version twin** — doc 33 removed the entire baseline/version split. Tasks/subtasks live directly under the project; the prior `versions/create`, `suspend`, `isVersion`/`versionOf`/`baselineId`/`versionNo` fields are all gone.
- Save → publish state machine (`{new, draft} → published`)
- **Publish structural-completeness gate** (doc 30) — `no_milestones` and `milestone_without_activity` rejections
- Soft-delete cascade — single-transaction wipe of every M/A/T/S under the project
- **Audit expansion (doc 33 change 1)** — every M/A/T/S create + delete + dep-edge change records a row in `project_audit_logs` with the new `actor_role` column (admin / member / vendor / viewer)

If any step doesn't match the expected signal, the first place to look is the response error payload — the service layer returns structured `errorIdentifier` values (`invalid_field`, `invalid_publish`, `not_found`, `validation_error`, `invalid_status`) that pinpoint the rule that rejected the request. For `invalid_publish` (doc 30), inspect `_embedded.details.errorIdentifier` to distinguish `no_milestones` from `milestone_without_activity`.
