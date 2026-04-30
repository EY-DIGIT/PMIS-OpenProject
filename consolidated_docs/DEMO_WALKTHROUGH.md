# PMIS API — End-to-End Demo Walkthrough

Scope: Users, Projects, Vendors, Resource Types, Milestones, Activities, Tasks, Subtasks, Project Tree.
Excluded: project_members, roles, work_packages, work_package_types, meetings.

This walkthrough takes a fresh environment from zero to a fully versioned project with tasks on the active version, and demonstrates baseline-to-version propagation. Each step shows the Swagger UI target, the request body (copy-paste ready), and the success signal to confirm before moving on.

---

## Prerequisites

- Python 3.12 venv activated
- `pip install -r requirements.txt`
- Delete any stale `pmis.db` in the project root (fresh DB ensures seeded vendors + resource types)
- Start the server: `uvicorn app.main:app --reload`
- Open Swagger UI at `http://127.0.0.1:8000/docs`

**On first boot**, `init_db()` creates the schema and seeds:

- One admin user: `login=admin`, `password=admin123`
- Five vendors: Infosys, TCS, Wipro, Accenture, Capgemini
- Three resource types: rfp, asg, ccn
- Built-in work package types (not used in this demo)

All the dates in the bodies below are set for **2026**. Replace them with dates in your own future if this document has aged.

---

## Demo storyline

We're the admin. We'll:

1. Log in and authorize Swagger.
2. List the seeded vendors + resource types.
3. Create a baseline project (`New Ingestion Pipeline`) with a vendor attached.
4. Add two milestones under it.
5. Add activities of all three types (standard, resource/count, resource/details).
6. Hit the Save button → `new → draft`.
7. Publish → baseline is live.
8. Demonstrate that post-publish PATCH still works on the baseline.
9. Create a version of the baseline — the M/A tree clones with lineage.
10. Show that the version rejects milestone writes but accepts task writes.
11. Add tasks + subtasks under the version.
12. Edit a baseline milestone and watch it cascade to the version twin.
13. Delete a baseline activity and watch the version twin follow.
14. Suspend the version + create a second version.
15. Fetch the full project tree.
16. Soft-delete the baseline — cascades down to every M/A/T/S + every live version.

Each section says **Expect** so you can confirm success before continuing.

---

## Step 0 — Log in

**Swagger:** `Users ▸ POST /users/login`. Click **Try it out**, paste the body, **Execute**.

```json
{
  "login": "admin",
  "password": "admin123"
}
```

**Expect 200.** Copy `data.accessToken` from the response.

Click the green **Authorize** button at the top of Swagger, paste `Bearer <token>` (note the word `Bearer ` and the space), click Authorize, then Close. Every subsequent call now carries the header automatically.

---

## Step 1 — Sanity-check the catalogs

### 1a. List vendors

**`GET /vendors`** — Execute.

**Expect 200** and an `_embedded.elements` list of 5 vendors. Copy the `id` of "Infosys" (UUID) — you'll use it as `vendorId` below.
ac5a2d47-df49-4503-b27e-7f734e1c5ee9

### 1b. List resource types

**`GET /resource_types`** — Execute.

**Expect 200** with `rfp`, `asg`, `ccn`. Copy the `id` of `rfp` — you'll use it as `typeOfResourceId` on a resource activity later.
c272a938-0dc7-4aa8-8593-ca217b845020

### 1c. List status transitions catalog (added in doc 15)

**`GET /project_status_transitions`** — Execute.

**Expect 200**. The response lists every `(fromStatus, toStatus)` edge in the project lifecycle plus the seed row (`fromStatus: null, toStatus: "new"`) marking the initial status. Each row carries `requiresAdmin` and `versionOnly` flags so the FE can render context-aware next-step dropdowns. The create-project endpoint validates the `status` field against this catalog — sending `"status": "inprogress"` returns `error_type: invalid_status`.

### 1d. List project owners catalog (added in doc 15)

**`GET /project_owners`** — Execute.

**Expect 200** with the bootstrap admin pre-seeded. Only users in this whitelist are accepted as a project's `owner`. To add a new owner, an admin calls `POST /api/v3/project_owners/create` with either `{"login": "..."}` or `{"userId": N}` and an optional `displayName`. `DELETE /api/v3/project_owners/{user_id}` soft-deactivates a row (toggles `active=False`; never hard-deletes).

---

## Step 2 — Create the baseline project

**`POST /projects/create`** — Execute with:

```json
{
  "name": "New Ingestion Pipeline",
  "description": "Demo project for PMIS walkthrough",
  "owner": "admin",
  "active": true,
  "isPublic": false,
  "category": "MSIP",
  "startDate": "2026-05-01T09:00:00Z",
  "endDate": "2026-12-31T17:00:00Z",
  "vendorIds": ["<INFOSYS_VENDOR_ID>87b1c7c6-a843-41ee-95c9-1ab0cdc34178"]
}
```

**Expect 201.** The response shows a fresh UUID `data.id`, `data.projectCode` starting with `UIDAI-PR`, `data.status: "new"`, `data.isVersion: false`, and `data.vendors` listing Infosys.

**Save `data.id` as `PROJECT_UUID`** — every subsequent request will need it.
d09637f3-70db-4fe9-b1e1-1238cdc167b2

### Optional: try the "others" category

The full "others" pattern now requires THREE coordinated fields (`category` + `categoryOther` + `categoryOtherReason` — `categoryOtherReason` was added in doc 15).

1. `"category": "others"` alone → **expect 422** with `categoryOther is required`.
2. Add `"categoryOther": "Partnership Experiments"` and try again → **expect 422** with `categoryOtherReason is required`.
3. Add `"categoryOtherReason": "Cross-SBU engagement that doesn't fit MSAP/MSIP/BSP."` and try again → **expect 201**. The response shows `data.categoryOther` and `data.categoryOtherReason`.
4. To prove the symmetry: send `"category": "MSIP"` with `"categoryOtherReason": "stray reason"` → **expect 422** because the reason field is forbidden when category is anything other than `others`.

Delete that project afterward or ignore it; we focus on the first one for the rest of the demo.

---

## Step 3 — Add two milestones on the baseline

**`POST /projects/{project_uuid}/milestones/create`** — substitute `PROJECT_UUID`.

### 3a. M1

```json
{
  "name": "M1 — Foundation",
  "description": "Auth, schemas, CRUD scaffolding",
  "startDate": "2026-05-05T09:00:00Z",
  "endDate": "2026-08-31T17:00:00Z",
  "status": "not_completed",
  "vendors": ["<INFOSYS_VENDOR_ID>"ac5a2d47-df49-4503-b27e-7f734e1c5ee9]
}
```

**Note (doc 15):** the milestone create body now uses `vendors` (was `vendorIds`). The legacy `vendorIds` and `vendor_ids` aliases are still accepted on input for back-compat — Swagger displays the canonical `vendors`.

**Expect 201.** Copy `data.id` as `M1_ID`.
c98cdfe5-e14a-4464-b190-49fe7ffde8a7

### 3b. M2

```json
{
  "name": "M2 — Rollout",
  "startDate": "2026-09-01T09:00:00Z",
  "endDate": "2026-12-15T17:00:00Z"
}
```

**Expect 201.** Copy as `M2_ID`.
d642554b-71ba-4929-aa5d-6a504e7ac8c2

---

## Step 4 — Add activities of all three types on M1

**`POST /milestones/{milestone_id}/activities/create`** — substitute `M1_ID`.

### 4a. Standard activity

```json
{
  "name": "A1 — Design REST schemas",
  "type": "standard",
  "startDate": "2026-05-10T09:00:00Z",
  "endDate": "2026-06-30T17:00:00Z",
  "status": "not_completed"
}
```

**Expect 201.** Copy `data.id` as `A1_ID`. `data.dependsOn` should be `[]` (no deps yet).
4a1af992-4dd9-4352-b0ac-a856b3caaa10

### 4b. Resource activity in count mode

```json
{
  "name": "A2 — Need 3 engineers",
  "type": "resource",
  "startDate": "2026-05-10T09:00:00Z",
  "endDate": "2026-07-31T17:00:00Z",
  "resourceMode": "count",
  "resourceCount": 3
}
```

**Expect 201.**
de19e446-3671-4be4-b473-30359767a186

### 4c. Resource activity in details mode (full classification)

```json
{
  "name": "A3 — Onboard Designer Alice",
  "type": "resource",
  "startDate": "2026-05-10T09:00:00Z",
  "endDate": "2026-07-31T17:00:00Z",
  "resourceMode": "details",
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

**Expect 201.** `data.resource` echoes the classification columns. Copy `data.id` as `A3_ID`.
79dc2688-36b1-48b0-9804-eb7660bda11f

### 4d. Show the "others" idiom on division

```json
{
  "name": "A4 — Onboard engineer, special program",
  "type": "resource",
  "startDate": "2026-05-10T09:00:00Z",
  "endDate": "2026-07-31T17:00:00Z",
  "resourceMode": "details",
  "resource": {
    "resourceName": "Bob Pereira",
    "jobRole": "Integration Lead",
    "typeOfResourceId": "<RFP_RESOURCE_TYPE_ID>",
    "division": "others",
    "divisionOther": "Beta Program"
  }
}
```

**Expect 201**. Copy `data.id` as `A4_ID`. If you change `division` to `tmd1` while keeping `divisionOther` set, you should get **422** — that's the "others" pattern enforced.
b33f9ad7-1f37-4709-a08f-0b5ff0abfd51

### 4e. Wire `dependsOn` between activities

Make A3 depend on A1 and A2 (arbitrary, for illustration). First let's also grab A2's id by re-reading the milestone's activities list:

**`GET /milestones/{M1_ID}/activities`** — copy A2's id as `A2_ID` (the resource/count-mode one).

Then **`PATCH /activities/{A3_ID}`**:

```json
{
  "dependsOn": [
    "<A1_ID>4a1af992-4dd9-4352-b0ac-a856b3caaa10",
    "<A2_ID>de19e446-3671-4be4-b473-30359767a186"
  ]
}
```

**Expect 200.** `data.dependsOn` should be a sorted list containing both ids.

### Bonus: dep history survives a remove

Clear all of A3's dependencies via **`PATCH /activities/{A3_ID}`** with `{ "dependsOn": [] }` — **expect 200**, `data.dependsOn` is `[]`. Then re-add them via `{ "dependsOn": ["<A1_ID>", "<A2_ID>"] }` — **expect 200** again. The DB now has two soft-deleted rows plus two fresh live rows for those pairs; the API shows the live pair. You won't see the history through the API, but `project_audit_logs` and the `activity_dependencies` table itself preserve it for auditing.

Now test the **cycle check** — try to make A1 depend on A3:

**`PATCH /activities/{A1_ID}`**:

```json
{
  "dependsOn": ["<A3_ID>79dc2688-36b1-48b0-9804-eb7660bda11f"]
}
```

**Expect 422** with `"Adding dependency on '<A3_ID>' would create a cycle."` (A1 → A3 → A1 would close the loop since A3 depends on A1).

Test the **self-edge rejection** — try `"dependsOn": ["<A1_ID>"]` on A1:

**Expect 422** with `"An activity cannot depend on itself."`.

---

## Step 5 — Try to add a task on the baseline (should fail)

**`POST /activities/{activity_id}/tasks/create`** — substitute `A1_ID`.

```json
{
  "name": "T? — Should fail on baseline",
  "type": "standard",
  "startDate": "2026-05-15T09:00:00Z",
  "endDate": "2026-06-15T17:00:00Z"
}
```

**Expect 403** with the message "Tasks and subtasks can only be added or modified within a version. Create a version of this baseline first." This is the baseline/version guard in action.

---

## Step 6 — Save Project (new → draft)

**`POST /projects/{project_uuid}/save`** — execute with no body.

**Expect 200** and `data.status: "draft"`. Re-running it is a no-op (still 200, still `draft`).

If you try it on a project with zero milestones, you'd get **422** with the message mentioning milestones.

---

## Step 7 — Publish

**`POST /projects/{project_uuid}/publish`**.

**Expect 200** and `data.status: "published"`. Running it again returns **409** (already published).

---

## Step 8 — PATCH a published baseline

Show that published baselines are still editable.

**`PATCH /projects/{project_uuid}`**:

```json
{
  "description": "Rebranded: Ingestion 2.0"
}
```

**Expect 200** and the new description. (Before the Doc-12 change this would have been 409.) The edit doesn't cascade anywhere because project-level edits stay scoped to the baseline; only M/A edits propagate.

---

## Step 9 — Create a version

**`POST /projects/{project_uuid}/versions/create`** — execute with no body.

**Expect 201** with a fresh `data.id` (different UUID), new `data.projectCode`, `data.isVersion: true`, `data.versionNo: 1`, `data.status: "new"`.

**Save `data.id` as `VERSION_UUID`.**
1a04ad15-9cd2-4f31-88c9-bfc0d33d0259

Running the same call again returns **409** (only one active version per baseline).

---

## Step 10 — Inspect the version's cloned M/A

**`GET /projects/{version_uuid}/milestones`** — substitute `VERSION_UUID`.

**Expect 200** showing two milestones (M1 and M2 clones) under the version. Their `id` is fresh (UUIDs differ from the baseline); `cloned_from_id` is not surfaced in the API but is set in the DB.

Pick M1's clone and get its activities via `GET /milestones/{id}/activities` — you should see A1, A2, A3, A4 all present with fresh ids. Check `dependsOn` on the version's A3 clone — the **live** edges from Step 4e were cloned too, so it should reference the **version's** A1 and A2 clones (the ids are rewritten; they are not the baseline ids). Historical (soft-deleted) edges on the baseline are not carried forward.

**Save M1's clone id** as `VERSION_M1_ID`.
d6f17ac9-e5c7-4630-9338-6958841158db

**Save A1's clone id** as `VERSION_A1_ID`.
0f64024a-1488-4a08-9c02-f33a872bdbd4

**Save A3's clone id** as `VERSION_A3_ID`.
0361314d-0fab-493c-80a8-99892eaa5042

---

## Step 11 — Try to add a milestone on the version (should fail)

**`POST /projects/{version_uuid}/milestones/create`** with any valid body.

**Expect 403** with message "Milestones and activities can only be added or modified on the baseline project, not on a version. Apply the change on the baseline — it will propagate to active versions automatically." This is the other half of the baseline/version split.

---

## Step 12 — Add tasks + subtasks under the version

Tasks live only on versions.

### 12a. Add T1 under `VERSION_A1_ID` and T2 under `VERSION_A3_ID`

**Note (doc 15 change):** the task create body no longer accepts `type`. The task inherits its parent activity's type. Since both VERSION_A1 and VERSION_A3 are `standard` activities here, T1 and T2 will both come back with `type: "standard"`.

**`POST /activities/{VERSION_A1_ID}/tasks/create`**:

```json
{
  "name": "T1 — Implement /versions endpoint",
  "startDate": "2026-05-15T09:00:00Z",
  "endDate": "2026-06-20T17:00:00Z"
}
```

**Expect 201.** Copy `data.id` as `T1_ID`. `data.type` should read `"standard"` — inherited from the parent activity.
6767ad13-684e-4936-a95d-382ad5b075a1

**`POST /activities/{VERSION_A3_ID}/tasks/create`**:

```json
{
  "name": "T2 — Wire cascade helper",
  "startDate": "2026-05-20T09:00:00Z",
  "endDate": "2026-06-25T17:00:00Z"
}
```

**Expect 201.** Copy `data.id` as `T2_ID`.
d8c27bd7-137b-4ef7-9342-3ddc765ee75c

If you tried to create a task under a `resource` activity without supplying `resourceMode`, you'd get **422** — the inherited type is `resource`, so `resourceMode` (and the matching count or details body) is required. Same constraint as activities, just applied per the parent's type.

### 12b. Task dependsOn with hierarchy check

Try to make T1 depend on T2 via **`PATCH /tasks/{T1_ID}`**:

```json
{ "dependsOn": ["<T2_ID>d8c27bd7-137b-4ef7-9342-3ddc765ee75c"] }
```

This should succeed. Why? Because T1 lives under VERSION_A1 and T2 lives under VERSION_A3, and from Step 4e (cloned into the version) VERSION_A3 depends on VERSION_A1 — **but** the hierarchy rule says the source's parent activity must depend on the target's parent activity. Since T1's parent (VERSION_A1) does NOT depend on T2's parent (VERSION_A3) — the dependency goes the other way — this will fail.

**Expect 422** with `"Cannot add task dependency on task '<T2_ID>': the source's parent activity does not depend on that task's parent activity. Add the activity-level dependency first."`.

Now reverse it — make T2 depend on T1 via **`PATCH /tasks/{T2_ID}`**:

```json
{ "dependsOn": ["<T1_ID>"] }
```

**Expect 200.** This works because T2's parent (VERSION_A3) → VERSION_A1 (T1's parent) is a valid activity-level edge.

### 12c. Add a subtask under `T1_ID`

**`POST /tasks/{task_id}/subtasks/create`** — substitute `T1_ID`:

```json
{
  "name": "ST1 — Subtask for T1",
  "type": "resource",
  "startDate": "2026-05-18T09:00:00Z",
  "endDate": "2026-06-18T17:00:00Z",
  "resourceMode": "details",
  "resource": {
    "resourceName": "Carla Dias",
    "jobRole": "Senior Engineer",
    "experienceYears": 8
  }
}
```

**Expect 201.** Copy `data.id` as `ST1_ID`.

### 12d. Activity status-completion gate

Try to mark VERSION_A3 as completed while VERSION_A1 (one of its deps) is still `not_completed`:

**`PATCH /activities/{VERSION_A3_ID}`**:

```json
{ "status": "completed" }
```

**Expect 403** with `"Cannot mark this activity as completed — the following dependency target(s) are not yet completed: 'A1 — Design REST schemas' ..."`.

Now mark VERSION_A1 as completed first:

**`PATCH /activities/{VERSION_A1_ID}`** with `{ "status": "completed" }` — **expect 200**. Then retry the A3 patch — **expect 200** this time. The gate only passes once every dep is completed.

Reset A3 back to `not_completed` before moving on so the rest of the demo stays clean.

---

## Step 13 — Baseline M edit propagates to version

**`PATCH /milestones/{milestone_id}`** on the BASELINE `M1_ID`:

```json
{
  "name": "M1 — Foundation (renamed)",
  "description": "Post-publish rename on baseline"
}
```

**Expect 200.** Now check the version's M1 clone:

**`GET /milestones/{milestone_id}`** on `VERSION_M1_ID`.

**Expect 200** with `data.name == "M1 — Foundation (renamed)"`. The rename cascaded.

If you had updated only `status`, the version would **not** have picked it up — status is version-local. You can verify by PATCHing `{ "status": "completed" }` on the baseline M1 and then GETting the version M1 — baseline shows `completed`, version still shows `not_completed`.

---

## Step 14 — Baseline A delete cascades to version

**`DELETE /activities/{activity_id}`** on the BASELINE `A1_ID`.

**Expect 204** (or 200 depending on client). Now `GET /milestones/{VERSION_M1_ID}/activities`.

**Expect 200** and the version's A1 clone is **no longer** in the list (soft-deleted). A2, A3, A4 clones are still present.

---

## Step 15 — Suspend the version + spawn a second one

### 15a. Suspend

**`POST /projects/{version_uuid}/suspend`** — `VERSION_UUID`.

**Expect 200** and `data.status: "suspended"`. The version is now dormant.

### 15b. Create version 2

**`POST /projects/{project_uuid}/versions/create`** — `PROJECT_UUID` (the baseline).

**Expect 201** with `data.versionNo: 2`. This works because the previous version was suspended, freeing the active-version slot.

### 15c. Propagation skips suspended versions

**`PATCH /milestones/{milestone_id}`** on the baseline `M1_ID`:

```json
{
  "name": "M1 — Foundation (final)"
}
```

**Expect 200.** GET V1's M1 clone — name is still "M1 — Foundation (renamed)" (unchanged). GET V2's M1 clone — name is "M1 — Foundation (final)". The cascade reached V2 (active) but skipped V1 (suspended).

---

## Step 16 — Fetch the full tree

**`GET /projects/{project_uuid}/tree`** — `PROJECT_UUID`.

**Expect 200** with the baseline's full M → A → T → S hierarchy. T/S are always empty on the baseline (Step 5 proved you can't add them). Every A/T/S node carries a `dependsOn: []` array (baseline still has the Step 4e edges between A3→{A1, A2}, the others are empty). Try the same on `VERSION_UUID_2` (V2) — you'll see a clone with T1/T2/ST1 **not** present (those exist only on V1 and were cloned per-version).

Pass `?includeDeleted=true` to also see the soft-deleted A1 on the baseline.

---

## Step 17 — Soft-delete the baseline

**`DELETE /projects/{project_uuid}`** — `PROJECT_UUID` (the baseline).

**Expect 204.** Now verify the cascade:

- `GET /projects/{project_uuid}` → **404**
- `GET /projects/{VERSION_UUID_1}` → **404** (was active; deleted as part of baseline cascade)
- `GET /projects/{VERSION_UUID_2}` → **404** (same)
- `GET /projects/{project_uuid}/milestones` → **404**

Everything under the baseline — M/A/T/S plus every live version and **its** subtree — is soft-deleted in one transaction. The audit log has per-row entries tagged `cascaded_from_baseline_id`.

---

## Validation checklist

The happy path has demonstrated:

- JWT auth + admin permissions gate every write
- Server-generated UUID + projectCode on create
- Schema validation (422) for shape errors; service validation (422) for cross-field rules
- Category "others" + division "others" free-text pattern
- Vendor catalog + project/milestone subset rule
- Resource types catalog + resource classification columns
- Milestone status/depends (pass-through); activity status (standard-only)
- **Activity `dependsOn`** with existence check, self-edge rejection, cycle detection
- **Task/subtask `dependsOn`** with the hierarchy rule (parent must already depend)
- **Status-completion gate** on activities (can't mark completed with incomplete deps)
- Save Project (`new → draft`) wired to the milestone-exists gate
- Publish state machine (`{new, draft} → published`, admin only, idempotent with 409 on re-publish)
- Published baselines remain editable on PATCH
- Version creation (201; only-one-active invariant; 409 on duplicate)
- Baseline/version level guards (403 on task writes on baseline; 403 on M/A writes on version)
- Baseline M/A create/update/delete propagates to active versions with cascade audit
- Dependency edges are cloned at version creation with id-rewrites; versions evolve independently from baseline edges
- Dependency edges themselves follow soft-delete semantics — removed rows stay in the table with `deleted_at` stamped, a partial unique index keeps only one live row per pair, and re-adding a removed edge inserts a fresh row so history is preserved
- Status / dependency edges are version-local and do NOT propagate
- Suspended versions are dormant — no propagation
- Soft-delete of baseline cascades to every live version + their subtrees in one txn
- Deleting an M/A/T/S row soft-deletes every dependency edge that touches it (source or target)

If any step doesn't match the expected signal, the first place to look is the response error payload — the service layer returns structured `errorIdentifier` values (`invalid_field`, `project_locked`, `invalid_transition`, `not_found`, `validation_error`) that pinpoint the rule that rejected the request.
