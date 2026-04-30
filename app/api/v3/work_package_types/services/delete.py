"""
Delete work package type service.
"""
from sqlalchemy.orm import Session
from .....shared.service_result import ServiceResult
from .....infrastructure.db.repositories.work_package_type_repository import WorkPackageTypeRepository
from .....infrastructure.db.repositories.work_package_repository import WorkPackageRepository


def delete_work_package_type(db: Session, type_id: int) -> ServiceResult:
    repository = WorkPackageTypeRepository(db)
    if not repository.exists_by_id(type_id):
        return ServiceResult.fail(error=f"Work package type {type_id} not found", error_type="not_found")

    model = repository.get_by_id(type_id)
    if model and getattr(model, "is_builtin", False):
        return ServiceResult.fail(error="Cannot delete builtin type", error_type="forbidden")

    # Prevent deletion if any work package references this type
    wp_repo = WorkPackageRepository(db)
    if wp_repo.exists_by_type_id(type_id):
        return ServiceResult.fail(error="Cannot delete type in use by work packages", error_type="validation_error")

    try:
        ok = repository.delete(type_id)
        if not ok:
            return ServiceResult.fail(error="Failed to delete type", error_type="error")
        return ServiceResult.ok(True)
    except Exception as e:
        return ServiceResult.fail(error=f"Failed to delete work package type: {str(e)}", error_type="database_error")
