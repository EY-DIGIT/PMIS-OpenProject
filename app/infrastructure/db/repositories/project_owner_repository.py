"""Repository for the project_owners catalog."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models.project_owner import ProjectOwnerModel
from ..models.user import UserModel


class ProjectOwnerRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_active_with_user(
        self,
    ) -> List[Tuple[ProjectOwnerModel, UserModel]]:
        """Active catalog rows joined with their backing user record.

        Returned in (login, last_name, first_name) order so the dropdown
        sorts naturally for the UI.
        """
        return (
            self.db.query(ProjectOwnerModel, UserModel)
            .join(UserModel, UserModel.id == ProjectOwnerModel.user_id)
            .filter(ProjectOwnerModel.active.is_(True))
            .order_by(UserModel.login.asc())
            .all()
        )

    def is_login_an_active_owner(self, login: str) -> bool:
        """Check by user login (project.owner stores the login string)."""
        if not login:
            return False
        row = (
            self.db.query(ProjectOwnerModel.id)
            .join(UserModel, UserModel.id == ProjectOwnerModel.user_id)
            .filter(ProjectOwnerModel.active.is_(True))
            .filter(UserModel.login == login)
            .first()
        )
        return row is not None

    def add_by_user_id(
        self, user_id: int, display_name: Optional[str] = None,
    ) -> ProjectOwnerModel:
        """Insert (or reactivate) a catalog row for this user. Caller commits."""
        existing = (
            self.db.query(ProjectOwnerModel)
            .filter(ProjectOwnerModel.user_id == user_id)
            .first()
        )
        if existing is not None:
            existing.active = True
            if display_name is not None:
                existing.display_name = display_name
            self.db.flush()
            return existing
        row = ProjectOwnerModel(
            user_id=user_id, display_name=display_name, active=True,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def deactivate_by_user_id(self, user_id: int) -> bool:
        existing = (
            self.db.query(ProjectOwnerModel)
            .filter(ProjectOwnerModel.user_id == user_id)
            .first()
        )
        if existing is None:
            return False
        existing.active = False
        self.db.flush()
        return True
