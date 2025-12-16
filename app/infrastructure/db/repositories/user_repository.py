"""
User repository for database operations.
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from ...db.models.user import UserModel
from ....domain.users.user import User


class UserRepository:
    """Repository for User database operations."""

    def __init__(self, db: Session):
        """
        Initialize repository.

        Args:
            db: Database session
        """
        self.db = db

    def _to_domain(self, model: UserModel) -> User:
        """
        Convert database model to domain model.

        Args:
            model: Database model

        Returns:
            Domain model
        """
        return User(
            id=model.id,
            login=model.login,
            email=model.email,
            first_name=model.first_name,
            last_name=model.last_name,
            admin=model.admin,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def create(
        self,
        login: str,
        email: str,
        hashed_password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        admin: bool = False,
        status: str = "active"
    ) -> User:
        """
        Create a new user.

        Args:
            login: User login
            email: User email
            hashed_password: Hashed password
            first_name: First name
            last_name: Last name
            admin: Admin flag
            status: User status

        Returns:
            Created user domain model
        """
        user_model = UserModel(
            login=login,
            email=email,
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            admin=admin,
            status=status,
        )

        self.db.add(user_model)
        self.db.commit()
        self.db.refresh(user_model)

        return self._to_domain(user_model)

    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User domain model if found, None otherwise
        """
        user_model = self.db.query(UserModel).filter(UserModel.id == user_id).first()

        if user_model:
            return self._to_domain(user_model)

        return None

    def get_by_login(self, login: str) -> Optional[User]:
        """
        Get user by login.

        Args:
            login: User login

        Returns:
            User domain model if found, None otherwise
        """
        user_model = self.db.query(UserModel).filter(UserModel.login == login).first()

        if user_model:
            return self._to_domain(user_model)

        return None

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            email: User email

        Returns:
            User domain model if found, None otherwise
        """
        user_model = self.db.query(UserModel).filter(UserModel.email == email).first()

        if user_model:
            return self._to_domain(user_model)

        return None

    def get_password_hash(self, user_id: int) -> Optional[str]:
        """
        Get user password hash.

        Args:
            user_id: User ID

        Returns:
            Password hash if found, None otherwise
        """
        user_model = self.db.query(UserModel).filter(UserModel.id == user_id).first()

        if user_model:
            return user_model.hashed_password

        return None

    def get_password_hash_by_login(self, login: str) -> Optional[str]:
        """
        Get user password hash by login.

        Args:
            login: User login

        Returns:
            Password hash if found, None otherwise
        """
        user_model = self.db.query(UserModel).filter(UserModel.login == login).first()

        if user_model:
            return user_model.hashed_password

        return None

    def list(
        self,
        offset: int = 0,
        limit: int = 20,
        status: Optional[str] = None
    ) -> Tuple[List[User], int]:
        """
        List users with pagination.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter

        Returns:
            Tuple of (list of users, total count)
        """
        query = self.db.query(UserModel)

        if status:
            query = query.filter(UserModel.status == status)

        total = query.count()

        user_models = query.offset(offset).limit(limit).all()
        users = [self._to_domain(model) for model in user_models]

        return users, total

    def update(
        self,
        user_id: int,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        admin: Optional[bool] = None,
        status: Optional[str] = None
    ) -> Optional[User]:
        """
        Update user.

        Args:
            user_id: User ID
            email: New email
            first_name: New first name
            last_name: New last name
            admin: New admin flag
            status: New status

        Returns:
            Updated user domain model if found, None otherwise
        """
        user_model = self.db.query(UserModel).filter(UserModel.id == user_id).first()

        if not user_model:
            return None

        if email is not None:
            user_model.email = email
        if first_name is not None:
            user_model.first_name = first_name
        if last_name is not None:
            user_model.last_name = last_name
        if admin is not None:
            user_model.admin = admin
        if status is not None:
            user_model.status = status

        self.db.commit()
        self.db.refresh(user_model)

        return self._to_domain(user_model)

    def update_password(self, user_id: int, hashed_password: str) -> bool:
        """
        Update user password.

        Args:
            user_id: User ID
            hashed_password: New hashed password

        Returns:
            True if updated, False if user not found
        """
        user_model = self.db.query(UserModel).filter(UserModel.id == user_id).first()

        if not user_model:
            return False

        user_model.hashed_password = hashed_password
        self.db.commit()

        return True

    def delete(self, user_id: int) -> bool:
        """
        Delete user.

        Args:
            user_id: User ID

        Returns:
            True if deleted, False if user not found
        """
        user_model = self.db.query(UserModel).filter(UserModel.id == user_id).first()

        if not user_model:
            return False

        self.db.delete(user_model)
        self.db.commit()

        return True

    def exists_by_login(self, login: str) -> bool:
        """
        Check if user exists by login.

        Args:
            login: User login

        Returns:
            True if user exists, False otherwise
        """
        return self.db.query(
            self.db.query(UserModel).filter(UserModel.login == login).exists()
        ).scalar()

    def exists_by_email(self, email: str) -> bool:
        """
        Check if user exists by email.

        Args:
            email: User email

        Returns:
            True if user exists, False otherwise
        """
        return self.db.query(
            self.db.query(UserModel).filter(UserModel.email == email).exists()
        ).scalar()
