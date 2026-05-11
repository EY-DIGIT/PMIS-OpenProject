"""
Repository for WorkPackageType DB operations.
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from ...db.models.work_package_type import WorkPackageTypeModel
from ....domain.work_package_types.work_package_type import WorkPackageType


class WorkPackageTypeRepository:
    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, m: WorkPackageTypeModel) -> WorkPackageType:
        return WorkPackageType(
            id=m.id,
            name=m.name,
            internal_name=m.internal_name,
            is_builtin=m.is_builtin,
            is_active=m.is_active,
            position=m.position,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def create(self, name: str, internal_name: str, is_builtin: bool = False, is_active: bool = True, position: int = 0) -> WorkPackageType:
        model = WorkPackageTypeModel(
            name=name,
            internal_name=internal_name,
            is_builtin=is_builtin,
            is_active=is_active,
            position=position,
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, type_id: int) -> Optional[WorkPackageType]:
        m = self.db.query(WorkPackageTypeModel).filter(WorkPackageTypeModel.id == type_id).first()
        return self._to_domain(m) if m else None

    def list(self, offset: int = 1, limit: int = 20) -> Tuple[List[WorkPackageType], int]:
        q = self.db.query(WorkPackageTypeModel)
        total = q.count()
        models = q.offset((offset - 1) * limit).limit(limit).all()
        return [self._to_domain(m) for m in models], total

    def exists_by_internal_name(self, internal_name: str) -> bool:
        return self.db.query(self.db.query(WorkPackageTypeModel).filter(WorkPackageTypeModel.internal_name == internal_name).exists()).scalar()

    def exists_by_id(self, type_id: int) -> bool:
        return self.db.query(self.db.query(WorkPackageTypeModel).filter(WorkPackageTypeModel.id == type_id).exists()).scalar()

    def update(self, type_id: int, name: Optional[str] = None, is_active: Optional[bool] = None, position: Optional[int] = None) -> Optional[WorkPackageType]:
        m = self.db.query(WorkPackageTypeModel).filter(WorkPackageTypeModel.id == type_id).first()
        if not m:
            return None
        if name is not None:
            m.name = name
        if is_active is not None:
            m.is_active = is_active
        if position is not None:
            m.position = position
        self.db.commit()
        self.db.refresh(m)
        return self._to_domain(m)

    def delete(self, type_id: int) -> bool:
        m = self.db.query(WorkPackageTypeModel).filter(WorkPackageTypeModel.id == type_id).first()
        if not m:
            return False
        self.db.delete(m)
        self.db.commit()
        return True
