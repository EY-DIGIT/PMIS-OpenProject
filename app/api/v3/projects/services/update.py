"""
Project update service.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from .....core.errors import AuthorizationError, DomainError, NotFoundError, ValidationError
from .....core.project_lock import assert_project_editable
from .....domain.projects.project import Project
from .....infrastructure.db.repositories.project_repository import ProjectRepository
from .....infrastructure.db.repositories.user_repository import UserRepository
from .....infrastructure.db.repositories.vendor_repository import VendorRepository
from .....shared.datetime import ensure_aware_utc
from .....shared.service_result import ServiceResult
from .....shared.utils import normalize_string

from .audit import ACTION_UPDATE, project_snapshot, record_audit
from .transitions import editable_fields_for


def _verify_user_exists(db: Session, username: str) -> bool:
    return UserRepository(db).get_by_login(username) is not None


def update_project(
    db: Session,
    project_id: str,
    *,
    actor_id: Optional[int],
    patch: Dict[str, Any],
    vendor_ids: Optional[List[str]] = None,
) -> ServiceResult[Project]:
    """
    Apply a field patch to a project.

    ``patch`` is a dict of snake_case field names (the controller translates
    from the request schema). Fields outside the editable whitelist for the
    project's current state are rejected with 422 invalid_field.

    ``vendor_ids`` is independent of the column whitelist because vendors
    live in an association table. Semantics:
      - None  : leave the project's current vendor list unchanged.
      - []    : clear the vendor list.
      - [...] : replace the vendor list with exactly these UUIDs (must all
                reference existing active vendors; otherwise 422).
    """
    repo = ProjectRepository(db)
    project = repo.get_by_id(project_id)
    if project is None:
        return ServiceResult.fail(
            error=f"Project with ID {project_id} not found",
            error_type="not_found",
        )

    # Lock: published baselines (and, once M/A/T/S contributor extends this,
    # their subtrees) are not editable. Upstream's assert_project_editable
    # raises NotFoundError for soft-deleted / missing rows and
    # AuthorizationError for a published baseline.
    try:
        assert_project_editable(db, project_id)
    except NotFoundError as e:
        return ServiceResult.fail(error=e.message, error_type="not_found")
    except AuthorizationError as e:
        return ServiceResult.fail(
            error=e.message,
            error_type="project_locked",
            details={"errorIdentifier": "project_locked"},
        )
    except DomainError as e:
        return ServiceResult.fail(error=e.message, error_type="validation_error")

    # Drop keys whose value is None — None means "unchanged" in a PATCH.
    supplied = {k: v for k, v in patch.items() if v is not None}

    allowed = editable_fields_for(project)
    rejected = sorted(set(supplied) - allowed)
    if rejected:
        return ServiceResult.fail(
            error=(
                f"Fields not editable in current project state: "
                f"{', '.join(rejected)}"
            ),
            error_type="invalid_field",
            details={
                "errorIdentifier": "invalid_field",
                "rejected": rejected,
                "allowed": sorted(allowed),
                "project_status": project.status,
                "is_version": project.is_version,
            },
        )

    if "name" in supplied:
        supplied["name"] = normalize_string(supplied["name"])
        if not supplied["name"] or len(supplied["name"]) > 255:
            return ServiceResult.fail(
                error="Invalid name. Must be 1-255 characters.",
                error_type="validation_error",
            )

    if "description" in supplied and supplied["description"] is not None:
        if len(supplied["description"]) > 5000:
            return ServiceResult.fail(
                error="Description too long. Maximum 5000 characters.",
                error_type="validation_error",
            )

    if "status_explanation" in supplied and supplied["status_explanation"] is not None:
        if len(supplied["status_explanation"]) > 5000:
            return ServiceResult.fail(
                error="Status explanation too long. Maximum 5000 characters.",
                error_type="validation_error",
            )

    # "Must be in the future" is enforced by the Pydantic schema for the
    # supplied fields; skip the duplicate check to avoid naive/aware clashes.
    effective_start = ensure_aware_utc(
        supplied.get("start_date", project.start_date)
    )
    effective_end = ensure_aware_utc(
        supplied.get("end_date", project.end_date)
    )
    if (
        effective_start is not None
        and effective_end is not None
        and effective_end <= effective_start
    ):
        return ServiceResult.fail(
            error="end_date must be after start_date",
            error_type="validation_error",
        )

    if "owner" in supplied and not _verify_user_exists(db, supplied["owner"]):
        return ServiceResult.fail(
            error=f"Owner user '{supplied['owner']}' does not exist",
            error_type="validation_error",
        )

    # Vendor-list replacement. Handled outside the column whitelist.
    vendor_repo = VendorRepository(db)
    will_replace_vendors = vendor_ids is not None
    clean_vendor_ids: List[str] = []
    if will_replace_vendors:
        unique_vids = list(dict.fromkeys(vendor_ids or []))
        if unique_vids:
            ok_ids = set(vendor_repo.existing_active_ids(unique_vids))
            missing = [v for v in unique_vids if v not in ok_ids]
            if missing:
                return ServiceResult.fail(
                    error=f"Unknown or inactive vendor(s): {', '.join(missing)}",
                    error_type="validation_error",
                )
        clean_vendor_ids = unique_vids

    before = project_snapshot(project)

    try:
        updated = repo.update(
            project_id=project_id,
            updated_by=actor_id,
            **supplied,
        )
        if updated is None:
            return ServiceResult.fail(
                error=f"Project with ID {project_id} not found",
                error_type="not_found",
            )

        if will_replace_vendors:
            vendor_repo.set_project_vendors(project_id, clean_vendor_ids)
            updated.vendors = vendor_repo.list_project_vendors(project_id)

        record_audit(
            db,
            project_id=project_id,
            actor_id=actor_id,
            action=ACTION_UPDATE,
            before=before,
            after=project_snapshot(updated),
        )

        db.commit()
        return ServiceResult.ok(updated)

    except Exception as e:
        db.rollback()
        return ServiceResult.fail(
            error=f"Failed to update project: {str(e)}",
            error_type="internal_error",
        )
