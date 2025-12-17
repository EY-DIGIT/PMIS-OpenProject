"""
Integration test for Roles module.
"""
import pytest
from sqlalchemy.orm import Session
from app.api.v3.roles.services.create import create_role
from app.api.v3.roles.services.get import get_role_by_id, get_role_by_name
from app.api.v3.roles.services.list import list_roles
from app.api.v3.roles.services.update import update_role
from app.api.v3.roles.services.delete import delete_role
from app.infrastructure.db.repositories.role_repository import RoleRepository
from app.infrastructure.db.session import get_db, Base, engine


class TestRolesIntegration:
    """Integration tests for Roles module."""

    @pytest.fixture(scope="function", autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        # Create tables
        Base.metadata.create_all(bind=engine)
        yield
        # Drop tables
        Base.metadata.drop_all(bind=engine)

    @pytest.fixture
    def db(self):
        """Get database session."""
        db_session = next(get_db())
        return db_session

    def test_create_role(self, db: Session):
        """Test creating a role."""
        result = create_role(
            db=db,
            name="Editor",
            permissions=["projects:view", "projects:edit"],
            builtin=False
        )

        assert result.is_success()
        assert result.data.name == "Editor"
        assert result.data.permissions == ["projects:view", "projects:edit"]
        assert result.data.builtin is False

    def test_create_role_duplicate_name(self, db: Session):
        """Test creating a role with duplicate name fails."""
        # Create first role
        create_role(
            db=db,
            name="Editor",
            permissions=["projects:view"],
            builtin=False
        )

        # Try to create duplicate
        result = create_role(
            db=db,
            name="Editor",
            permissions=["projects:view"],
            builtin=False
        )

        assert result.is_failure()
        assert result.error_type == "already_exists"

    def test_create_role_invalid_name(self, db: Session):
        """Test creating a role with invalid name."""
        result = create_role(
            db=db,
            name="",
            permissions=["projects:view"],
            builtin=False
        )

        assert result.is_failure()
        assert result.error_type == "validation_error"

    def test_get_role_by_id(self, db: Session):
        """Test getting a role by ID."""
        # Create role
        create_result = create_role(
            db=db,
            name="Editor",
            permissions=["projects:view"],
            builtin=False
        )

        role_id = create_result.data.id

        # Get role
        result = get_role_by_id(db=db, role_id=role_id)

        assert result.is_success()
        assert result.data.id == role_id
        assert result.data.name == "Editor"

    def test_get_role_not_found(self, db: Session):
        """Test getting a non-existent role."""
        result = get_role_by_id(db=db, role_id=999)

        assert result.is_failure()
        assert result.error_type == "not_found"

    def test_get_role_by_name(self, db: Session):
        """Test getting a role by name."""
        # Create role
        create_role(
            db=db,
            name="Editor",
            permissions=["projects:view"],
            builtin=False
        )

        # Get role by name
        result = get_role_by_name(db=db, name="Editor")

        assert result.is_success()
        assert result.data.name == "Editor"

    def test_list_roles(self, db: Session):
        """Test listing roles with pagination."""
        # Create multiple roles
        for i in range(5):
            create_role(
                db=db,
                name=f"Role{i}",
                permissions=["projects:view"],
                builtin=False
            )

        # List roles
        result = list_roles(db=db, offset=0, limit=3)

        assert result.is_success()
        roles, total = result.data
        assert len(roles) == 3
        assert total == 5

    def test_update_role(self, db: Session):
        """Test updating a role."""
        # Create role
        create_result = create_role(
            db=db,
            name="Editor",
            permissions=["projects:view"],
            builtin=False
        )

        role_id = create_result.data.id

        # Update role
        result = update_role(
            db=db,
            role_id=role_id,
            name="Reviewer",
            permissions=["projects:view", "projects:comment"]
        )

        assert result.is_success()
        assert result.data.name == "Reviewer"
        assert result.data.permissions == ["projects:view", "projects:comment"]

    def test_update_builtin_role_fails(self, db: Session):
        """Test updating a builtin role fails."""
        # Create builtin role
        create_result = create_role(
            db=db,
            name="Admin",
            permissions=["projects:view"],
            builtin=True
        )

        role_id = create_result.data.id

        # Try to update
        result = update_role(
            db=db,
            role_id=role_id,
            name="SuperAdmin",
            permissions=["projects:view"]
        )

        assert result.is_failure()
        assert result.error_type == "forbidden"

    def test_delete_role(self, db: Session):
        """Test deleting a role."""
        # Create role
        create_result = create_role(
            db=db,
            name="Editor",
            permissions=["projects:view"],
            builtin=False
        )

        role_id = create_result.data.id

        # Delete role
        result = delete_role(db=db, role_id=role_id)

        assert result.is_success()

        # Verify deletion
        verify_result = get_role_by_id(db=db, role_id=role_id)
        assert verify_result.is_failure()

    def test_delete_builtin_role_fails(self, db: Session):
        """Test deleting a builtin role fails."""
        # Create builtin role
        create_result = create_role(
            db=db,
            name="Admin",
            permissions=["projects:view"],
            builtin=True
        )

        role_id = create_result.data.id

        # Try to delete
        result = delete_role(db=db, role_id=role_id)

        assert result.is_failure()
        assert result.error_type == "forbidden"

    def test_role_to_dict(self, db: Session):
        """Test role domain model to_dict conversion."""
        # Create role
        create_result = create_role(
            db=db,
            name="Editor",
            permissions=["projects:view", "projects:edit"],
            builtin=False
        )

        role = create_result.data
        role_dict = role.to_dict()

        assert role_dict["id"] == role.id
        assert role_dict["name"] == "Editor"
        assert role_dict["permissions"] == ["projects:view", "projects:edit"]
        assert role_dict["builtin"] is False
        assert "created_at" in role_dict
        assert "updated_at" in role_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
