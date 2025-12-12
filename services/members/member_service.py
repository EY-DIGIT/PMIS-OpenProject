"""
MemberService - Business logic for membership operations.

Based on OpenProject stable/16 branch Members services.
"""
from typing import List
from sqlalchemy.orm import Session
from datetime import datetime

try:
    from ..models import Member, MemberRole, Project, User
    from .. import db_models
    from ..schemas.member import MemberCreate, MemberUpdate
    from ..utils import ServiceResult
except ImportError:
    from models import Member, MemberRole, Project, User
    import db_models
    from schemas.member import MemberCreate, MemberUpdate
    from utils import ServiceResult


class MemberService:
    """Service for membership operations"""

    def __init__(self, db: Session, user):
        """
        Initialize MemberService.

        Args:
            db: Database session
            user: Current user object
        """
        self.db = db
        self.user = user

    def add_member(self, project_id: int, data: MemberCreate) -> ServiceResult:
        """
        Add member to project.

        Args:
            project_id: Project ID
            data: MemberCreate schema

        Returns:
            ServiceResult with created Member or errors
        """
        project = self.db.query(Project).get(project_id)
        if not project:
            return ServiceResult.failure_result(
                errors={'project': ['Project not found']},
                message="Project not found"
            )

        # Authorization check
        if not project.allows_to(self.user, 'manage_members'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized to manage members']},
                message="Not authorized to manage members"
            )

        # Validate user exists (use SQLAlchemy-mapped DBUser)
        DBUser = getattr(db_models, 'DBUser', None)
        if DBUser is None:
            # Fallback: original in-memory User class
            user_to_add = self.db.query(User).get(data.user_id)
        else:
            user_to_add = self.db.query(DBUser).get(data.user_id)

        if not user_to_add:
            return ServiceResult.failure_result(
                errors={'user': ['User not found']},
                message="User not found"
            )

        # Check if user is active
        # DBUser.status is an integer in DB models; models.User.status is an Enum
        status_val = getattr(user_to_add, 'status', None)
        if isinstance(status_val, int):
            is_active = (status_val == 1)
        else:
            # assume Enum-like
            is_active = (getattr(status_val, 'value', None) == 1)

        if not is_active:
            return ServiceResult.failure_result(
                errors={'user': ['User is not active']},
                message="User is not active"
            )

        # Check if already a member
        existing = self.db.query(Member).filter_by(
            user_id=data.user_id,
            project_id=project_id
        ).first()

        if existing:
            return ServiceResult.failure_result(
                errors={'member': ['User is already a member of this project']},
                message="User is already a member of this project"
            )

        try:
            # Create member
            member = Member(user_id=data.user_id, project_id=project_id)
            self.db.add(member)
            self.db.flush()

            # Add roles
            for role_id in data.role_ids:
                member_role = MemberRole(member_id=member.id, role_id=role_id)
                self.db.add(member_role)

            self.db.commit()
            self.db.refresh(member)

            return ServiceResult.success_result(
                member,
                message="Member added successfully"
            )

        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'error': [str(e)]},
                message=f"Error adding member: {str(e)}"
            )

    def update_member(self, member_id: int, data: MemberUpdate) -> ServiceResult:
        """
        Update member roles.

        Args:
            member_id: Member ID
            data: MemberUpdate schema

        Returns:
            ServiceResult with updated Member or errors
        """
        member = self.db.query(Member).get(member_id)
        if not member:
            return ServiceResult.failure_result(
                errors={'member': ['Member not found']},
                message="Member not found"
            )

        # Authorization check
        if not member.project.allows_to(self.user, 'manage_members'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized to manage members']},
                message="Not authorized to manage members"
            )

        try:
            # Remove existing direct roles (keep inherited ones)
            for mr in list(member.member_roles):
                if mr.inherited_from is None:
                    self.db.delete(mr)

            self.db.flush()

            # Add new roles
            for role_id in data.role_ids:
                member_role = MemberRole(member_id=member.id, role_id=role_id)
                self.db.add(member_role)

            member.updated_at = int(datetime.utcnow().timestamp())

            self.db.commit()
            self.db.refresh(member)

            return ServiceResult.success_result(
                member,
                message="Member updated successfully"
            )

        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'error': [str(e)]},
                message=f"Error updating member: {str(e)}"
            )

    def remove_member(self, member_id: int) -> ServiceResult:
        """
        Remove member from project.

        If member has inherited roles (from group), only removes direct roles.
        Otherwise, removes entire member record.

        Args:
            member_id: Member ID

        Returns:
            ServiceResult
        """
        member = self.db.query(Member).get(member_id)
        if not member:
            return ServiceResult.failure_result(
                errors={'member': ['Member not found']},
                message="Member not found"
            )

        # Authorization check
        if not member.project.allows_to(self.user, 'manage_members'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized to manage members']},
                message="Not authorized to manage members"
            )

        try:
            # Check if member has inherited roles
            has_inherited = member.has_inherited_roles()

            if has_inherited:
                # Only remove direct roles
                for mr in list(member.member_roles):
                    if mr.inherited_from is None:
                        self.db.delete(mr)

                member.updated_at = int(datetime.utcnow().timestamp())
            else:
                # Remove entire member
                self.db.delete(member)

            self.db.commit()

            return ServiceResult.success_result(
                message="Member removed successfully"
            )

        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'error': [str(e)]},
                message=f"Error removing member: {str(e)}"
            )

    def list_project_members(self, project_id: int) -> ServiceResult:
        """
        List all members of a project.

        Args:
            project_id: Project ID

        Returns:
            ServiceResult with list of Members or errors
        """
        project = self.db.query(Project).get(project_id)
        if not project:
            return ServiceResult.failure_result(
                errors={'project': ['Project not found']},
                message="Project not found"
            )

        # Authorization check
        if not project.allows_to(self.user, 'view_members'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized to view members']},
                message="Not authorized to view members"
            )

        members = self.db.query(Member).filter_by(project_id=project_id).all()

        return ServiceResult.success_result(
            members,
            message=f"Found {len(members)} members"
        )
