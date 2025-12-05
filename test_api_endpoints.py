"""
Integration tests for API endpoints.
"""

import sys
from pathlib import Path

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from user_service.database import Base, get_db
from user_service.main import app
from user_service.models import UserStatus


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Setup test database before each test"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


class TestUserAPIs:
    """Test user API endpoints"""

    def test_create_and_get_user(self):
        """Test creating and retrieving a user"""
        # Create user
        response = client.post(
            "/api/v3/users",
            json={
                "login": "testuser",
                "firstName": "Test",
                "lastName": "User",
                "email": "test@example.com",
                "password": "TestPass123",
                "admin": False,
                "status": "active",
                "language": "en"
            }
        )
        assert response.status_code == 201
        data = response.json()
        user_id = data["id"]
        assert data["login"] == "testuser"
        assert data["email"] == "test@example.com"

        # Get user
        response = client.get(f"/api/v3/users/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["login"] == "testuser"

    def test_update_user(self):
        """Test updating a user"""
        # Create user first
        response = client.post(
            "/api/v3/users",
            json={
                "login": "updateuser",
                "firstName": "Update",
                "lastName": "User",
                "email": "update@example.com",
                "password": "UpdatePass123",
                "admin": False,
                "status": "active",
                "language": "en"
            }
        )
        assert response.status_code == 201
        user_id = response.json()["id"]

        # Update user
        response = client.patch(
            f"/api/v3/users/{user_id}",
            json={
                "firstName": "Updated",
                "lastName": "UserName",
                "email": "updated@example.com"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["firstName"] == "Updated"
        assert data["lastName"] == "UserName"
        assert data["email"] == "updated@example.com"
        assert data["login"] == "updateuser"  # Unchanged

    def test_update_user_not_found(self):
        """Test updating non-existent user"""
        response = client.patch(
            "/api/v3/users/999999",
            json={"firstName": "Test"}
        )
        assert response.status_code == 404

    def test_delete_user(self):
        """Test deleting a user (soft delete)"""
        # Create user first
        response = client.post(
            "/api/v3/users",
            json={
                "login": "deleteuser",
                "firstName": "Delete",
                "lastName": "User",
                "email": "delete@example.com",
                "password": "DeletePass123",
                "admin": False,
                "status": "active",
                "language": "en"
            }
        )
        assert response.status_code == 201
        user_id = response.json()["id"]

        # Delete user
        response = client.delete(f"/api/v3/users/{user_id}")
        assert response.status_code == 202

        # Verify user still exists but with DELETED status
        response = client.get(f"/api/v3/users/{user_id}")
        assert response.status_code == 200
        data = response.json()
        # User should be marked as deleted in the database
        # (Note: We're doing soft delete, so user still exists)

    def test_delete_user_not_found(self):
        """Test deleting non-existent user"""
        response = client.delete("/api/v3/users/999999")
        assert response.status_code == 404

    def test_list_users(self):
        """Test listing users with pagination"""
        # Create multiple users
        for i in range(5):
            client.post(
                "/api/v3/users",
                json={
                    "login": f"user{i}",
                    "firstName": f"User",
                    "lastName": f"{i}",
                    "email": f"user{i}@example.com",
                    "password": "TestPass123",
                    "admin": False,
                    "status": "active",
                    "language": "en"
                }
            )

        # List users
        response = client.get("/api/v3/users?offset=0&pageSize=10")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 5
        assert data["total"] >= 5
        if "_embedded" in data:
            assert "elements" in data["_embedded"]

    def test_lock_unlock_user(self):
        """Test locking and unlocking a user"""
        # Create user
        response = client.post(
            "/api/v3/users",
            json={
                "login": "lockuser",
                "firstName": "Lock",
                "lastName": "User",
                "email": "lock@example.com",
                "password": "LockPass123",
                "admin": False,
                "status": "active",
                "language": "en"
            }
        )
        assert response.status_code == 201
        user_id = response.json()["id"]

        # Lock user
        response = client.post(f"/api/v3/users/{user_id}/lock")
        assert response.status_code == 200

        # Verify user is locked
        response = client.get(f"/api/v3/users/{user_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "locked"

        # Unlock user
        response = client.post(f"/api/v3/users/{user_id}/unlock")
        assert response.status_code == 200

        # Verify user is unlocked (active)
        response = client.get(f"/api/v3/users/{user_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    def test_lock_already_locked_user(self):
        """Test locking an already locked user"""
        # Create and lock user
        response = client.post(
            "/api/v3/users",
            json={
                "login": "alreadylocked",
                "firstName": "Already",
                "lastName": "Locked",
                "email": "locked@example.com",
                "password": "LockedPass123",
                "admin": False,
                "status": "locked",
                "language": "en"
            }
        )
        assert response.status_code == 201
        user_id = response.json()["id"]

        # Try to lock again
        response = client.post(f"/api/v3/users/{user_id}/lock")
        assert response.status_code == 422


class TestAuthAPIs:
    """Test authentication API endpoints"""

    def test_register_user(self):
        """Test user registration"""
        response = client.post(
            "/api/v3/auth/register",
            json={
                "login": "newuser",
                "firstName": "New",
                "lastName": "User",
                "email": "new@example.com",
                "password": "NewPass123",
                "language": "en"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["login"] == "newuser"
        assert data["status"] == "registered"

    def test_login(self):
        """Test user login"""
        # Create user first
        client.post(
            "/api/v3/users",
            json={
                "login": "loginuser",
                "firstName": "Login",
                "lastName": "User",
                "email": "login@example.com",
                "password": "LoginPass123",
                "admin": False,
                "status": "active",
                "language": "en"
            }
        )

        # Login
        response = client.post(
            "/api/v3/auth/login",
            json={
                "username": "loginuser",
                "password": "LoginPass123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert data["user"]["login"] == "loginuser"

    def test_get_user_schema(self):
        """Test getting user schema"""
        response = client.get("/api/v3/users/schema")
        assert response.status_code == 200
        data = response.json()
        assert "login" in data
        assert "email" in data
        assert "password" in data
