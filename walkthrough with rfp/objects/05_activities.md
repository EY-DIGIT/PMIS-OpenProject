# Activities

## Mapping strategy

The RFP itemises sub-deliverables under each D-section (e.g. §4.2.1.a through
§4.2.1.j for D1). Each becomes one PMIS activity under the corresponding
milestone.

Three RFP items + three PMIS activity types map cleanly:

| RFP wording | PMIS activity type | Why |
|---|---|---|
| Analysis / report / study / evaluation | `standard` | Time-boxed knowledge work, no headcount metric. |
| Onsite SME deployment / PMU staffing / workshops | `resource` | Headcount-driven; tracks named consultants or pooled count. |
| One-shot events (publication, signing, switchover drill) | `transactional` | Atomic, no progress %. |

This document shows **D1 in full** and **D7 in full** (the two milestones
called out in `PLAN.md` for in-depth walkthrough), then a representative
sample for the remaining nine milestones.

---

## Endpoint

```
POST /api/v3/milestones/{milestone_id}/activities
```

Permission: project-edit access (members + admins).

For `type=resource` activities, the resource sub-payload exercises the
`resource_types` catalogue (`typeOfResourceId` references the seed).
`resourceMode='details'` carries a named `ResourcePayload`; `resourceMode='count'`
carries `resourceCount` and skips the named-person details.

For `type=resource` + `resourceMode=details`, the `resource.division` field
exercises the same `tmd1 / tmd2 / others` enum used on users — including
`division='others'` + `divisionOther='PMU'` for PMU-staffed work.

---

## D1 — AS-IS Implementation Report (full breakdown)

The RFP's §4.2.1 lists ten sub-items (4.2.1.a → 4.2.1.j). Mapped below.

### A1 — Stakeholder mapping and study planning  *(standard)*

```json
{
  "name": "Stakeholder mapping across UIDAI HO, technology centres, regional and state offices",
  "description": "Conducted per RFP §4.2.1.a + §4.2.1.c. Catalogue all internal stakeholders to be interviewed before fieldwork begins.",
  "type": "standard",
  "status": "not_completed",
  "startDate": "2026-06-01T00:00:00Z",
  "endDate": "2026-06-15T00:00:00Z",
  "position": 1,
  "dependsOn": []
}
```

### A2 — AS-IS technology assessment  *(standard)*

```json
{
  "name": "AS-IS assessment of CIDR — technology, architecture, hardware, networking, applications, business processes",
  "description": "Per RFP §4.2.1.b. Capture current implementation baseline including challenges in governance, inter-MSP coordination and performance.",
  "type": "standard",
  "status": "not_completed",
  "startDate": "2026-06-08T00:00:00Z",
  "endDate": "2026-07-15T00:00:00Z",
  "position": 2,
  "dependsOn": ["<A1_UUID>"]
}
```

### A3 — Visit ecosystem partners  *(resource — count)*

```json
{
  "name": "Visit ecosystem partners (AUAs, KUAs, Registrars, ASKs, contact centres) on a sample basis",
  "description": "Per RFP §4.2.1.d. At least one ecosystem partner visited in every region. Pool-staffed by PMC field consultants.",
  "type": "resource",
  "resourceMode": "count",
  "resourceCount": 4,
  "startDate": "2026-06-15T00:00:00Z",
  "endDate": "2026-07-30T00:00:00Z",
  "position": 3,
  "dependsOn": ["<A1_UUID>"]
}
```

### A4 — Visit UIDAI units  *(resource — count)*

```json
{
  "name": "Visit all UIDAI units — HO, regional offices, state offices, data centres",
  "description": "Per RFP §4.2.1.e. Pool-staffed by PMC field consultants.",
  "type": "resource",
  "resourceMode": "count",
  "resourceCount": 4,
  "startDate": "2026-06-15T00:00:00Z",
  "endDate": "2026-07-30T00:00:00Z",
  "position": 4,
  "dependsOn": ["<A1_UUID>"]
}
```

### A5 — Infrastructure scalability evaluation  *(standard)*

```json
{
  "name": "Evaluate infrastructure ability to scale up to meet growing demand and performance requirements",
  "description": "Per RFP §4.2.1.f. Output feeds the DPR (D4) sizing model.",
  "type": "standard",
  "status": "not_completed",
  "startDate": "2026-07-01T00:00:00Z",
  "endDate": "2026-07-31T00:00:00Z",
  "position": 5,
  "dependsOn": ["<A2_UUID>"]
}
```

### A6 — Existing-contract review  *(standard)*

```json
{
  "name": "Review current MSAP, MSIP and BSP contractual provisions for improvement areas",
  "description": "Per RFP §4.2.1.g. Identify clauses to be carried forward, improved or dropped in the new MSP contract(s).",
  "type": "standard",
  "status": "not_completed",
  "startDate": "2026-07-01T00:00:00Z",
  "endDate": "2026-07-31T00:00:00Z",
  "position": 6,
  "dependsOn": []
}
```

### A7 — Risk assessment + management plan  *(resource — details, named SME)*

```json
{
  "name": "Risk identification, assessment and management plan for CIDR + UIDAI ecosystem",
  "description": "Per RFP §4.2.1.h + §4.2.1.i. Owner: PMC SME — DR/BCP. Methodology covers physical/environmental, fraud, logical, communication, natural and technological threats; both qualitative and quantitative analysis.",
  "type": "resource",
  "resourceMode": "details",
  "resource": {
    "resourceName": "Sandeep Varma",
    "position": "SME — Disaster Recovery & BCP",
    "designation": "Senior Risk Consultant",
    "jobRole": "Risk Assessment Lead",
    "qualification": "M.Tech (Computer Science), CISA, ISO 22301 LA",
    "experienceYears": "16",
    "typeOfResourceId": "<RESOURCE_TYPE_CONSULTANT_UUID>",
    "division": "tmd1",
    "onboardDate": "2026-07-01T00:00:00Z",
    "offboardDate": "2026-08-15T00:00:00Z"
  },
  "startDate": "2026-07-01T00:00:00Z",
  "endDate": "2026-08-15T00:00:00Z",
  "position": 7,
  "dependsOn": ["<A2_UUID>"]
}
```

### A8 — AS-IS report drafting & submission  *(standard)*

```json
{
  "name": "Prepare and submit consolidated AS-IS report on existing implementation, challenges and improvement areas",
  "description": "Per RFP §4.2.1.j. Final deliverable for D1 — synthesises A1–A7 outputs.",
  "type": "standard",
  "status": "not_completed",
  "startDate": "2026-08-01T00:00:00Z",
  "endDate": "2026-09-01T00:00:00Z",
  "position": 8,
  "dependsOn": ["<A2_UUID>", "<A3_UUID>", "<A4_UUID>", "<A5_UUID>", "<A6_UUID>", "<A7_UUID>"]
}
```

---

## D7 — RFPs for MSP Selection (full breakdown)

The RFP's §4.2.7 splits this into (a) EOI conduct and (b) RFP authoring,
each with multiple sub-items.

### A1 — Draft EOI document  *(standard)*

```json
{
  "name": "Draft Expression of Interest (EOI) — project description, scope, eligibility, PQ criteria, certifications",
  "description": "Per RFP §4.2.7.a.i. Sections A through H per the RFP enumeration.",
  "type": "standard",
  "status": "not_completed",
  "startDate": "2027-01-01T00:00:00Z",
  "endDate": "2027-01-31T00:00:00Z",
  "position": 1,
  "dependsOn": []
}
```

### A2 — Internal PMC review  *(standard)*

```json
{
  "name": "Internal PMC review of EOI by Program Director and SMEs",
  "description": "Sign-off by Program Director (RFP §4.2.10.a.iv requirement). Iterative.",
  "type": "standard",
  "status": "not_completed",
  "startDate": "2027-01-25T00:00:00Z",
  "endDate": "2027-02-05T00:00:00Z",
  "position": 2,
  "dependsOn": ["<A1_UUID>"]
}
```

### A3 — UIDAI review and acceptance of EOI  *(standard)*

```json
{
  "name": "UIDAI review of EOI; incorporate revisions to acceptance",
  "description": "Per RFP §4.2.7.b.ii (paraphrased, applies equally to EOI). UIDAI nodal divisions sign acceptance per RFP §5.21.",
  "type": "standard",
  "status": "not_completed",
  "startDate": "2027-02-05T00:00:00Z",
  "endDate": "2027-02-28T00:00:00Z",
  "position": 3,
  "dependsOn": ["<A2_UUID>"]
}
```

### A4 — Publish EOI  *(transactional)*

```json
{
  "name": "Publish accepted EOI on GeM portal / agreed platform",
  "description": "Per RFP §4.2.8.a.i. Atomic publication event.",
  "type": "transactional",
  "startDate": "2027-03-01T00:00:00Z",
  "endDate": "2027-03-01T00:00:00Z",
  "position": 4,
  "dependsOn": ["<A3_UUID>"]
}
```

### A5 — EOI evaluation and shortlist  *(resource — details, SME Procurement)*

```json
{
  "name": "EOI evaluation and shortlisting of prospective bidders",
  "description": "Per RFP §4.2.7.a.ii. PMC SME (Procurement) leads with UIDAI Procurement Lead.",
  "type": "resource",
  "resourceMode": "details",
  "resource": {
    "resourceName": "Neha Kapoor",
    "position": "SME — Procurement & Legal",
    "designation": "Lead Procurement Consultant",
    "jobRole": "EOI Evaluation Lead",
    "qualification": "MBA (Procurement), LLB",
    "experienceYears": "14",
    "typeOfResourceId": "<RESOURCE_TYPE_CONSULTANT_UUID>",
    "division": "tmd2",
    "onboardDate": "2027-03-15T00:00:00Z",
    "offboardDate": "2027-04-15T00:00:00Z"
  },
  "startDate": "2027-03-15T00:00:00Z",
  "endDate": "2027-04-15T00:00:00Z",
  "position": 5,
  "dependsOn": ["<A4_UUID>"]
}
```

### A6 — Determine number of RFPs required  *(standard)*

```json
{
  "name": "Recommend number and scope of RFPs to be issued",
  "description": "Per RFP §4.2.7.b.i. Output: 1, 2 or 3 RFPs depending on bundling strategy from D4 DPR.",
  "type": "standard",
  "status": "not_completed",
  "startDate": "2027-02-15T00:00:00Z",
  "endDate": "2027-03-15T00:00:00Z",
  "position": 6,
  "dependsOn": []
}
```

### A7 — Author RFP — scope of work and project description  *(standard)*

```json
{
  "name": "Author RFP — Project background, scope, objectives, key stakeholders, exclusions",
  "description": "Per RFP §4.2.7.b.iii.A through §4.2.7.b.v. Includes 14 sub-items of broad scope (CIDR management, IT infra procurement, replication, ISMS, testing, training, ops & support, etc.).",
  "type": "standard",
  "status": "not_completed",
  "startDate": "2027-03-01T00:00:00Z",
  "endDate": "2027-04-15T00:00:00Z",
  "position": 7,
  "dependsOn": ["<A6_UUID>"]
}
```

### A8 — Author RFP — SLAs, payment schedule, legal terms  *(resource — details, SME Procurement)*

```json
{
  "name": "Author RFP — SLAs, payment schedule, legal/contractual terms (Aadhaar Act 2016 compliance)",
  "description": "Per RFP §4.2.7.b.xv (SLA design, calculation principles, severity levels, LD %, downtime/uptime, peak-hour service levels, LD capping, payment-component mapping) and §4.2.7.b.xiv (legal terms per GoI procurement norms).",
  "type": "resource",
  "resourceMode": "details",
  "resource": {
    "resourceName": "Neha Kapoor",
    "position": "SME — Procurement & Legal",
    "designation": "Lead Procurement Consultant",
    "jobRole": "RFP Author — SLA & Legal",
    "qualification": "MBA (Procurement), LLB",
    "experienceYears": "14",
    "typeOfResourceId": "<RESOURCE_TYPE_CONSULTANT_UUID>",
    "division": "tmd2",
    "onboardDate": "2027-04-01T00:00:00Z",
    "offboardDate": "2027-05-15T00:00:00Z"
  },
  "startDate": "2027-04-01T00:00:00Z",
  "endDate": "2027-05-15T00:00:00Z",
  "position": 8,
  "dependsOn": ["<A6_UUID>"]
}
```

### A9 — RFP presentations to UIDAI  *(standard)*

```json
{
  "name": "Make detailed RFP presentations to UIDAI; iterate to acceptance",
  "description": "Per RFP §4.2.7.b.ii. PMC presents draft RFP to UIDAI evaluation committee; revise to acceptance.",
  "type": "standard",
  "status": "not_completed",
  "startDate": "2027-05-01T00:00:00Z",
  "endDate": "2027-05-25T00:00:00Z",
  "position": 9,
  "dependsOn": ["<A7_UUID>", "<A8_UUID>"]
}
```

### A10 — Publish RFP  *(transactional)*

```json
{
  "name": "Publish accepted RFP(s) on GeM portal",
  "description": "Per RFP §4.2.8.a.i. Atomic publication event marking start of D8 bid-process management.",
  "type": "transactional",
  "startDate": "2027-06-01T00:00:00Z",
  "endDate": "2027-06-01T00:00:00Z",
  "position": 10,
  "dependsOn": ["<A9_UUID>"]
}
```

---

## Representative activities for D2 – D6, D8 – D11

Each milestone gets 3-5 activities here so the dataset is complete without
ballooning. Add more from the RFP's §4.2.x sub-items as needed.

### D2 — Project Documents Repository

- A1: **Identify documentation gaps** (standard) — 2026-06-01 → 2026-06-30
  (per §4.2.2.a)
- A2: **Coordinate inventory from MSAP/MSIP/BSP** (standard) — 2026-06-15 → 2026-08-01
  (per §4.2.2.b)
- A3: **Build digital repository** (resource, count=2 PMC tech writers) — 2026-07-01 → 2026-09-01
  (per §4.2.2.c+d)

### D3 — Program Management Strategy

- A1: **Tech-stack roadmap workshop, Bengaluru** (transactional) — 2026-07-15
  (per §4.2.3.d)
- A2: **Tech-stack roadmap workshop, New Delhi** (transactional) — 2026-07-22
  (per §4.2.3.d)
- A3: **Multi-DC infrastructure design** (resource, details, SME Cloud/Infra) — 2026-08-01 → 2026-10-15
  (per §4.2.3.e)
- A4: **Risk-treatment framework** (standard) — 2026-09-01 → 2026-10-31
  (per §4.2.3.h)
- A5: **Program Management Strategy report drafting** (standard) — 2026-10-01 → 2026-11-01

### D4 — DPR

- A1: **7-10 year tech roadmap** (standard) — 2026-06-15 → 2026-08-15
- A2: **TCO + SLA-linked payment-stream model** (standard) — 2026-08-01 → 2026-09-30
- A3: **DC-DR + BCP options analysis** (resource, details, SME DR/BCP) — 2026-09-01 → 2026-10-31
- A4: **DPR drafting and submission** (standard) — 2026-10-01 → 2026-11-01

### D5 — DR + BCP Plan

- A1: **Critical-process identification** (standard) — 2026-09-01 → 2026-09-30
- A2: **DC-DR connectivity + failover design** (resource, details, SME DR/BCP) — 2026-09-15 → 2026-11-30
- A3: **Integrated BCP/DR drill — switchover** (transactional) — 2026-12-15
- A4: **Comprehensive DR+BCP plan based on drill learnings** (standard) — 2026-12-15 → 2027-01-01

### D6 — Functional + Technical Specs

- A1: **CIDR application/middleware/DB specs** (standard) — 2026-11-01 → 2027-01-15
- A2: **Multi-modal biometric subsystem evaluation** (resource, details, SME Biometrics) — 2026-12-01 → 2027-02-15
- A3: **7-year growth model + workload analysis** (standard) — 2027-01-01 → 2027-02-15
- A4: **Architecture views — application/data/network/security/deployment** (standard) — 2027-01-15 → 2027-02-28
- A5: **Bill of Materials + DC gap analysis** (standard) — 2027-02-01 → 2027-03-01

### D8 — Bid Process Management

- A1: **Conduct pre-bid meetings** (transactional) — 2027-04-01
- A2: **Issue clarifications + corrigenda** (standard) — 2027-04-01 → 2027-05-01
- A3: **Technical bid evaluation** (resource, count=3 evaluators) — 2027-07-01 → 2027-08-31
- A4: **Financial bid opening + QCBS scoring** (resource, details, SME Procurement) — 2027-09-01 → 2027-09-30
- A5: **CNC + NOA preparation** (standard) — 2027-10-01 → 2027-11-15
- A6: **Contract signing** (transactional) — 2027-12-01

### D9 — Transition Management

- A1: **Establish PMU at UIDAI HO** (resource, details, PMU Coord Delhi) — 2027-12-01 → 2028-12-01
- A2: **Establish PMU sub-unit at Tech Centre Bengaluru** (resource, details, PMU Coord Bengaluru) — 2027-12-01 → 2028-12-01
- A3: **KT — operations / technology / processes from old MSPs to new MSPs** (resource, count=6 KT consultants) — 2027-12-15 → 2028-08-31
- A4: **Asset return + handover audit** (standard) — 2028-06-01 → 2028-09-30
- A5: **Transition Closure Report** (standard) — 2028-10-01 → 2028-12-01

### D10 — In-life Project Management

- A1: **Weekly status reports** (resource, details, PMC Project Manager) — 2027-12-01 → 2031-12-01
- A2: **MSP contract clarifications (3-day SLA)** (resource, count=2) — 2027-12-01 → 2031-12-01
- A3: **Quarterly Steering Committee meetings** (resource, count=8) — 2027-12-01 → 2031-12-01
- A4: **MSP deliverable review and approval recommendations** (resource, details, PMC Program Director) — 2027-12-01 → 2031-12-01

### D11 — Governance Automation Tool

- A1: **Tool selection + procurement** (standard) — 2026-06-01 → 2026-07-15
- A2: **Customise Project-Timelines, Contract, Meetings modules** (resource, count=3 dev) — 2026-07-15 → 2026-10-01
- A3: **Security testing on consultant infrastructure** (standard) — 2026-09-15 → 2026-10-31
- A4: **Deploy to UIDAI infrastructure + UAT** (transactional) — 2026-11-01
- A5: **Knowledge transfer + training to UIDAI users** (resource, count=2 trainers) — 2026-11-01 → 2026-12-01

---

## What this exercises

- **All three activity types** (`standard`, `resource`, `transactional`).
- **Both resource modes** (`count`, `details`).
- **Resource division paths** including `tmd1` (tech), `tmd2` (procurement)
  and (in tasks/subtasks below) `others` + `divisionOther='PMU'`.
- **Inter-activity dependencies** within and across milestones (e.g. A8 in D1
  depends on the seven prior activities; A9 in D7 depends on A7+A8).
- **Three-tier date hierarchy** — every activity's start/end fits inside its
  milestone's window.
- **Status field** (`not_completed`, `completed`) on `standard` activities;
  exercised by `PATCH .../activities/{id}` during the demo close-out.
