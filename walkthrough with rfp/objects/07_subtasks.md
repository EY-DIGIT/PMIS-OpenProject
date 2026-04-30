# Subtasks

## Mapping strategy

Subtasks are the leaf granularity in PMIS — under tasks, which are under
activities, which are under milestones. They inherit `type` from their parent
task (which inherits from the activity).

Two task-trees from `06_tasks.md` are drilled into subtasks here, matching the
ones called out in `PLAN.md`:

1. **D1 / A3 / T1 — North-region partner visit** → 5 subtasks, one per partner
   type (AUA, KUA, Registrar, ASK, Contact Centre).
2. **D7 / A1 / T4 — EOI Sections D–F** → 3 subtasks, one per section, with
   sequencing dependencies.

The other tasks can have subtasks added in the same pattern when needed; these
two cover every shape of the schema.

---

## Endpoint

```
POST /api/v3/tasks/{task_id}/subtasks/create
```

Permission: project-edit.

> Reminder: type is inherited from the parent task. Do not send `type` in the
> body.

---

## D1 / A3 / T1 — North region → 5 partner-type subtasks

Parent task `T1` (North region) is `type=resource`, `resourceMode=count`,
`resourceCount=1`. The five subtasks below split the visiting consultant's
time across the five partner classes the RFP enumerates in §4.2.1.d.

> Each subtask carries `resourceMode=count` + `resourceCount=1` even though
> the parent's count is also 1 — because they're not concurrent staffing
> bumps; they're sequential time-slices of the same consultant. PMIS doesn't
> aggregate child counts upward into the parent (the parent's count remains
> the booking number; subtask counts capture per-step intensity).

### S1 — AUA visits (North)

```json
{
  "name": "Visit Authentication User Agencies (AUAs) in North region",
  "description": "Per RFP §4.2.1.d. Sample at least one banking AUA, one government-services AUA, one telecom AUA per major state.",
  "startDate": "2026-06-15T00:00:00Z",
  "endDate": "2026-06-19T00:00:00Z",
  "position": 1,
  "resourceMode": "count",
  "resourceCount": 1,
  "dependsOn": []
}
```

### S2 — KUA visits (North)

```json
{
  "name": "Visit Know Your Customer User Agencies (KUAs) in North region",
  "description": "Per RFP §4.2.1.d.",
  "startDate": "2026-06-19T00:00:00Z",
  "endDate": "2026-06-23T00:00:00Z",
  "position": 2,
  "resourceMode": "count",
  "resourceCount": 1,
  "dependsOn": []
}
```

### S3 — Registrar visits (North)

```json
{
  "name": "Visit Aadhaar Registrars in North region",
  "description": "Per RFP §4.2.1.d. State-level registrar offices responsible for resident enrolment.",
  "startDate": "2026-06-23T00:00:00Z",
  "endDate": "2026-06-27T00:00:00Z",
  "position": 3,
  "resourceMode": "count",
  "resourceCount": 1,
  "dependsOn": []
}
```

### S4 — Aadhaar Seva Kendra visits (North)

```json
{
  "name": "Visit Aadhaar Seva Kendras (ASKs) in North region",
  "description": "Per RFP §4.2.1.d. Front-line resident-facing centres.",
  "startDate": "2026-06-27T00:00:00Z",
  "endDate": "2026-07-01T00:00:00Z",
  "position": 4,
  "resourceMode": "count",
  "resourceCount": 1,
  "dependsOn": []
}
```

### S5 — Contact Centre visit (North)

```json
{
  "name": "Visit UIDAI contact centre — North region",
  "description": "Per RFP §4.2.1.d. Resident-helpline operations review.",
  "startDate": "2026-07-01T00:00:00Z",
  "endDate": "2026-07-05T00:00:00Z",
  "position": 5,
  "resourceMode": "count",
  "resourceCount": 1,
  "dependsOn": []
}
```

---

## D7 / A1 / T4 — EOI Sections D–F → 3 sequencing subtasks

Parent task `T4` is `type=standard`. Subtasks inherit `type=standard` and use
`status` (`not_completed` / `completed`) instead of resource fields.

### S1 — Section D: Deliverables and outcomes

```json
{
  "name": "Draft EOI Section D — Expected deliverables and outcomes of the assignment",
  "description": "Per RFP §4.2.7.a.i.D. Lists the specific outputs the selected MSP(s) will be required to produce.",
  "startDate": "2027-01-12T00:00:00Z",
  "endDate": "2027-01-15T00:00:00Z",
  "position": 1,
  "dependsOn": []
}
```

### S2 — Section E: Places of execution

```json
{
  "name": "Draft EOI Section E — Place(s) of execution of the assignment",
  "description": "Per RFP §4.2.7.a.i.E. Lists UIDAI HO, technology centres, regional and state offices.",
  "startDate": "2027-01-15T00:00:00Z",
  "endDate": "2027-01-18T00:00:00Z",
  "position": 2,
  "dependsOn": ["<S1_UUID>"]
}
```

### S3 — Section F: PQ / Eligibility criteria

```json
{
  "name": "Draft EOI Section F — Pre-Qualification / Eligibility Criteria (project experience: number + value)",
  "description": "Per RFP §4.2.7.a.i.F. Includes minimum number of similar projects and minimum aggregate value thresholds.",
  "startDate": "2027-01-18T00:00:00Z",
  "endDate": "2027-01-22T00:00:00Z",
  "position": 3,
  "dependsOn": ["<S2_UUID>"]
}
```

---

## What this exercises

- **Two-level inheritance**: type cascades milestone → activity → task → subtask
  without any explicit `type` field on the subtask payload.
- **Resource-mode propagation through two levels**.
- **Linear sequencing dependency** (S1 → S2 → S3) at the subtask level — each
  subtask must wait for the prior section to be drafted.
- **`dependsOn` rule at subtask level**: PMIS enforces that subtask
  dependencies must reference subtasks whose parent task is either the same
  task or one the current task already `dependsOn` — naturally satisfied here
  since all three subtasks share parent T4.
- **Three-tier date hierarchy**: each subtask's window fits inside its task,
  inside its activity, inside its milestone, inside the project. Date-cascade
  validator confirmed at all four boundaries.

## Negative-path demos (optional)

1. Create a subtask under T1 (S1: AUA visits) with `dependsOn` pointing to an
   S-row under a different parent task whose parent activity ≠ T1's activity:

   ```
   POST /api/v3/tasks/<T1_UUID>/subtasks/create
   { "name": "Bad dep", "dependsOn": ["<S_under_T4_UUID>"], ... }
   ```

   Should fail validation: parent task T1 doesn't `dependsOn` T4's parent.

2. Date out of bounds (subtask `endDate` > task `endDate`):

   Should fail with the date-cascade validator's "subtask end must be ≤ task
   end" message.
