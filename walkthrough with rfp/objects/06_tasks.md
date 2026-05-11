# Tasks

## Mapping strategy

Tasks live one level under activities. They inherit their parent activity's
`type`, so a task under a `standard` activity is also `standard`; a task under
a `resource` activity carries its own `resourceMode` + (count or details).

This document drills two activities into tasks (per the plan in `PLAN.md`):

1. **D1 / A3 — "Visit ecosystem partners"** (resource, count) → 4 region tasks.
2. **D7 / A1 — "Draft EOI document"** (standard) → 5 sequencing tasks for the
   EOI authoring lifecycle.

The rest of the activities can have tasks added in the same pattern; these two
are enough to demonstrate every shape of the schema.

---

## Endpoint

```
POST /api/v3/activities/{activity_id}/tasks/create
```

Permission: project-edit.

> Reminder: the parent activity's `type` is inherited; do **not** send `type`
> in the task body. PMIS pulls it from the parent and validates the
> resource-mode/count/details payload accordingly.

---

## D1 / A3 — "Visit ecosystem partners" → 4 regional tasks

Parent activity: `type=resource`, `resourceMode=count`, `resourceCount=4`.
Each task is one regional sweep, staffed by one PMC field consultant.

### T1 — North region

```json
{
  "name": "Ecosystem partner visits — North region (Delhi NCR, Punjab, UP, Haryana, J&K, Himachal, Uttarakhand)",
  "description": "Per RFP §4.2.1.d. Sample at least one AUA, KUA, Registrar, ASK and contact-centre per state in the region.",
  "startDate": "2026-06-15T00:00:00Z",
  "endDate": "2026-07-05T00:00:00Z",
  "position": 1,
  "resourceMode": "count",
  "resourceCount": 1,
  "dependsOn": []
}
```

### T2 — South region

```json
{
  "name": "Ecosystem partner visits — South region (Karnataka, Tamil Nadu, Kerala, Andhra Pradesh, Telangana)",
  "description": "Per RFP §4.2.1.d.",
  "startDate": "2026-06-15T00:00:00Z",
  "endDate": "2026-07-10T00:00:00Z",
  "position": 2,
  "resourceMode": "count",
  "resourceCount": 1,
  "dependsOn": []
}
```

### T3 — East region

```json
{
  "name": "Ecosystem partner visits — East region (West Bengal, Odisha, Bihar, Jharkhand, Assam, NE states)",
  "description": "Per RFP §4.2.1.d.",
  "startDate": "2026-06-22T00:00:00Z",
  "endDate": "2026-07-20T00:00:00Z",
  "position": 3,
  "resourceMode": "count",
  "resourceCount": 1,
  "dependsOn": []
}
```

### T4 — West region

```json
{
  "name": "Ecosystem partner visits — West region (Maharashtra, Gujarat, Rajasthan, Madhya Pradesh, Goa)",
  "description": "Per RFP §4.2.1.d.",
  "startDate": "2026-06-22T00:00:00Z",
  "endDate": "2026-07-25T00:00:00Z",
  "position": 4,
  "resourceMode": "count",
  "resourceCount": 1,
  "dependsOn": []
}
```

> Note: tasks under a `count`-mode resource activity each carry their own
> `resourceCount`. The four together sum to the parent's count of 4.

---

## D7 / A1 — "Draft EOI document" → 5 sequencing tasks

Parent activity: `type=standard`. Tasks inherit `type=standard` and carry
`status` field (`not_completed` / `completed`) instead of resource fields.

### T1 — EOI Section A: Project description

```json
{
  "name": "Draft EOI Section A — Description of the project",
  "description": "Per RFP §4.2.7.a.i.A. Sets the macro context for prospective bidders.",
  "startDate": "2027-01-01T00:00:00Z",
  "endDate": "2027-01-05T00:00:00Z",
  "position": 1,
  "dependsOn": []
}
```

### T2 — EOI Section B: Broad scope of work

```json
{
  "name": "Draft EOI Section B — Broad scope of work",
  "description": "Per RFP §4.2.7.a.i.B. Summary scope without prescribing specific service-level numbers.",
  "startDate": "2027-01-05T00:00:00Z",
  "endDate": "2027-01-12T00:00:00Z",
  "position": 2,
  "dependsOn": ["<T1_UUID>"]
}
```

### T3 — EOI Section C: Background on UIDAI ecosystem

```json
{
  "name": "Draft EOI Section C — Background of UIDAI and its ecosystem partners",
  "description": "Per RFP §4.2.7.a.i.C. AUAs / KUAs / Registrars context for prospective bidders.",
  "startDate": "2027-01-08T00:00:00Z",
  "endDate": "2027-01-15T00:00:00Z",
  "position": 3,
  "dependsOn": ["<T1_UUID>"]
}
```

### T4 — EOI Sections D–F: Deliverables, locations, eligibility

```json
{
  "name": "Draft EOI Sections D–F — Deliverables/outcomes, places of execution, PQ/Eligibility criteria",
  "description": "Per RFP §4.2.7.a.i.D, §4.2.7.a.i.E and §4.2.7.a.i.F. PQ criteria includes project experience (number + value).",
  "startDate": "2027-01-12T00:00:00Z",
  "endDate": "2027-01-22T00:00:00Z",
  "position": 4,
  "dependsOn": ["<T2_UUID>", "<T3_UUID>"]
}
```

### T5 — EOI Sections G–H: Submission and certifications

```json
{
  "name": "Draft EOI Sections G–H — Instructions to bidders, submission forms/templates, quality certifications",
  "description": "Per RFP §4.2.7.a.i.G and §4.2.7.a.i.H. Closes the EOI document for internal review.",
  "startDate": "2027-01-22T00:00:00Z",
  "endDate": "2027-01-31T00:00:00Z",
  "position": 5,
  "dependsOn": ["<T4_UUID>"]
}
```

---

## What this exercises

- **Type inheritance**: tasks pick up `type` from their parent activity — no
  `type` in the POST body.
- **Resource-mode propagation**: count-mode parent → count-mode tasks; the per-
  task `resourceCount` totals to the parent's count.
- **Cross-task dependencies**: T2 + T3 fan out from T1; T4 fans in from T2+T3;
  T5 hangs off T4. Demonstrates a non-trivial dependency DAG within one
  activity.
- **Date containment**: every task's window fits inside the parent activity's
  window which fits inside the parent milestone's window — tested by the
  date-cascade validator.
- **`dependsOn` constraint**: PMIS enforces that a task's `dependsOn` must
  reference tasks whose **parent activity** is either the same activity or one
  the current activity already `dependsOn` — exercised here by tasks all
  sharing one parent activity.

## Negative-path demo (optional)

After creating T1–T5, attempt:

```
PATCH /api/v3/tasks/<T1_UUID>
{ "dependsOn": ["<T5_UUID>"] }
```

Should produce a cycle-detection error (T1 → T5 → T4 → T2/T3 → T1) — useful
to show during the dependency-graph part of the demo.
