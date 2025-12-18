"""
Get work package type service.
"""
from sqlalchemy.orm import Session
from .....shared.service_result import ServiceResult
from .....infrastructure.db.repositories.work_package_type_repository import WorkPackageTypeRepository


def get_work_package_type_by_id(db: Session, type_id: int) -> ServiceResult:
    repository = WorkPackageTypeRepository(db)
    model = repository.get_by_id(type_id)
    if not model:
        return ServiceResult.fail(error=f"Work package type {type_id} not found", error_type="not_found")
    return ServiceResult.ok(model)
