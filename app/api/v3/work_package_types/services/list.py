"""
List work package types service.
"""
from typing import Tuple, List
from sqlalchemy.orm import Session
from .....shared.service_result import ServiceResult
from .....infrastructure.db.repositories.work_package_type_repository import WorkPackageTypeRepository


def list_work_package_types(db: Session, offset: int = 1, limit: int = 20) -> ServiceResult[Tuple[List, int]]:
    repository = WorkPackageTypeRepository(db)
    items, total = repository.list(offset=offset, limit=limit)
    return ServiceResult.ok((items, total))
