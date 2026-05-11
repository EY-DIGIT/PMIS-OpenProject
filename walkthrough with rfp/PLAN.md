# PMIS Demo Walkthrough — UIDAI PMC RFP

## Source RFP

- **Title**: Request for Proposal — Hiring of Project Management Consultancy (PMC) for selection and on-boarding of MSP(s) {Managed Service Provider(s)}
- **RFP No.**: HQ-24072/1/2023-TECH-II-HQ
- **Issuer**: Unique Identification Authority of India (UIDAI), MeitY
- **Dated**: 30/05/2025
- **Pages**: 170

The RFP commissions a Project Management Consultancy to lead UIDAI through the
selection and onboarding of new Managed Service Providers (MSPs) for the
Central Identities Data Repository (CIDR) — covering the existing MSAP
(Application & Production), MSIP (Infrastructure), and BSP (Biometric Service
Provider) ecosystems.

The consultancy spans **30 months of active work plus an in-life management
phase of ~4 years** and delivers a fixed catalogue of eleven deliverables
(D1–D11), each with its own timeline, payment weight, and acceptance criteria.

This walkthrough maps that RFP onto the PMIS object model and produces a
ready-to-load demo dataset.

---

## Why this RFP fits PMIS well

- **Clear deliverables → milestones**: D1–D11 map 1:1 to PMIS milestones with
  defined start/end dates anchored on T0 (contract signing).
- **Sub-deliverables → activities**: Each D-section in §4.2 of the RFP
  enumerates 5–15 sub-tasks (4.2.1.a, 4.2.1.b, …) that translate naturally into
  PMIS activities with `type=standard` or `type=resource`.
- **Resource-heavy work → resource activities**: PMC sub-units at UIDAI HO and
  Tech Centre Bengaluru match PMIS's `type=resource` activity with
  `resourceMode=details` (named consultant) or `resourceMode=count` (pool
  staffing).
- **Multiple vendors → vendor mapping**: 3 incumbent MSPs + 1 PMC firm + future
  MSPs to be selected exercises the vendor-project bidirectional mapping.
- **Onsite + offsite split → divisions**: Tech work → `tmd1`; procurement &
  legal → `tmd2`; the cross-functional PMU → `others` ("PMU").

---

## How the RFP is broken down

### 1 Project (top level)

A single PMIS Project represents the entire UIDAI-PMC engagement.

| Field | Value |
|---|---|
| name | UIDAI-PMC: CIDR MSP Selection & Transition |
| category | `others` (`categoryOther` = "PMC", reason explains why) |
| owner | `tmd1` (UIDAI Technology Division) |
| status | `new` → `published` once milestones are baselined |
| startDate / endDate | 2026-06-01 → 2031-12-31 (T0 + 5y6m) |

T0 (contract signing) is anchored at **2026-06-01** so all dates remain in the
future relative to today (2026-04-29) and pass the project schema's
`must-be-future` validators.

### 2 Vendors (4)

| Slot | Vendor | Role in demo |
|---|---|---|
| Incumbent | MSAP Operations Pvt Ltd | Current Application & Production MSP |
| Incumbent | MSIP Infrastructure Solutions Ltd | Current Infrastructure MSP |
| Incumbent | BSP Biometric Systems Ltd | Current Biometric Service Provider |
| Engaged | Aadhaar Project Consultancy LLP | The PMC bidder who won this contract |

All four are mapped to the project (`projectIds` on vendor create), so the
project's `/vendors` endpoint surfaces all of them.

### 3 Users (10)

Two populations:

- **PMC team (vendor: Aadhaar Project Consultancy LLP)** — Program Director
  (admin), Project Manager, 4 SMEs, 2 PMU coordinators.
- **UIDAI stakeholders (vendor: one of the incumbents, division `tmd1`)** —
  Tech Lead (admin) and Procurement Lead.

Every user maps to the demo project via `projectIds`. Divisions are spread:
- `tmd1` for technology profiles
- `tmd2` for procurement / legal
- `others` (`divisionOther` = "PMU") for the dedicated Project Management Unit
  staff — exercises the `division='others'` validation path

### 4 Milestones (11 — D1 through D11)

Each RFP deliverable becomes one milestone. Dates are computed from T0:

| ID | Code | Name | Start | End |
|---|---|---|---|---|
| 1 | D1 | AS-IS implementation report | T0 | T0+3m |
| 2 | D2 | Project documents repository + KM plan | T0 | T0+3m |
| 3 | D3 | Program Management Strategy & Roadmap | T0 | T0+5m |
| 4 | D4 | Detailed Project Report (DPR) | T0 | T0+5m |
| 5 | D5 | DR + BCP plan | T0+3m | T0+7m |
| 6 | D6 | Functional & technical specs (CIDR IT) | T0+5m | T0+9m |
| 7 | D7 | RFPs for MSP selection (incl. EOI) | T0+7m | T0+12m |
| 8 | D8 | Bid management & contract signing | T0+9m | T0+18m |
| 9 | D9 | Transition Management | T0+18m | T0+30m |
| 10 | D10 | In-life Project Management | T0+18m | T0+66m |
| 11 | D11 | Governance Automation Tool | T0 | T0+6m |

`depends` chain: D5 depends on D1; D6 on D3+D4; D7 on D6; D8 on D7; D9 on D8;
D10 on D9. D11 is parallel.

### 5 Activities (per milestone)

Each milestone is broken into the sub-deliverables explicitly listed in
§4.2.x.x of the RFP. The walkthrough shows two milestones in **full depth**
(D1 — AS-IS report, and D7 — RFP authoring) with 6–10 activities each, and
the remaining 9 milestones at **summary depth** (3–5 representative
activities) so the dataset is complete without becoming unmanageable.

Three activity types are exercised:
- `standard` — for analysis/reporting work (most D1, D2, D3 items)
- `resource` (mode=details) — for named SME deployments (PMU staffing,
  workshops)
- `resource` (mode=count) — for pool-staffed activities (e.g. ecosystem visits
  to AUAs/KUAs)
- `transactional` — for one-shot events (e.g. contract signing in D8, EOI
  publication in D7)

### 6 Tasks + Subtasks

Two tasks-in-depth examples are walked through:

- D1's "Visit ecosystem partners" activity → 4 tasks (one per region:
  North/South/East/West) → subtasks per partner type (AUA, KUA, Registrar, ASK,
  Contact Centre).
- D7's "Prepare EOI document" activity → 5 tasks (Draft, Internal review, UIDAI
  review, Revisions, Final publication) → subtasks for each section of the EOI.

The dependency model is exercised: each region-task `dependsOn` the
"Stakeholder mapping" task; subtask dependencies cascade similarly under their
parent task.

---

## Folder layout

```
walkthrough with rfp/
├── PLAN.md                       ← this file
└── objects/
    ├── 01_vendors.md
    ├── 02_users.md
    ├── 03_project.md
    ├── 04_milestones.md
    ├── 05_activities.md
    ├── 06_tasks.md
    ├── 07_subtasks.md
    └── 08_walkthrough_sequence.md
```

Each object document contains:
- A short narrative on what the object represents in this RFP
- One or more **POST request bodies** as JSON, ready to paste into Swagger or
  curl
- The endpoint path each body targets
- Notes on the validation rules being exercised (e.g. "this exercises the
  `owner='others'` + `ownerOther` paired requirement")

`08_walkthrough_sequence.md` ties everything together with the exact order to
fire the requests during a live demo (vendors → users → project → milestones →
activities → tasks → subtasks → status transitions → versioning) so the demo
reads as a coherent story end-to-end.
