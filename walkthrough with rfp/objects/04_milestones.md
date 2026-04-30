# Milestones

## Mapping

The RFP enumerates eleven explicit deliverables (D1–D11) with codified
timelines in §4.3. Each becomes one PMIS milestone under the parent project
created in `03_project.md`.

T0 = **2026-06-01**.

| # | Code | Name | Start | End | Depends |
|---|------|------|-------|-----|---------|
| M1 | D1 | Report on existing (AS-IS) implementation and improvement areas | T0 | T0+3m | — |
| M2 | D2 | Project documents repository + Knowledge Management plan | T0 | T0+3m | — |
| M3 | D3 | Program Management Strategy, Roadmap, Transition & Maintenance Plan | T0 | T0+5m | M1, M2 |
| M4 | D4 | Detailed Project Report (DPR) — CIDR enhancement strategy & roadmap | T0 | T0+5m | M1 |
| M5 | D5 | Disaster Recovery Plan + Business Continuity Plan + integrated DR test | T0+3m | T0+7m | M1 |
| M6 | D6 | Functional & Technical Specifications for CIDR IT systems | T0+5m | T0+9m | M3, M4 |
| M7 | D7 | RFPs for MSP selection (incl. EOI conduct) | T0+7m | T0+12m | M6 |
| M8 | D8 | Bid Process Management & Contract Signing | T0+9m | T0+18m | M7 |
| M9 | D9 | Transition Management to new MSPs | T0+18m | T0+30m | M8 |
| M10 | D10 | In-life Project Management & Governance | T0+18m | T0+66m | M9 |
| M11 | D11 | Governance Automation Tool — supply, install, UAT, maintenance | T0 | T0+6m | — |

The `depends` chain mirrors the RFP's "after acceptance of D… consultant shall
proceed to…" language, allowing PMIS to flag downstream slippage if any
upstream milestone falls behind.

---

## Endpoint

```
POST /api/v3/projects/{project_id}/milestones
```

Permission: requires the same access as project edit (project members + admins).

`vendors` field uses the project's vendor UUIDs from `01_vendors.md` so each
milestone shows the vendors actively involved at that stage. Examples:

- D1 / D2: all 3 incumbents + PMC (audit-the-current-world milestones).
- D7 / D8: PMC + UIDAI only — the new MSPs aren't selected yet; these
  milestones produce the contracts that will engage them.
- D9: PMC + (eventually) the newly-selected MSPs once known.

---

## Request bodies

### M1 — D1: AS-IS Implementation Report

```json
{
  "name": "D1: AS-IS Implementation Report and Improvement Areas",
  "description": "Comprehensive study of UIDAI ecosystem and CIDR implementation: technology, architecture, networking, application, business processes, knowledge-transfer needs, governance and inter-MSP coordination challenges. Includes risk-management plan covering physical, fraud, logical, communication, natural and technological threats. Drives all downstream design deliverables.",
  "startDate": "2026-06-01T00:00:00Z",
  "endDate": "2026-09-01T00:00:00Z",
  "position": 1,
  "status": "not_completed",
  "depends": [],
  "vendors": [
    "<MSAP_VENDOR_UUID>",
    "<MSIP_VENDOR_UUID>",
    "<BSP_VENDOR_UUID>",
    "<PMC_VENDOR_UUID>"
  ]
}
```

### M2 — D2: Project Documents Repository + KM Plan

```json
{
  "name": "D2: Project Documents Repository and Knowledge Management Plan",
  "description": "Identify documentation gaps from current MSAP / MSIP / BSP. Coordinate inventory of source code, operational manuals, system design docs into version control. Build digital repository covering application architectures, access matrix, IT governance, SOPs, IT policies, process flows, incident/problem management, IT assets, networking, info-security/cyber-security. Maintainable on a digital platform updated continuously by PMC.",
  "startDate": "2026-06-01T00:00:00Z",
  "endDate": "2026-09-01T00:00:00Z",
  "position": 2,
  "status": "not_completed",
  "depends": [],
  "vendors": [
    "<MSAP_VENDOR_UUID>",
    "<MSIP_VENDOR_UUID>",
    "<BSP_VENDOR_UUID>",
    "<PMC_VENDOR_UUID>"
  ]
}
```

### M3 — D3: Program Management Strategy & Roadmap

```json
{
  "name": "D3: Program Management Strategy, Roadmap, Transition Plan and Maintenance Plan",
  "description": "Futuristic technology stack, operations + maintenance + technology-development strategy, procurement / transition / exit / migration plans, program-monitoring strategy, shared-responsibility model across MSPs. Includes minimum two workshops (Bengaluru and New Delhi), multi-DC infrastructure design, structured risk-assessment + treatment framework. Drives the procurement strategy fed into D7.",
  "startDate": "2026-06-01T00:00:00Z",
  "endDate": "2026-11-01T00:00:00Z",
  "position": 3,
  "status": "not_completed",
  "depends": ["<M1_UUID>", "<M2_UUID>"],
  "vendors": ["<PMC_VENDOR_UUID>"]
}
```

### M4 — D4: Detailed Project Report (DPR)

```json
{
  "name": "D4: Detailed Project Report — CIDR Enhancement Strategy and Roadmap",
  "description": "DPR spanning 7-10 year tech roadmap, capacity & scalability for CIDR, minimal vendor lock-in strategy, TCO analysis with SLA-linked payment streams, application life-cycle management, scalability + benchmarking + post-implementation monitoring, comprehensive DC-DR + BCP options, sensitivity analysis (time + cost), detailed costing sheets, project schedule with key phases, dependencies, critical paths, milestones from design through Go-Live with new MSPs.",
  "startDate": "2026-06-01T00:00:00Z",
  "endDate": "2026-11-01T00:00:00Z",
  "position": 4,
  "status": "not_completed",
  "depends": ["<M1_UUID>"],
  "vendors": ["<PMC_VENDOR_UUID>"]
}
```

### M5 — D5: DR + BCP Plan

```json
{
  "name": "D5: Disaster Recovery Plan, Business Continuity Plan and Integrated BCP/DR Test",
  "description": "Review and revise existing DRP/BCP for CIDR — data replication strategies between DC, DR and DC-DR connectivity; failover procedures; identification of critical processes; backup connectivity; DR maintenance drill; switchover drill between DC and DR. Plan and conduct an integrated BCP/DR exercise based on actual downtime of all CIDR/UIDAI processes. Output: comprehensive DC-DR and BCP plan based on exercise learnings.",
  "startDate": "2026-09-01T00:00:00Z",
  "endDate": "2027-01-01T00:00:00Z",
  "position": 5,
  "status": "not_completed",
  "depends": ["<M1_UUID>"],
  "vendors": ["<MSIP_VENDOR_UUID>", "<PMC_VENDOR_UUID>"]
}
```

### M6 — D6: Functional & Technical Specs

```json
{
  "name": "D6: Functional and Technical Specifications for CIDR IT Systems",
  "description": "Detailed functional + technical requirements for application software, middleware, biometric matching/de-dup, database, front/back-end, servers, networking, security, storage. Multi-modal biometric subsystem evaluation + improvements. 7-year growth model with workload analysis + sizing methodology. Architecture views: application, data, network, security, deployment. Bill of Materials with specifications. Gap analysis on existing DC facilities and non-IT infrastructure vs proposed BOM.",
  "startDate": "2026-11-01T00:00:00Z",
  "endDate": "2027-03-01T00:00:00Z",
  "position": 6,
  "status": "not_completed",
  "depends": ["<M3_UUID>", "<M4_UUID>"],
  "vendors": [
    "<MSAP_VENDOR_UUID>",
    "<MSIP_VENDOR_UUID>",
    "<BSP_VENDOR_UUID>",
    "<PMC_VENDOR_UUID>"
  ]
}
```

### M7 — D7: RFPs for MSP Selection

```json
{
  "name": "D7: RFPs for Selection of MSP(s) to Manage and Enhance CIDR",
  "description": "Two-part deliverable: (a) Preparation and conduct of EOI for short-listing prospective bidders. (b) Preparation of one or more RFPs covering management & enhancement of CIDR, IT infra procurement & install, replication of IT infra, ISMS + monitoring systems, testing & benchmarking, documentation & training, ops & support, managed services, app development + bug fix, helpdesk + facilitation centres, end-to-end UID logistics, facilities mgmt, sys & DB admin, regional & state-office IT mgmt. Includes SLA design with calculation principles, downtime/uptime, peak-hour service levels, payment-component & LD capping, payment schedule with sample calculations, legal/contractual requirements per Aadhaar Act 2016.",
  "startDate": "2027-01-01T00:00:00Z",
  "endDate": "2027-06-01T00:00:00Z",
  "position": 7,
  "status": "not_completed",
  "depends": ["<M6_UUID>"],
  "vendors": ["<PMC_VENDOR_UUID>"]
}
```

### M8 — D8: Bid Process Management & Contract Signing

```json
{
  "name": "D8: Bid Process Management and Contract Signing",
  "description": "Publication of RFP on GeM portal / agreed platform; pre-bid meetings; clarifications + corrigendum; technical bid evaluation; financial bid opening + evaluation; BOM examination + technical-proposal compliance; QCBS scoring; CNC; closure of bid process and selection of service provider; preparation of NOA + draft contract; finalisation and signing of contract(s). Consultant provides secretarial/technical/financial/legal/contractual support to UIDAI bid-evaluation committees.",
  "startDate": "2027-03-01T00:00:00Z",
  "endDate": "2027-12-01T00:00:00Z",
  "position": 8,
  "status": "not_completed",
  "depends": ["<M7_UUID>"],
  "vendors": ["<PMC_VENDOR_UUID>"]
}
```

### M9 — D9: Transition Management

```json
{
  "name": "D9: Transition Management to New MSPs",
  "description": "Establish PMU at UIDAI HO + PMU sub-unit at Tech Centre Bengaluru. Weekly project-management reports to UIDAI; review/validate detailed project & transition plans from incoming MSPs; KT of operations / technology / processes; ensure all assets returned by old MSPs and handed over to new MSPs through UIDAI; manage licences, IPR, warranties; KT + training to UIDAI on SLA monitoring tools; review/validate procurement, transition, commissioning and Go-Live plans using industry-standard PM tools; submit Transition Closure Report.",
  "startDate": "2027-12-01T00:00:00Z",
  "endDate": "2028-12-01T00:00:00Z",
  "position": 9,
  "status": "not_completed",
  "depends": ["<M8_UUID>"],
  "vendors": [
    "<MSAP_VENDOR_UUID>",
    "<MSIP_VENDOR_UUID>",
    "<BSP_VENDOR_UUID>",
    "<PMC_VENDOR_UUID>"
  ]
}
```

### M10 — D10: In-life Project Management

```json
{
  "name": "D10: In-life Project Management and Governance",
  "description": "Monitor adherence to MSP timelines (flag delays within 2 business days); suggest mid-course corrections; provide MSP contract clarifications within 3 working days; verify BOM provided by MSP/implementation partners; verify procurement, install, configuration, commissioning of IT + non-IT infra; verify software/tool agreements and licence updates; review MSP deliverables and recommend approvals to UIDAI. Ongoing project management and governance over the operational MSP contract lifecycle.",
  "startDate": "2027-12-01T00:00:00Z",
  "endDate": "2031-12-01T00:00:00Z",
  "position": 10,
  "status": "not_completed",
  "depends": ["<M9_UUID>"],
  "vendors": ["<PMC_VENDOR_UUID>"]
}
```

### M11 — D11: Governance Automation Tool

```json
{
  "name": "D11: Governance Automation Tool — Supply, Install, UAT and Maintenance",
  "description": "Implement automated governance solution to manage MSP activities, PMC deliverables and contracts. Modules: Project Timelines (baseline plan, sub-activity breakdown, divisions/SPOCs, audit trail, comments, automated email alerts, dashboards); Contract Module (milestone-payment-SLA mapping, doc upload, invoice workflow, change-request tracking, alerts on SLA impact / event-of-default); Meetings Module (Steering Committee minutes, action assignment, comment trail, dashboards). General: doc management, RBAC, encrypted/secure, audit trails, AI-driven extraction, integrations, lifecycle management. Hosted on UIDAI infrastructure; security-tested at consultant cost; KT and training to UIDAI users.",
  "startDate": "2026-06-01T00:00:00Z",
  "endDate": "2026-12-01T00:00:00Z",
  "position": 11,
  "status": "not_completed",
  "depends": [],
  "vendors": ["<PMC_VENDOR_UUID>"]
}
```

---

## What this exercises

- **Eleven distinct milestones** under one project — pagination + ordering on
  `GET /projects/{id}/milestones`.
- **Dependency graph** via `depends` field — each downstream milestone names
  upstream UUIDs. (Per current schema this is captured but not yet
  referentially enforced; useful for showing future enforcement.)
- **Vendor associations** (`vendors` field) per milestone — exercises the
  vendor-must-belong-to-project validator.
- **Mix of long (D9: 12 months, D10: 48 months) and short (D1, D2: 3 months)
  milestones** — shows the timeline view at multiple zoom levels.
- **Status default** `not_completed` on create; `PATCH .../milestones/{id}`
  with `{"status": "completed"}` is the close-out demo at the end of each
  milestone's run.
