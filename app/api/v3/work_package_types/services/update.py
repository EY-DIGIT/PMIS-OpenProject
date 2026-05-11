"""
Update work package type service.
"""
from typing import Optional
from sqlalchemy.orm import Session
from .....shared.service_result import ServiceResult
from .....infrastructure.db.repositories.work_package_type_repository import WorkPackageTypeRepository


def update_work_package_type(db: Session, type_id: int, name: Optional[str] = None, is_active: Optional[bool] = None, position: Optional[int] = None) -> ServiceResult:
    repository = WorkPackageTypeRepository(db)
    if not repository.exists_by_id(type_id):
        return ServiceResult.fail(error=f"Work package type {type_id} not found", error_type="not_found")

    try:
        model = repository.update(type_id=type_id, name=name, is_active=is_active, position=position)
        return ServiceResult.ok(model)
    except Exception as e:
        return ServiceResult.fail(error=f"Failed to update work package type: {str(e)}", error_type="database_error")
