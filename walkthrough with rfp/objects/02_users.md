# Users

## Why these ten

The RFP defines two distinct user populations:

1. **PMC team** (§4.4 Manpower): the consultant resources deployed by the
   bidder — must include a Program Director, a Program Manager, SMEs across
   biometrics / cloud / procurement / DR, and a dedicated PMU staffed at UIDAI
   HO + Tech Centre Bengaluru (§4.2.9.b).
2. **UIDAI stakeholders**: nodal officials who approve deliverables, sign
   contracts, and chair Steering Committee meetings.

Ten users cover both populations and exercise every branch of the user-create
schema (admin / non-admin, all three division paths including `others` +
`divisionOther`, vendor mapping into both PMC firm and an incumbent).

| # | Login | Role | Vendor | Division | Admin |
|---|---|---|---|---|---|
| 1 | uidai.tech.lead | UIDAI Tech Lead — accepts deliverables D3/D4/D6 | MSIP Infrastructure Solutions Ltd | tmd1 | yes |
| 2 | uidai.proc.lead | UIDAI Procurement Lead — chairs CNC during D8 | MSIP Infrastructure Solutions Ltd | tmd2 | yes |
| 3 | pmc.program.director | PMC Program Director — signs all PMC deliverables (§4.2.10.a.iv) | Aadhaar Project Consultancy LLP | tmd1 | yes |
| 4 | pmc.project.manager | PMC Program Manager — owns weekly status reports (§4.2.9.c.i) | Aadhaar Project Consultancy LLP | tmd1 | no |
| 5 | sme.biometrics | SME — Biometrics; informs D6 specs for matcher subsystem | Aadhaar Project Consultancy LLP | tmd1 | no |
| 6 | sme.cloud.infra | SME — Cloud & Infrastructure; informs DPR (D4), DR (D5) | Aadhaar Project Consultancy LLP | tmd1 | no |
| 7 | sme.procurement | SME — Procurement & Legal; informs RFP authoring (D7) | Aadhaar Project Consultancy LLP | tmd2 | no |
| 8 | sme.dr.bcp | SME — Disaster Recovery & BCP; owns D5 deliverable | Aadhaar Project Consultancy LLP | tmd1 | no |
| 9 | pmu.coord.delhi | PMU Coordinator at UIDAI HO (Delhi) | Aadhaar Project Consultancy LLP | others ("PMU") | no |
| 10 | pmu.coord.bengaluru | PMU Coordinator at Tech Centre Bengaluru | Aadhaar Project Consultancy LLP | others ("PMU") | no |

> Users 9 and 10 set `division="others"` + `divisionOther="PMU"` to exercise
> the paired-validation rule. The PMU is a cross-functional unit set up
> specifically by §4.2.9.b — it doesn't fit either tmd1 (pure tech) or tmd2
> (pure procurement) so it earns its own free-text label.

---

## Endpoint

```
POST /api/v3/users/create
```

Permission: `USERS_CREATE` (admin).

### Required-field reminders

- Every user must reference an existing `vendorId` — fill these in from the
  responses of the four vendor creates in `01_vendors.md`.
- Every user must include at least one `projectIds` entry — fill from the
  project create response in `03_project.md`.
- Passwords use `Demo!2026` for all demo users — strong enough to pass the
  ≥ 8-char minimum and easy to remember during a walkthrough.

---

## Request bodies

### U1 — UIDAI Tech Lead

```json
{
  "login": "uidai.tech.lead",
  "email": "tech.lead@uidai.gov.in.example",
  "password": "Demo!2026",
  "firstName": "Aravind",
  "lastName": "Reddy",
  "admin": true,
  "vendorId": "<MSIP_VENDOR_UUID>",
  "division": "tmd1",
  "projectIds": ["<PROJECT_UUID>"]
}
```

### U2 — UIDAI Procurement Lead

```json
{
  "login": "uidai.proc.lead",
  "email": "procurement.lead@uidai.gov.in.example",
  "password": "Demo!2026",
  "firstName": "Lakshmi",
  "lastName": "Subramanian",
  "admin": true,
  "vendorId": "<MSIP_VENDOR_UUID>",
  "division": "tmd2",
  "projectIds": ["<PROJECT_UUID>"]
}
```

### U3 — PMC Program Director

```json
{
  "login": "pmc.program.director",
  "email": "vikram.joshi@aadhaar-pmc.example",
  "password": "Demo!2026",
  "firstName": "Vikram",
  "lastName": "Joshi",
  "admin": true,
  "vendorId": "<PMC_VENDOR_UUID>",
  "division": "tmd1",
  "projectIds": ["<PROJECT_UUID>"]
}
```

### U4 — PMC Program Manager

```json
{
  "login": "pmc.project.manager",
  "email": "ananya.rao@aadhaar-pmc.example",
  "password": "Demo!2026",
  "firstName": "Ananya",
  "lastName": "Rao",
  "admin": false,
  "vendorId": "<PMC_VENDOR_UUID>",
  "division": "tmd1",
  "projectIds": ["<PROJECT_UUID>"]
}
```

### U5 — SME Biometrics

```json
{
  "login": "sme.biometrics",
  "email": "kavitha.nair@aadhaar-pmc.example",
  "password": "Demo!2026",
  "firstName": "Kavitha",
  "lastName": "Nair",
  "admin": false,
  "vendorId": "<PMC_VENDOR_UUID>",
  "division": "tmd1",
  "projectIds": ["<PROJECT_UUID>"]
}
```

### U6 — SME Cloud & Infrastructure

```json
{
  "login": "sme.cloud.infra",
  "email": "rohit.gupta@aadhaar-pmc.example",
  "password": "Demo!2026",
  "firstName": "Rohit",
  "lastName": "Gupta",
  "admin": false,
  "vendorId": "<PMC_VENDOR_UUID>",
  "division": "tmd1",
  "projectIds": ["<PROJECT_UUID>"]
}
```

### U7 — SME Procurement & Legal

```json
{
  "login": "sme.procurement",
  "email": "neha.kapoor@aadhaar-pmc.example",
  "password": "Demo!2026",
  "firstName": "Neha",
  "lastName": "Kapoor",
  "admin": false,
  "vendorId": "<PMC_VENDOR_UUID>",
  "division": "tmd2",
  "projectIds": ["<PROJECT_UUID>"]
}
```

### U8 — SME DR / BCP

```json
{
  "login": "sme.dr.bcp",
  "email": "sandeep.varma@aadhaar-pmc.example",
  "password": "Demo!2026",
  "firstName": "Sandeep",
  "lastName": "Varma",
  "admin": false,
  "vendorId": "<PMC_VENDOR_UUID>",
  "division": "tmd1",
  "projectIds": ["<PROJECT_UUID>"]
}
```

### U9 — PMU Coordinator (Delhi HO)  *— exercises division='others'*

```json
{
  "login": "pmu.coord.delhi",
  "email": "pmu.delhi@aadhaar-pmc.example",
  "password": "Demo!2026",
  "firstName": "Priya",
  "lastName": "Sharma",
  "admin": false,
  "vendorId": "<PMC_VENDOR_UUID>",
  "division": "others",
  "divisionOther": "PMU",
  "projectIds": ["<PROJECT_UUID>"]
}
```

### U10 — PMU Coordinator (Tech Centre Bengaluru)  *— exercises division='others'*

```json
{
  "login": "pmu.coord.bengaluru",
  "email": "pmu.bengaluru@aadhaar-pmc.example",
  "password": "Demo!2026",
  "firstName": "Karthik",
  "lastName": "Bhat",
  "admin": false,
  "vendorId": "<PMC_VENDOR_UUID>",
  "division": "others",
  "divisionOther": "PMU",
  "projectIds": ["<PROJECT_UUID>"]
}
```

---

## What this exercises

- Required-field path: `login`, `email`, `password`, `vendorId`, `division`,
  `projectIds` (≥1).
- All three division enums: `tmd1`, `tmd2`, `others` + paired
  `divisionOther`.
- Mix of `admin=true` (3 users — both UIDAI leads and the PMC Program Director)
  and `admin=false` (7 users).
- Each vendor referenced by ≥1 user (avoids "orphan vendor" demo state).
- Two users mapped onto the PMC vendor with `division=others` show the
  divisions catalogue auto-create when `divisionOther="PMU"` is submitted (per
  doc 18 §6).

## Negative-path demo (optional)

To show validation kicking in, attempt:

```json
{
  "login": "should.fail",
  "email": "x@example.com",
  "password": "Demo!2026",
  "vendorId": "<PMC_VENDOR_UUID>",
  "division": "others",
  "projectIds": ["<PROJECT_UUID>"]
}
```

(omits `divisionOther`) — should return 422 with a
`"divisionOther required when division=='others'"` style error.
