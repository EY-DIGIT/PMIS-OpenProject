"""
Test suite for Project module.

Tests models, services, and API endpoints.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from database import Base
from models import (
    Project, Member, MemberRole, Role, RolePermission,
    EnabledModule, User, UserStatus
)
from services.project_service import ProjectService
from services.member_service import MemberService
from schemas.project import ProjectCreate, ProjectUpdate
from schemas.member import MemberCreate, MemberUpdate
from utils.permissions import seed_default_roles


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_projects.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create test database and session"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def admin_user(db):
    """Create admin user for testing"""
    user = User(
        login="admin",
        firstname="Admin",
        lastname="User",
        mail="admin@test.com",
        status=UserStatus.ACTIVE,
        admin=True
    )
    user.password = "password123"
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def regular_user(db):
    """Create regular user for testing"""
    user = User(
        login="user",
        firstname="Regular",
        lastname="User",
        mail="user@test.com",
        status=UserStatus.ACTIVE,
        admin=False
    )
    user.password = "password123"
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def project_admin_role(db):
    """Create project admin role"""
    role = Role(name="Project admin", position=1)
    db.add(role)
    db.flush()

    # Add permissions
    permissions = [
        'view_project', 'edit_project', 'manage_members',
        'add_subprojects', 'archive_project', 'copy_projects'
    ]
    for perm in permissions:
        rp = RolePermission(role_id=role.id, permission=perm)
        db.add(rp)

    db.commit()
    db.refresh(role)
    return role


@pytest.fixture
def member_role(db):
    """Create member role"""
    role = Role(name="Member", position=2)
    db.add(role)
    db.flush()

    # Add permissions
    permissions = ['view_project', 'view_members']
    for perm in permissions:
        rp = RolePermission(role_id=role.id, permission=perm)
        db.add(rp)

    db.commit()
    db.refresh(role)
    return role


# Model Tests

def test_project_creation(db):
    """Test creating a project"""
    project = Project(
        name="Test Project",
        identifier="test-project",
        description="Test description",
        public=True,
        active=True
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    assert project.id is not None
    assert project.name == "Test Project"
    assert project.identifier == "test-project"
    assert project.active is True
    assert project.public is True


def test_project_identifier_validation(db):
    """Test project identifier validation"""
    # Invalid: uppercase
    with pytest.raises(ValueError, match="lowercase"):
        project = Project(name="Test", identifier="TEST-PROJECT")
        db.add(project)
        db.commit()

    # Invalid: purely numeric
    with pytest.raises(ValueError, match="purely numeric"):
        project = Project(name="Test", identifier="123")
        db.add(project)
        db.commit()

    # Invalid: reserved word
    with pytest.raises(ValueError, match="reserved"):
        project = Project(name="Test", identifier="new")
        db.add(project)
        db.commit()


def test_member_creation(db, admin_user, project_admin_role):
    """Test creating a member"""
    project = Project(name="Test", identifier="test")
    db.add(project)
    db.flush()

    member = Member(user_id=admin_user.id, project_id=project.id)
    db.add(member)
    db.flush()

    member_role = MemberRole(member_id=member.id, role_id=project_admin_role.id)
    db.add(member_role)
    db.commit()

    assert member.id is not None
    assert member.user_id == admin_user.id
    assert len(member.roles) == 1
    assert member.roles[0].name == "Project admin"


def test_role_permissions(db, project_admin_role):
    """Test role permission methods"""
    assert project_admin_role.has_permission('view_project')
    assert project_admin_role.has_permission('edit_project')
    assert not project_admin_role.has_permission('nonexistent')

    permissions = project_admin_role.get_permissions()
    assert 'view_project' in permissions
    assert 'manage_members' in permissions


# Service Tests

def test_project_service_create(db, admin_user, project_admin_role):
    """Test ProjectService.create_project"""
    service = ProjectService(db, admin_user)

    data = ProjectCreate(
        name="New Project",
        identifier="new-project",
        description="Created via service",
        public=False
    )

    result = service.create_project(data)

    assert result.is_success()
    assert result.result.name == "New Project"
    assert result.result.identifier == "new-project"
    assert result.result.public is False

    # Check that creator was added as member
    assert len(result.result.members) == 1
    assert result.result.members[0].user_id == admin_user.id


def test_project_service_update(db, admin_user, project_admin_role):
    """Test ProjectService.update_project"""
    # Create project
    project = Project(name="Old Name", identifier="test")
    db.add(project)
    db.flush()

    # Add user as admin
    member = Member(user_id=admin_user.id, project_id=project.id)
    db.add(member)
    db.flush()

    member_role = MemberRole(member_id=member.id, role_id=project_admin_role.id)
    db.add(member_role)
    db.commit()

    # Update project
    service = ProjectService(db, admin_user)
    data = ProjectUpdate(name="New Name", description="Updated")

    result = service.update_project(project.id, data)

    assert result.is_success()
    assert result.result.name == "New Name"
    assert result.result.description == "Updated"


def test_project_service_archive(db, admin_user, project_admin_role):
    """Test ProjectService.archive_project"""
    # Create project
    project = Project(name="Test", identifier="test", active=True)
    db.add(project)
    db.flush()

    # Add user as admin
    member = Member(user_id=admin_user.id, project_id=project.id)
    db.add(member)
    db.flush()

    member_role = MemberRole(member_id=member.id, role_id=project_admin_role.id)
    db.add(member_role)
    db.commit()

    # Archive project
    service = ProjectService(db, admin_user)
    result = service.archive_project(project.id)

    assert result.is_success()
    assert result.result.active is False


def test_member_service_add(db, admin_user, regular_user, project_admin_role, member_role):
    """Test MemberService.add_member"""
    # Create project with admin
    project = Project(name="Test", identifier="test")
    db.add(project)
    db.flush()

    admin_member = Member(user_id=admin_user.id, project_id=project.id)
    db.add(admin_member)
    db.flush()

    admin_member_role = MemberRole(member_id=admin_member.id, role_id=project_admin_role.id)
    db.add(admin_member_role)
    db.commit()

    # Add regular user as member
    service = MemberService(db, admin_user)
    data = MemberCreate(
        user_id=regular_user.id,
        project_id=project.id,
        role_ids=[member_role.id]
    )

    result = service.add_member(project.id, data)

    assert result.is_success()
    assert result.result.user_id == regular_user.id
    assert result.result.project_id == project.id
    assert len(result.result.roles) == 1


def test_member_service_update(db, admin_user, regular_user, project_admin_role, member_role):
    """Test MemberService.update_member"""
    # Create project with members
    project = Project(name="Test", identifier="test")
    db.add(project)
    db.flush()

    # Add admin
    admin_member = Member(user_id=admin_user.id, project_id=project.id)
    db.add(admin_member)
    db.flush()
    admin_mr = MemberRole(member_id=admin_member.id, role_id=project_admin_role.id)
    db.add(admin_mr)

    # Add regular user
    user_member = Member(user_id=regular_user.id, project_id=project.id)
    db.add(user_member)
    db.flush()
    user_mr = MemberRole(member_id=user_member.id, role_id=member_role.id)
    db.add(user_mr)
    db.commit()

    # Update regular user's roles
    service = MemberService(db, admin_user)
    data = MemberUpdate(role_ids=[project_admin_role.id])

    result = service.update_member(user_member.id, data)

    assert result.is_success()
    assert len(result.result.roles) == 1
    assert result.result.roles[0].id == project_admin_role.id


def test_member_service_remove(db, admin_user, regular_user, project_admin_role, member_role):
    """Test MemberService.remove_member"""
    # Create project with members
    project = Project(name="Test", identifier="test")
    db.add(project)
    db.flush()

    # Add admin
    admin_member = Member(user_id=admin_user.id, project_id=project.id)
    db.add(admin_member)
    db.flush()
    admin_mr = MemberRole(member_id=admin_member.id, role_id=project_admin_role.id)
    db.add(admin_mr)

    # Add regular user
    user_member = Member(user_id=regular_user.id, project_id=project.id)
    db.add(user_member)
    db.flush()
    user_mr = MemberRole(member_id=user_member.id, role_id=member_role.id)
    db.add(user_mr)
    db.commit()

    # Remove regular user
    service = MemberService(db, admin_user)
    result = service.remove_member(user_member.id)

    assert result.is_success()

    # Verify member is deleted
    deleted_member = db.query(Member).get(user_member.id)
    assert deleted_member is None


# Permission Tests

def test_project_allows_to(db, admin_user, regular_user, project_admin_role, member_role):
    """Test project permission checking"""
    # Create project
    project = Project(name="Test", identifier="test", public=False)
    db.add(project)
    db.flush()

    # Add regular user as member
    member = Member(user_id=regular_user.id, project_id=project.id)
    db.add(member)
    db.flush()

    member_role_link = MemberRole(member_id=member.id, role_id=member_role.id)
    db.add(member_role_link)
    db.commit()

    # Admin can do everything
    assert project.allows_to(admin_user, 'view_project')
    assert project.allows_to(admin_user, 'edit_project')
    assert project.allows_to(admin_user, 'manage_members')

    # Regular user with member role
    assert project.allows_to(regular_user, 'view_project')
    assert project.allows_to(regular_user, 'view_members')
    assert not project.allows_to(regular_user, 'edit_project')
    assert not project.allows_to(regular_user, 'manage_members')


def test_project_visibility(db, admin_user, regular_user):
    """Test project visibility"""
    # Public project
    public_project = Project(name="Public", identifier="public", public=True, active=True)
    db.add(public_project)

    # Private project
    private_project = Project(name="Private", identifier="private", public=False, active=True)
    db.add(private_project)
    db.commit()

    # Admin sees everything
    assert public_project.is_visible(admin_user)
    assert private_project.is_visible(admin_user)

    # Regular user sees only public
    assert public_project.is_visible(regular_user)
    assert not private_project.is_visible(regular_user)


# Integration Tests

def test_seed_default_roles(db):
    """Test seeding default roles"""
    roles = seed_default_roles(db)

    assert len(roles) >= 3  # At least Project admin, Member, Reader

    # Check Project admin role
    project_admin = db.query(Role).filter_by(name="Project admin").first()
    assert project_admin is not None
    assert project_admin.has_permission('view_project')
    assert project_admin.has_permission('edit_project')
    assert project_admin.has_permission('manage_members')


if __name__ == "__main__":
    print("Running Project Module Tests...")
    print("="*60)

    # Run pytest
    pytest.main([__file__, "-v", "--tb=short"])
