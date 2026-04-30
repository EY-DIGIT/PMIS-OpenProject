# Project

## What this represents

A single PMIS Project carries the **entire UIDAI–PMC engagement** from the day
the consultancy contract is signed to the closure of in-life project
management — a window of approximately 5.5 years (T0 + 66 months).

Why one project, not eleven? The RFP itself frames the work as a single
**Assignment** (§2.1) executed across three contractually-distinct **Phases**
(§4.4.4.d):

- **Phase 1**: Deliverables D1–D8 (T0 → T0+18m) — strategy, design, RFP, bid
- **Phase 2**: Deliverable D9 (T0+18m → T0+30m) — transition management
- **Phase 3**: Deliverable D10 (T0+18m onwards) — in-life management

Plus the parallel D11 governance tool track (T0 → T0+6m).

In PMIS those phases live as **milestones inside one project**, not separate
projects, because:
- They share one budget, one contract, one set of vendors, one team.
- They share status-transition dependencies (D9 cannot start until D8 is
  accepted, etc.).
- A single project gives one dashboard for UIDAI's Steering Committee.

Sub-projects can still be carved off later via PMIS's `parentId` if a discrete
sub-engagement (e.g. a separate PoC) is added — but not from day one.

---

## Endpoint

```
POST /api/v3/projects/create
```

Permission: `PROJECTS_CREATE` (admin).

---

## Date anchor

Today is **2026-04-29**. The PMIS project schema rejects past dates on create,
so T0 is anchored at **2026-06-01** (~one month out, within Real-World™
contract-signing horizon).

| Symbol | Date |
|---|---|
| T0  | 2026-06-01 |
| T0+3m  | 2026-09-01 |
| T0+5m  | 2026-11-01 |
| T0+6m  | 2026-12-01 |
| T0+7m  | 2027-01-01 |
| T0+9m  | 2027-03-01 |
| T0+12m | 2027-06-01 |
| T0+18m | 2027-12-01 |
| T0+30m | 2028-12-01 |
| T0+66m | 2031-12-01 |

The project's `endDate` is set to **2031-12-31** to extend slightly beyond the
last milestone for a grace period.

---

## Request body

```json
{
  "name": "UIDAI-PMC: CIDR MSP Selection & Transition",
  "description": "Project Management Consultancy engagement with UIDAI for the selection and onboarding of new MSP(s) — MSAP, MSIP, BSP — managing the Central Identities Data Repository (CIDR). Spans Phase 1 (D1–D8: strategy, design, RFP, bid management — 18 months), Phase 2 (D9: transition management — 12 months) and Phase 3 (D10: in-life project management — 48 months), with parallel D11 governance tool delivery in the first 6 months. Anchored on RFP HQ-24072/1/2023-TECH-II-HQ dated 30/05/2025.",
  "active": true,
  "isPublic": false,
  "status": "new",
  "owner": "tmd1",
  "category": "others",
  "categoryOther": "PMC",
  "categoryOtherReason": "This engagement is a Project Management Consultancy contract — not a Managed Service contract. It does not fit MSAP / MSIP / BSP, all of which describe service-provider work the PMC will help UIDAI procure rather than perform itself. Categorised as 'others/PMC' to keep the procurement governance dashboard correctly partitioned.",
  "vendorIds": [
    "<MSAP_VENDOR_UUID>",
    "<MSIP_VENDOR_UUID>",
    "<BSP_VENDOR_UUID>",
    "<PMC_VENDOR_UUID>"
  ],
  "startDate": "2026-06-01T00:00:00Z",
  "endDate": "2031-12-31T23:59:59Z"
}
```

---

## What this exercises

- **`category='others'` triple-validation**: `categoryOther` (label) + `categoryOtherReason` (governance explanation) both required and validated together.
- **`owner='tmd1'`**: the strict-division owner field added in doc 18, no `ownerOther` needed.
- **Bidirectional vendor mapping**: `vendorIds` populates the project ↔ vendor link in both directions; the four vendor records will surface this project under their `projects` collection.
- **Future-date validators**: both dates must be > now() and `endDate >= startDate`.
- **Status default**: starts as `new` (only legal initial value per the
  status-transition catalogue seeded by `init_db()`).

## Status transitions to demo after creation

The project moves through realistic states as the demo progresses:

| Step | Transition | Trigger in demo |
|---|---|---|
| 1 | `new` → `draft` | After milestones D1–D11 are created (project is being scoped) |
| 2 | `draft` → `published` | After PMU is staffed and Steering Committee approves the baseline |
| 3 | (later) `published` → `closed` | After D10's in-life management completes — only run this at the very end of the demo |

`PATCH /api/v3/projects/{id}` with `{"status": "draft"}` then
`{"status": "published"}` walks through the transitions; admin-only
`requires_admin` flag on `published → closed` exercises the RBAC gate.

## Versioning demo (optional)

After publishing, PMIS's project-version feature can be shown by:

1. `POST /api/v3/projects/{id}/versions` to spawn version `v1` (cloned milestones, activities, etc.).
2. Modify a milestone date on the version, demonstrate base/version side-by-side
   in the projection.
3. Show only one active version per baseline (the partial unique index
   `ux_projects_active_version_per_baseline`).
