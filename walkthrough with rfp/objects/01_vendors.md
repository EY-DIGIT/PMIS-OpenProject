# Vendors

## Why these four

The RFP lives at the intersection of three incumbent vendor families and the
new PMC firm. All four are represented here so the demo exercises the
vendor-project mapping end-to-end.

| Vendor | RFP role |
|---|---|
| MSAP Operations Pvt Ltd | Current Managed Service Application Provider — operates CIDR application stack, helpdesk, and end-user services. |
| MSIP Infrastructure Solutions Ltd | Current Managed Service Infrastructure Provider — owns DC/DR hardware, networking, storage. |
| BSP Biometric Systems Ltd | Current Biometric Service Provider — runs the multi-modal de-duplication and matching subsystem. |
| Aadhaar Project Consultancy LLP | The PMC bidder who won this RFP — fields the consultant team described in §4.4 (Manpower) and §4.2.9.b (PMU sub-units). |

> Note: The first three are *targets* of the engagement (their handover into
> new MSPs is the whole point of the contract). The fourth is the *executor*
> of the engagement. Both are modelled as PMIS Vendors because PMIS treats
> "vendor" as any external organisation involved in a project — the
> distinction lives in how users and milestones reference them.

---

## Endpoint

```
POST /api/v3/vendors/create
```

Permission: `VENDORS_CREATE` (admin).

Note: `projectIds` is left empty here because the project doesn't exist yet at
the time vendors are created. The wiring is established the other direction —
when the project is created (see `03_project.md`), `vendorIds` lists all four
vendor UUIDs. PMIS keeps the link bidirectional.

---

## Request bodies

### V1 — MSAP Operations Pvt Ltd

```json
{
  "name": "MSAP Operations Pvt Ltd",
  "description": "Incumbent Managed Service Application Provider for CIDR. Operates Aadhaar enrolment, update, authentication application stack and the application-side helpdesk.",
  "active": true,
  "email": "delivery.cidr@msap-operations.example",
  "contactPerson": "Suresh Iyer",
  "phoneNumber": "+91 80 4567 8101"
}
```

### V2 — MSIP Infrastructure Solutions Ltd

```json
{
  "name": "MSIP Infrastructure Solutions Ltd",
  "description": "Incumbent Managed Service Infrastructure Provider. Owns CIDR data centre, DR site, networking fabric, storage tiers and platform virtualisation.",
  "active": true,
  "email": "cidr.ops@msip-infra.example",
  "contactPerson": "Anita Krishnan",
  "phoneNumber": "+91 80 2899 4500"
}
```

### V3 — BSP Biometric Systems Ltd

```json
{
  "name": "BSP Biometric Systems Ltd",
  "description": "Incumbent Biometric Service Provider. Operates multi-modal biometric de-duplication and authentication matchers used during enrolment and authentication.",
  "active": true,
  "email": "uidai.support@bsp-biometric.example",
  "contactPerson": "Rajiv Menon",
  "phoneNumber": "+91 80 2554 7733"
}
```

### V4 — Aadhaar Project Consultancy LLP (the PMC firm)

```json
{
  "name": "Aadhaar Project Consultancy LLP",
  "description": "Project Management Consultancy engaged by UIDAI under RFP HQ-24072/1/2023-TECH-II-HQ for selection and onboarding of new MSP(s). Fields the PMU at UIDAI HO and Tech Centre Bengaluru.",
  "active": true,
  "email": "uidai.pmc@aadhaar-pmc.example",
  "contactPerson": "Vikram Joshi",
  "phoneNumber": "+91 11 2345 6789"
}
```

---

## What this exercises

- Bulk vendor seed under one project context.
- Contact-detail columns added in doc 18 (`email`, `contactPerson`,
  `phoneNumber`).
- The vendor list endpoint (`GET /vendors`) should return all four.
- After project creation, `GET /vendors/{id}` should show the project mapped
  back via the bidirectional projection.
- Soft-delete + restore can be demoed by deleting V3 (BSP) and restoring it,
  showing the `include_deleted=true` flag effect.
