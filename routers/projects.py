"""
FastAPI router for Project endpoints.

Implements OpenProject-compatible REST API v3 project endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

try:
    from ..database import get_db
    from ..models import Project, User
    from ..db_models import DBUser  # SQLAlchemy User model for queries
    from ..schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
    from ..services.project_service import ProjectService
except ImportError:
    from database import get_db
    from models import Project, User
    from db_models import DBUser  # SQLAlchemy User model for queries
    from schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
    from services.project_service import ProjectService


router = APIRouter(prefix="/api/v3/projects", tags=["projects"])


# Dependency to get current user (you'll need to implement this based on your auth)
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


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    active: Optional[bool] = Query(None, description="Filter by active status"),
    public: Optional[bool] = Query(None, description="Filter by public status"),
    parent_id: Optional[int] = Query(None, description="Filter by parent project"),
    sort_by: str = Query("name", description="Sort field"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all visible projects.

    Filters:
    - active: true/false (archived projects)
    - public: true/false
    - parent_id: filter by parent project

    Sorting:
    - sort_by: field name (name, created_at, etc.)
    - sort_order: asc/desc

    Pagination:
    - offset: starting position
    - pageSize: items per page (1-100)
    """
    query = db.query(Project)

    # Visibility filter (non-admins only see projects they have access to)
    if not current_user.admin:
        user_project_ids = [m.project_id for m in current_user.members if m.project_id]
        query = query.filter(
            (Project.public == True) | (Project.id.in_(user_project_ids))
        )

    # Apply filters
    if active is not None:
        query = query.filter(Project.active == active)
    if public is not None:
        query = query.filter(Project.public == public)
    if parent_id is not None:
        query = query.filter(Project.parent_id == parent_id)

    # Sorting
    sort_column = getattr(Project, sort_by, Project.name)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Pagination
    projects = query.offset(offset).limit(page_size).all()

    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get single project by ID"""
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check visibility
    if not project.is_visible(current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    return project


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new project"""
    service = ProjectService(db, current_user)
    result = service.create_project(data)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update existing project"""
    service = ProjectService(db, current_user)
    result = service.update_project(project_id, data)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.post("/{project_id}/archive", response_model=ProjectResponse)
def archive_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Archive project and all subprojects"""
    service = ProjectService(db, current_user)
    result = service.archive_project(project_id)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.post("/{project_id}/unarchive", response_model=ProjectResponse)
def unarchive_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Unarchive project"""
    service = ProjectService(db, current_user)
    result = service.unarchive_project(project_id)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.post("/{project_id}/copy", response_model=ProjectResponse)
def copy_project(
    project_id: int,
    data: ProjectCreate,
    copy_members: bool = Query(False, description="Copy project members"),
    copy_modules: bool = Query(True, description="Copy enabled modules"),
    copy_settings: bool = Query(True, description="Copy project settings"),
    copy_status: bool = Query(False, description="Copy project status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Copy project with selective data.

    Options:
    - copy_members: Copy project members (default: false)
    - copy_modules: Copy enabled modules (default: true)
    - copy_settings: Copy project settings (default: true)
    - copy_status: Copy project status (default: false)
    """
    service = ProjectService(db, current_user)
    copy_options = {
        'members': copy_members,
        'modules': copy_modules,
        'settings': copy_settings,
        'status': copy_status,
    }
    result = service.copy_project(project_id, data, copy_options)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return result.result


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete project (admin only)"""
    service = ProjectService(db, current_user)
    result = service.delete_project(project_id)

    if result.is_failure():
        raise HTTPException(status_code=422, detail=result.errors)

    return None
