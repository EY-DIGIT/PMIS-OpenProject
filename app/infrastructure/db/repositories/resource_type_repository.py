"""Resource-type catalog queries."""
from typing import List, Optional

from sqlalchemy.orm import Session

from ..models.resource_type import ResourceTypeModel
from ....domain.resource_types.resource_type import ResourceType


def _to_domain(m: ResourceTypeModel) -> ResourceType:
    return ResourceType(
        id=m.id,
        code=m.code,
        name=m.name,
        active=bool(m.active),
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class ResourceTypeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, code: str, name: str, active: bool = True) -> ResourceType:
        m = ResourceTypeModel(code=code.strip().lower(), name=name.strip(), active=active)
        self.db.add(m)
        self.db.flush()
        return _to_domain(m)

    def get_by_id(self, rt_id: str) -> Optional[ResourceType]:
        m = self.db.query(ResourceTypeModel).filter(ResourceTypeModel.id == rt_id).first()
        return _to_domain(m) if m else None

    def get_by_code(self, code: str) -> Optional[ResourceType]:
        m = (
            self.db.query(ResourceTypeModel)
            .filter(ResourceTypeModel.code == code.lower())
            .first()
        )
        return _to_domain(m) if m else None

    def exists_by_code(self, code: str) -> bool:
        return (
            self.db.query(ResourceTypeModel.id)
            .filter(ResourceTypeModel.code == code.lower())
            .first()
            is not None
        )

    def list_active(self) -> List[ResourceType]:
        rows = (
            self.db.query(ResourceTypeModel)
            .filter(ResourceTypeModel.active == True)  # noqa: E712
            .order_by(ResourceTypeModel.code.asc())
            .all()
        )
        return [_to_domain(r) for r in rows]

    def is_active(self, rt_id: str) -> bool:
        row = (
            self.db.query(ResourceTypeModel.active)
            .filter(ResourceTypeModel.id == rt_id)
            .first()
        )
        return bool(row and row[0])
