"""
Users Controller - Handles user-related requests.
"""

from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.user import User
from services.users import (
    UserCreateService,
    UserUpdateService,
    UserDeleteService,
)
from repositories import UserRepository


class UsersController:
    """Controller for user operations"""

    @staticmethod
    def list_users(db: Session, current_user: User, **filters) -> List:
        """List users with filters"""
        # Implementation needed
        return []

    @staticmethod
    def get_user(db: Session, user_id: int, current_user: User):
        """Get a specific user"""
        repo = UserRepository(db)
        user = repo.find_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    @staticmethod
    def create_user(db: Session, user_data: dict, current_user: User):
        """Create a new user"""
        service = UserCreateService(current_user)
        result = service.call(user_data)

        if result.is_failure():
            raise HTTPException(status_code=422, detail=result.errors)

        repo = UserRepository(db)
        return repo.create(result.result)

    @staticmethod
    def update_user(db: Session, user_id: int, user_data: dict, current_user: User):
        """Update a user"""
        repo = UserRepository(db)
        user = repo.find_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        service = UserUpdateService(current_user, user)
        result = service.call(user_data)

        if result.is_failure():
            raise HTTPException(status_code=422, detail=result.errors)

        return repo.update(result.result)

    @staticmethod
    def delete_user(db: Session, user_id: int, current_user: User):
        """Delete a user"""
        repo = UserRepository(db)
        user = repo.find_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        service = UserDeleteService(current_user, user)
        result = service.call()

        if result.is_failure():
            raise HTTPException(status_code=422, detail=result.errors)

        repo.delete(user_id)
