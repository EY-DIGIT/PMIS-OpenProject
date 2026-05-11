# Demo Walkthrough — End-to-End Sequence

This document is the **runbook** for a live PMIS demo using the UIDAI PMC RFP
as the storyline. It calls the request bodies in `01_vendors.md` through
`07_subtasks.md` in the right order, with the right substitutions, and adds
the status-transition + versioning beats that make the demo land as a story.

> **Important — actual API paths used (verified against the deployed
> backend at http://10.1.131.199:8000)**
>
> Some endpoint paths in the per-object docs were generic conventions; the
> live API uses these specific paths:
>
> | Object | Path |
> |---|---|
> | Milestone | `POST /api/v3/projects/{project_uuid}/milestones/create` |
> | Resource types | `GET /api/v3/resource_types` (underscore) |
> | Activity (standard) | `POST /api/v3/milestones/{milestone_id}/activities/standard/create` |
> | Activity (resource/count) | `POST /api/v3/milestones/{milestone_id}/activities/resource/count/create` |
> | Activity (resource/details) | `POST /api/v3/milestones/{milestone_id}/activities/resource/details/create` |
> | Activity (transactional) | `POST /api/v3/milestones/{milestone_id}/activities/transactional/create` |
> | Project status: new → draft | `POST /api/v3/projects/{project_uuid}/save` |
> | Project status: draft → published | `POST /api/v3/projects/{project_uuid}/publish` |
> | Project status: → closed | `POST /api/v3/projects/{project_uuid}/close` |
> | Project version | `POST /api/v3/projects/{project_uuid}/versions/create` |
>
> The activity body **does not include `type`** — type is encoded in the URL.
> Each type has its own request schema (see OpenAPI for `StandardActivityCreateRequest`,
> `ResourceCountActivityCreateRequest`, `ResourceDetailsActivityCreateRequest`,
> `TransactionalActivityCreateRequest`).
>
> **Tasks and subtasks can only be created inside a project version**, not on
> the baseline. The baseline-only error is:
> `"Tasks and subtasks can only be added or modified within a version. Create a version of this baseline first."`
> So the sequence must be: publish baseline → create v1 → look up the cloned
> activity IDs in v1 → create tasks against those.
>
> **User logins must be alphanumeric, underscore, or hyphen only** —
> dots are rejected. The login `pmc.program.director` becomes
> `pmc_program_director`.

Total run time at presentation pace: **~25 minutes** (15 if you skip the
versioning + negative-path demos).

---

## 0 · Prerequisites

- App running locally: `fastapi dev app/main.py`
- Swagger UI open at `http://127.0.0.1:8000/docs` (one tab) and a terminal
  with `curl` ready (second tab).
- Bootstrap admin login known: `admin` / `<BOOTSTRAP_ADMIN_PASSWORD>` from
  `.env`.

> **Tip**: keep a scratch text file open. As you create each object, paste its
> response `id` into a labelled placeholder (e.g. `MSAP_VENDOR_UUID = …`).
> Every subsequent step needs at least one prior UUID.

---

## 1 · Authenticate as bootstrap admin (~1 min)

```
POST /api/v3/users/login
{ "login": "admin", "password": "<BOOTSTRAP_ADMIN_PASSWORD>" }
```

Capture `access_token`. In Swagger, click **Authorize** and paste it.

In curl, set:

```bash
TOKEN="<access_token>"
```

---

## 2 · Create the four vendors (~2 min)

In order — using request bodies V1 → V4 from `01_vendors.md`:

```
POST /api/v3/vendors/create  (V1: MSAP)
POST /api/v3/vendors/create  (V2: MSIP)
POST /api/v3/vendors/create  (V3: BSP)
POST /api/v3/vendors/create  (V4: PMC firm)
```

Capture each `id` into:
- `MSAP_VENDOR_UUID`
- `MSIP_VENDOR_UUID`
- `BSP_VENDOR_UUID`
- `PMC_VENDOR_UUID`

> **Demo callout**: open `GET /api/v3/vendors` after creation — show all four
> with email + contact-person fields populated (doc 18 contact-detail
> columns).

---

## 3 · Create the project (~2 min)

Using the request body in `03_project.md`. Substitute the four
`<*_VENDOR_UUID>` placeholders before sending.

```
POST /api/v3/projects/create
```

Capture response `id` into `PROJECT_UUID`.

> **Demo callouts**:
> - The `categoryOther='PMC'` + `categoryOtherReason` fields together exercise
>   the doc-18 paired-validation rule.
> - `GET /api/v3/projects/{PROJECT_UUID}/vendors` shows all four vendors
>   bidirectionally mapped (the `vendorIds` we sent populated both sides).
> - The project starts in status `new` — ready to receive milestones.

---

## 4 · Create the ten users (~5 min)

Using request bodies U1 → U10 in `02_users.md`. Substitute `vendorId` and
`projectIds` placeholders before each call.

```
POST /api/v3/users/create  (U1: UIDAI Tech Lead)
POST /api/v3/users/create  (U2: UIDAI Procurement Lead)
POST /api/v3/users/create  (U3: PMC Program Director)
POST /api/v3/users/create  (U4: PMC Program Manager)
POST /api/v3/users/create  (U5–U8: SMEs)
POST /api/v3/users/create  (U9, U10: PMU coordinators)
```

> **Demo callouts during this block**:
> - U9 + U10 use `division='others'` + `divisionOther='PMU'` → exercises the
>   strict-division paired-validator and seeds `PMU` into the divisions
>   catalogue if not already present.
> - **Negative path**: try U9 again with `divisionOther` removed → expect 422.
>   Restore the field and re-send.
> - `GET /api/v3/users` shows all 11 users (10 + bootstrap admin).
> - `GET /api/v3/projects/{PROJECT_UUID}/members` should now show all 10.

---

## 5 · Create the eleven milestones (~4 min)

Re-authenticate as `pmc.program.director` to demo a non-bootstrap admin
flow:

```
POST /api/v3/users/login
{ "login": "pmc.program.director", "password": "Demo!2026" }
```

Then for each milestone M1 → M11 from `04_milestones.md`:

```
POST /api/v3/projects/{PROJECT_UUID}/milestones
```

Capture every milestone `id`. Since later milestones reference earlier ones in
`depends`, create them in the order M1 → M11.

> **Demo callouts**:
> - The `vendors` field on each milestone is validated against the project's
>   vendor list — try sending an unrelated vendor UUID to demo the rejection.
> - `GET /api/v3/projects/{PROJECT_UUID}/milestones` shows the ordered list
>   with start/end dates, status, position.

---

## 6 · Move project to draft, then published (~2 min)

```
PATCH /api/v3/projects/{PROJECT_UUID}
{ "status": "draft" }

PATCH /api/v3/projects/{PROJECT_UUID}
{ "status": "published" }
```

> **Demo callout**: this exercises the status-transition catalogue seeded by
> `init_db()` in `app/infrastructure/db/session.py`. `GET /api/v3/projects/status-transitions` lists the legal edges.

---

## 7 · Create activities under D1 (~3 min)

Drill into D1 only (per `05_activities.md` D1 section). Eight activities:
A1–A8.

For each:

```
POST /api/v3/milestones/{M1_UUID}/activities
```

Substitute `dependsOn` placeholders with the prior activity UUIDs as you go.
For A7 (resource/details), substitute `<RESOURCE_TYPE_CONSULTANT_UUID>` from:

```
GET /api/v3/resource-types
```

(pick the row with code `consultant` or any other appropriate seed code).

> **Demo callouts**:
> - A3 + A4 exercise `type=resource` + `resourceMode=count`.
> - A7 exercises `type=resource` + `resourceMode=details` with a named
>   `ResourcePayload`.
> - Try posting A7 with a `resourceCount` field set — expect 422 (cannot mix
>   modes).
> - Try posting A7 with `division='others'` but no `divisionOther` — expect
>   422.

---

## 8 · Create activities under D7 (~3 min)

Drill into D7 (per `05_activities.md` D7 section). Ten activities A1–A10.

```
POST /api/v3/milestones/{M7_UUID}/activities
```

> **Demo callouts**:
> - A4 + A10 exercise `type=transactional` (one-shot events; no progress %).
> - A1 vs A4 contrast `standard` (status field) vs `transactional` (no
>   status).

For the remaining 9 milestones, run a single representative activity from each
(per the summary blocks in `05_activities.md`) so every milestone has at least
one activity for the timeline view.

---

## 9 · Create tasks under D1/A3 and D7/A1 (~3 min)

Per `06_tasks.md`:

```
POST /api/v3/activities/{D1_A3_UUID}/tasks/create  (T1–T4: 4 region tasks)
POST /api/v3/activities/{D7_A1_UUID}/tasks/create  (T1–T5: 5 EOI sequencing tasks)
```

Capture all task UUIDs.

> **Demo callouts**:
> - Tasks under D1/A3 inherit `type=resource` + `resourceMode=count`.
> - Tasks under D7/A1 inherit `type=standard`.
> - Show the dependency DAG: `dependsOn` references prior task UUIDs and
>   PMIS detects cycles. Try posting a self-loop on T5 (`dependsOn: [T5_UUID]`)
>   to demo cycle detection.

---

## 10 · Create subtasks (~2 min)

Per `07_subtasks.md`:

```
POST /api/v3/tasks/{D1_A3_T1_UUID}/subtasks/create  (S1–S5: 5 partner-type subtasks)
POST /api/v3/tasks/{D7_A1_T4_UUID}/subtasks/create  (S1–S3: 3 EOI section subtasks)
```

> **Demo callouts**:
> - Subtasks inherit `type` two levels up.
> - Date cascade is enforced through subtask → task → activity → milestone.
> - Try setting an S1 `endDate` past T1's `endDate` to demo cascade
>   validation.

---

## 11 · Status close-out cascade (~2 min)

Show the close-out flow on a single chain:

```
PATCH /api/v3/subtasks/{D7_A1_T4_S1_UUID}    { "status": "completed" }
PATCH /api/v3/subtasks/{D7_A1_T4_S2_UUID}    { "status": "completed" }
PATCH /api/v3/subtasks/{D7_A1_T4_S3_UUID}    { "status": "completed" }
PATCH /api/v3/tasks/{D7_A1_T4_UUID}          { "status": "completed" }
PATCH /api/v3/activities/{D7_A1_UUID}        { "status": "completed" }
```

> **Demo callout**: depending on PMIS rules, completing all child subtasks may
> auto-roll up to the parent task. Show whichever behaviour is current.

---

## 12 · (Optional) Project versioning (~3 min)

```
POST /api/v3/projects/{PROJECT_UUID}/versions
{ "name": "v1 — Steering Committee baseline" }
```

Capture `VERSION_PROJECT_UUID`. Show:

- All milestones, activities, tasks, subtasks cloned under the version.
- `GET /api/v3/projects?baseline_id={PROJECT_UUID}` lists the baseline + its
  active version.
- Modify a milestone date on the version — show the baseline is untouched.
- Try creating a second active version — should fail because of the partial
  unique index `ux_projects_active_version_per_baseline`.

---

## 13 · Tear-down (optional)

If running fresh demos, soft-delete the project:

```
DELETE /api/v3/projects/{PROJECT_UUID}
```

Then show:

- `GET /api/v3/projects` excludes it (soft-delete hides it by default).
- `GET /api/v3/projects?include_deleted=true` (admin-only) brings it back
  into the list with `deletedAt` populated.
- `POST /api/v3/projects/{PROJECT_UUID}/restore` undoes the soft delete.

---

## Story arc — what the audience should take away

1. **Real-world fit**: A 170-page government RFP collapses cleanly into one
   PMIS project with 11 milestones, ~50 activities, ~40 tasks/subtasks. The
   model isn't a toy.
2. **Ergonomic validation**: Every bad payload returns a clear 422 — the
   `division/owner/category='others'` paired-validation paths in particular
   show how PMIS keeps the catalogue clean while leaving an escape hatch.
3. **Lifecycle support**: Soft-delete + restore + versioning + status
   transitions all run on the same dataset; nothing is mocked or skipped.
4. **Multi-vendor reality**: The bidirectional vendor-project mapping means
   the procurement view and the program view stay synchronised.
5. **Governance trail**: `categoryOtherReason`, `divisionOther`, audit
   columns (`created_by`, `updated_by`, `deleted_by`) and the status-transition
   table show how every "soft" choice the program makes leaves a trace.

---

## Quick checklist (laminate-friendly)

- [ ] App running, Swagger open, terminal ready
- [ ] Bootstrap login → `TOKEN`
- [ ] V1–V4 created, UUIDs noted
- [ ] Project created, `PROJECT_UUID` noted
- [ ] U1–U10 created (incl. negative-path demo)
- [ ] M1–M11 created (depends wired)
- [ ] Project: `new` → `draft` → `published`
- [ ] D1 activities A1–A8
- [ ] D7 activities A1–A10
- [ ] One representative activity per remaining milestone
- [ ] Tasks: D1/A3 (T1–T4), D7/A1 (T1–T5)
- [ ] Subtasks: D1/A3/T1 (S1–S5), D7/A1/T4 (S1–S3)
- [ ] Close-out cascade demo
- [ ] (Optional) Versioning demo
- [ ] (Optional) Soft-delete + restore demo
