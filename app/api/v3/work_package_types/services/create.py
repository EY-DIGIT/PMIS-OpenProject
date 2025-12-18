"""
Create work package type service.
"""
from sqlalchemy.orm import Session
from .....shared.service_result import ServiceResult
from .....infrastructure.db.repositories.work_package_type_repository import WorkPackageTypeRepository
from .....domain.work_package_types.work_package_type import WorkPackageType


def create_work_package_type(db: Session, name: str, internal_name: str, is_builtin: bool = False, is_active: bool = True, position: int = 0) -> ServiceResult[WorkPackageType]:
    repository = WorkPackageTypeRepository(db)

    if repository.exists_by_internal_name(internal_name):
        return ServiceResult.fail(error=f"Type with internal name '{internal_name}' already exists", error_type="already_exists")

    try:
        model = repository.create(
            name=name,
            internal_name=internal_name,
            is_builtin=is_builtin,
            is_active=is_active,
            position=position,
        )

        return ServiceResult.ok(model)
    except Exception as e:
        return ServiceResult.fail(error=f"Failed to create work package type: {str(e)}", error_type="database_error")
