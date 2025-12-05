"""
FastAPI router for Membership endpoints.

Implements OpenProject-compatible REST API v3 membership endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

try:
    from ..database import get_db
    from ..models import Member, Project, User
    from ..db_models import DBUser  # SQLAlchemy User model for queries
    from ..schemas.member import MemberCreate, MemberUpdate, MemberResponse
    from ..services.member_service import MemberService
except ImportError:
    from database import get_db
    from models import Member, Project, User
    from db_models import DBUser  # SQLAlchemy User model for queries
    from schemas.member import MemberCreate, MemberUpdate, MemberResponse
    from services.member_service import MemberService


router = APIRouter(prefix="/api/v3", tags=["memberships"])


# Dependency to get current user (reuse from projects router)
def get_current_user(db: Session = Depends(get_db)) -> User:
    """
    Get current authenticated user.

    TODO: Implement actual authentication (JWT, session, etc.)
    For now, returns a mock admin user for testing.
    """
    # This is a placeholder - replace with actual auth implementation
    user = db.query(DBUser).filter_by(admin=True).first()
    if not user:
        # Create a test admin user if none exists
        try:
            from ..models import UserStatus
        except ImportError:
            from models import UserStatus
        user = DBUser(
            login="admin",
            firstname="Admin",
            lastname="User",
            mail="admin@example.com",
            status=UserStatus.ACTIVE.value,  # Use enum value
            admin=True
        )
        db.add(user)
        db.commit()
    return user


@router.get("/projects/{project_id}/memberships", response_model=List[MemberResponse])
def list_project_memberships(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all members of a project"""
    service = MemberService(db, current_user)
    result = service.list_project_members(project_id)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.post("/projects/{project_id}/memberships", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def create_membership(
    project_id: int,
    data: MemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add member to project"""
    # Ensure project_id matches
    data.project_id = project_id

    service = MemberService(db, current_user)
    result = service.add_member(project_id, data)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.get("/memberships/{member_id}", response_model=MemberResponse)
def get_membership(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get single membership"""
    member = db.query(Member).get(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Membership not found")

    # Check if user can view members
    if not member.project.allows_to(current_user, 'view_members'):
        raise HTTPException(status_code=403, detail="Access denied")

    return member


@router.patch("/memberships/{member_id}", response_model=MemberResponse)
def update_membership(
    member_id: int,
    data: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update member roles"""
    service = MemberService(db, current_user)
    result = service.update_member(member_id, data)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.delete("/memberships/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_membership(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove member from project"""
    service = MemberService(db, current_user)
    result = service.remove_member(member_id)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return None
