"""Update a milestone (partial; with date re-validation)."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from .....core.errors import NotFoundError, ValidationError
from .....core.project_lock import assert_milestone_activity_writable
from .....domain.milestones.milestone import (
    MILESTONE_STATUS_CHOICES,
    Milestone,
)
from .....infrastructure.db.models.project import ProjectModel
from .....infrastructure.db.repositories.dependency_repository import (
    DependencyRepository,
)
from .....infrastructure.db.repositories.milestone_repository import MilestoneRepository
from .....infrastructure.db.repositories.vendor_repository import VendorRepository
from .....shared.date_rules import validate_entity_dates
from .....shared.labels import KIND_MILESTONE, resolve_labels_to_ids
from ...projects.services.audit import record_audit
from ...projects.services.baseline_version_sync import (
    ACTION_MILESTONE_UPDATE,
    propagate_milestone_update,
    propagate_milestone_dependency_change,
)


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def update_milestone(
    db: Session,
    *,
    milestone_id: str,
    name: Optional[str],
    description: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    position: Optional[int],
    current_user_id: Optional[int],
    status: Optional[str] = None,
    depends_on: Optional[List[str]] = None,
    vendor_ids: Optional[List[str]] = None,
) -> Milestone:
    repo = MilestoneRepository(db)
    model = repo.get_model(milestone_id)
    if model is None:
        raise NotFoundError("The milestone could not be found.")

    assert_milestone_activity_writable(db, model.project_id)

    project = db.query(ProjectModel).filter(ProjectModel.id == model.project_id).first()
    if project is None or project.start_date is None:
        raise NotFoundError(
            "The project this milestone belongs to could not be found or has no start date."
        )

    new_start = start_date if start_date is not None else model.start_date
    new_end = end_date if end_date is not None else model.end_date

    validate_entity_dates(
        entity_start=new_start,
        entity_end=new_end,
        actual_start=None,
        actual_end=None,
        parent_start_date=project.start_date,
        project_start_date=project.start_date,
        entity_label="milestone",
        parent_label="project",
    )

    if status is not None and status not in MILESTONE_STATUS_CHOICES:
        raise ValidationError(
            f"Milestone status must be one of: {', '.join(MILESTONE_STATUS_CHOICES)}."
        )

    # Validate depends_on (replace-list semantics) BEFORE writing.
    # Accepts UUIDs or labels (e.g. "M2"); see app/shared/labels.py.
    desired_deps: Optional[List[str]] = None
    if depends_on is not None:
        dep_repo = DependencyRepository(db)
        candidates, _id_to_raw = resolve_labels_to_ids(
            db,
            project_id=model.project_id,
            expected_kind=KIND_MILESTONE,
            raw_inputs=depends_on,
        )
        if candidates:
            # Existence check (folded into the below cycle/missing logic
            # for tighter error messages — keeps the per-target raise).
            ok = dep_repo.existing_target_milestone_ids(model.project_id, candidates)
            missing = [d for d in candidates if d not in ok]
            if missing:
                raise ValidationError(
                    f"Unknown or out-of-project milestone dependency target(s): "
                    f"{', '.join(missing)}"
                )
            offending = dep_repo.would_create_cycle_milestone(
                milestone_id, candidates,
            )
            if offending is not None:
                if offending == milestone_id:
                    raise ValidationError(
                        "A milestone cannot depend on itself."
                    )
                raise ValidationError(
                    f"Adding milestone dependency on {offending} would "
                    "create a cycle."
                )
        desired_deps = candidates

    updates = {}
    if name is not None:
        updates["name"] = name.strip()
    if description is not None:
        updates["description"] = description
    if start_date is not None:
        updates["start_date"] = start_date
    if end_date is not None:
        updates["end_date"] = end_date
    if position is not None:
        updates["position"] = position
    if status is not None:
        updates["status"] = status

    vendor_repo = VendorRepository(db)
    will_replace_vendors = vendor_ids is not None
    resolved_vendor_ids: List[str] = []
    if will_replace_vendors:
        # Doc 25: each entry can be a UUID or a ``VN-...`` code.
        unique_input = list(dict.fromkeys(vendor_ids or []))
        if unique_input:
            resolved_pairs = [
                (token, vendor_repo.resolve_id(token)) for token in unique_input
            ]
            unresolved = [t for (t, rid) in resolved_pairs if rid is None]
            if unresolved:
                raise ValidationError(
                    f"Unknown vendor(s): {', '.join(unresolved)}"
                )
            canonical_ids = [rid for (_t, rid) in resolved_pairs]
            active = set(vendor_repo.existing_active_ids(canonical_ids))
            missing_active = [
                t for (t, rid) in resolved_pairs if rid not in active
            ]
            if missing_active:
                raise ValidationError(
                    f"Unknown or inactive vendor(s): {', '.join(missing_active)}"
                )
            project_vendor_ids = set(vendor_repo.project_vendor_ids(model.project_id))
            not_on_project_tokens = [
                t for (t, rid) in resolved_pairs if rid not in project_vendor_ids
            ]
            if not_on_project_tokens:
                raise ValidationError(
                    f"Vendor(s) not attached to this project: {', '.join(not_on_project_tokens)}. "
                    "Add them to the project first."
                )
            resolved_vendor_ids = canonical_ids

    if not updates and not will_replace_vendors and desired_deps is None:
        return repo._to_domain(model)

    before_snapshot = {k: _iso(getattr(model, k)) for k in updates.keys()} if updates else {}

    if updates:
        updated = repo.update(milestone_id, updates=updates, updated_by=current_user_id)
    else:
        updated = repo._to_domain(model)

    if desired_deps is not None:
        DependencyRepository(db).set_milestone_dependencies(
            milestone_id, model.project_id, desired_deps,
            actor_id=current_user_id,
        )
        db.commit()
        updated.depends_on = list(desired_deps)

    if will_replace_vendors:
        vendor_repo.set_milestone_vendors(milestone_id, resolved_vendor_ids)
        db.commit()
        updated.vendors = vendor_repo.list_milestone_vendors(milestone_id)

    if updates:
        record_audit(
            db,
            project_id=model.project_id,
            actor_id=current_user_id,
            action=ACTION_MILESTONE_UPDATE,
            before={"milestone_id": milestone_id, **before_snapshot},
            after={k: _iso(v) for k, v in updates.items()},
        )
        db.commit()
        propagate_milestone_update(
            db,
            baseline_milestone_id=milestone_id,
            updates=updates,
            actor_id=current_user_id,
        )

    if desired_deps is not None:
        propagate_milestone_dependency_change(
            db, baseline_milestone_id=milestone_id, actor_id=current_user_id,
        )

    return updated
