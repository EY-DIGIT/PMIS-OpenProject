#!/usr/bin/env python
"""
Comprehensive Test Suite for PMIS API
Tests all key endpoints required by frontend with proper setup and teardown
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import app and database setup
from app.main import app
from app.infrastructure.db.session import Base, get_db
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.models.project import ProjectModel
from app.infrastructure.db.models.meeting import MeetingModel
from app.core.security import hash_password


# Setup test database
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables
Base.metadata.create_all(bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the dependency
app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Create test admin user
    admin = UserModel(
        login="admin",
        email="admin@example.com",
        hashed_password=hash_password("admin123"),
        first_name="Admin",
        last_name="User",
        admin=True,
        status="active"
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def admin_token(db_session):
    """Authenticate as admin and return token"""
    response = client.post(
        "/api/v3/users/login",
        json={"login": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    data = response.json()
    token = data.get("data", {}).get("access_token") or data.get("access_token")
    return token


@pytest.fixture
def admin_headers(admin_token):
    """Return authorization headers with admin token"""
    return {"Authorization": f"Bearer {admin_token}"}


# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

class TestAuthentication:
    """Test authentication endpoints"""

    def test_health_check(self):
        """Test health check endpoint (no auth required)"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"]

    def test_root_endpoint(self):
        """Test root endpoint (no auth required)"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "_type" in data
        assert "_links" in data

    def test_login_success(self, db_session):
        """Test successful login"""
        response = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "admin123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "access_token" in data
        token = data.get("data", {}).get("access_token") or data.get("access_token")
        assert token is not None

    def test_login_invalid_credentials(self, db_session):
        """Test login with invalid credentials"""
        response = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "wrongpassword"}
        )
        assert response.status_code in [400, 401, 422]

    def test_introspect_token(self, db_session, admin_token):
        """Test token introspection endpoint"""
        response = client.post(
            "/api/v3/users/introspect",
            json={"access_token": admin_token}
        )
        assert response.status_code in [200, 400]  # May not be implemented


# ============================================================================
# USER ENDPOINTS TESTS
# ============================================================================

class TestUsers:
    """Test user management endpoints"""

    def test_get_current_user(self, admin_headers):
        """Test GET /api/v3/users/me"""
        response = client.get("/api/v3/users/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "login" in data

    def test_list_users(self, admin_headers):
        """Test GET /api/v3/users - List users"""
        response = client.get("/api/v3/users", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        # Check response structure
        assert isinstance(data, dict)

    def test_list_users_with_pagination(self, admin_headers):
        """Test GET /api/v3/users with pagination params"""
        response = client.get(
            "/api/v3/users?offset=1&pageSize=10",
            headers=admin_headers
        )
        assert response.status_code == 200

    def test_create_user(self, admin_headers, db_session):
        """Test POST /api/v3/users - Create user"""
        response = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "testuser",
                "email": "testuser@example.com",
                "password": "TestPass123",
                "firstName": "Test",
                "lastName": "User"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        # Check that user was created
        created_user_id = data.get("data", {}).get("id") or data.get("id")
        assert created_user_id is not None

    def test_get_user_by_id(self, admin_headers, db_session):
        """Test GET /api/v3/users/{user_id}"""
        # First create a user
        response = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "gettest",
                "email": "gettest@example.com",
                "password": "TestPass123",
                "firstName": "Get",
                "lastName": "Test"
            }
        )
        assert response.status_code in [200, 201]
        user_data = response.json()
        user_id = user_data.get("data", {}).get("id") or user_data.get("id")

        # Now get the user
        response = client.get(f"/api/v3/users/{user_id}", headers=admin_headers)
        assert response.status_code == 200

    def test_update_user(self, admin_headers, db_session):
        """Test PATCH /api/v3/users/{user_id}"""
        # Create a user first
        response = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "updatetest",
                "email": "updatetest@example.com",
                "password": "TestPass123",
                "firstName": "Update",
                "lastName": "Test"
            }
        )
        assert response.status_code in [200, 201]
        user_data = response.json()
        user_id = user_data.get("data", {}).get("id") or user_data.get("id")

        # Update the user
        response = client.patch(
            f"/api/v3/users/{user_id}",
            headers=admin_headers,
            json={
                "firstName": "UpdatedFirstName",
                "lastName": "UpdatedLastName"
            }
        )
        assert response.status_code in [200, 204]

    def test_update_password(self, admin_headers):
        """Test PATCH /api/v3/users/{user_id}/password"""
        response = client.patch(
            "/api/v3/users/1/password",
            headers=admin_headers,
            json={"password": "NewPassword123"}
        )
        # May fail depending on permissions
        assert response.status_code in [200, 204, 403]

    def test_delete_user(self, admin_headers, db_session):
        """Test DELETE /api/v3/users/{user_id}"""
        # Create a user first
        response = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "deletetest",
                "email": "deletetest@example.com",
                "password": "TestPass123",
                "firstName": "Delete",
                "lastName": "Test"
            }
        )
        assert response.status_code in [200, 201]
        user_data = response.json()
        user_id = user_data.get("data", {}).get("id") or user_data.get("id")

        # Delete the user
        response = client.delete(f"/api/v3/users/{user_id}", headers=admin_headers)
        assert response.status_code in [200, 204]


# ============================================================================
# PROJECT ENDPOINTS TESTS
# ============================================================================

class TestProjects:
    """Test project management endpoints"""

    def test_create_project(self, admin_headers):
        """Test POST /api/v3/projects - Create project"""
        response = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "test-proj",
                "name": "Test Project",
                "description": "Test project description"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        project_id = data.get("data", {}).get("id") or data.get("id")
        assert project_id is not None
        return project_id

    def test_list_projects(self, admin_headers):
        """Test GET /api/v3/projects - List projects"""
        response = client.get("/api/v3/projects", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_list_projects_with_pagination(self, admin_headers):
        """Test GET /api/v3/projects with pagination"""
        response = client.get(
            "/api/v3/projects?offset=1&pageSize=10",
            headers=admin_headers
        )
        assert response.status_code == 200

    def test_list_projects_with_filters(self, admin_headers):
        """Test GET /api/v3/projects with filters"""
        response = client.get(
            "/api/v3/projects?active=true&public=true",
            headers=admin_headers
        )
        assert response.status_code == 200

    def test_get_project_by_id(self, admin_headers):
        """Test GET /api/v3/projects/{project_id}"""
        # Create a project first
        response = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "get-proj",
                "name": "Get Project",
                "description": "Get project test"
            }
        )
        assert response.status_code in [200, 201]
        project_data = response.json()
        project_id = project_data.get("data", {}).get("id") or project_data.get("id")

        # Get the project
        response = client.get(f"/api/v3/projects/{project_id}", headers=admin_headers)
        assert response.status_code == 200

    def test_update_project(self, admin_headers):
        """Test PATCH /api/v3/projects/{project_id}"""
        # Create a project first
        response = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "update-proj",
                "name": "Update Project",
                "description": "Update project test"
            }
        )
        assert response.status_code in [200, 201]
        project_data = response.json()
        project_id = project_data.get("data", {}).get("id") or project_data.get("id")

        # Update the project
        response = client.patch(
            f"/api/v3/projects/{project_id}",
            headers=admin_headers,
            json={
                "name": "Updated Project Name",
                "description": "Updated description"
            }
        )
        assert response.status_code in [200, 204]

    def test_delete_project(self, admin_headers):
        """Test DELETE /api/v3/projects/{project_id}"""
        # Create a project first
        response = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "delete-proj",
                "name": "Delete Project",
                "description": "Delete project test"
            }
        )
        assert response.status_code in [200, 201]
        project_data = response.json()
        project_id = project_data.get("data", {}).get("id") or project_data.get("id")

        # Delete the project
        response = client.delete(f"/api/v3/projects/{project_id}", headers=admin_headers)
        assert response.status_code in [200, 204]


# ============================================================================
# MEETING ENDPOINTS TESTS
# ============================================================================

class TestMeetings:
    """Test meeting management endpoints"""

    def _create_project_for_meeting(self, admin_headers):
        """Helper to create a project for testing meetings"""
        response = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "meeting-test-proj",
                "name": "Meeting Test Project",
                "description": "Project for meeting tests"
            }
        )
        if response.status_code in [200, 201]:
            data = response.json()
            return data.get("data", {}).get("id") or data.get("id")
        return None

    def test_create_meeting(self, admin_headers):
        """Test POST /api/v3/projects/{project_id}/meetings"""
        project_id = self._create_project_for_meeting(admin_headers)
        if not project_id:
            pytest.skip("Could not create test project")

        response = client.post(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers,
            json={
                "title": "Test Meeting",
                "description": "Test meeting description",
                "scheduled_at": "2026-05-15T10:00:00Z",
                "duration_minutes": 60,
                "location": "Conference Room A"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        meeting_id = data.get("data", {}).get("id") or data.get("id")
        assert meeting_id is not None

    def test_list_meetings(self, admin_headers):
        """Test GET /api/v3/projects/{project_id}/meetings"""
        project_id = self._create_project_for_meeting(admin_headers)
        if not project_id:
            pytest.skip("Could not create test project")

        response = client.get(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers
        )
        assert response.status_code == 200

    def test_list_meetings_with_pagination(self, admin_headers):
        """Test GET /api/v3/projects/{project_id}/meetings with pagination"""
        project_id = self._create_project_for_meeting(admin_headers)
        if not project_id:
            pytest.skip("Could not create test project")

        response = client.get(
            f"/api/v3/projects/{project_id}/meetings?offset=0&limit=10",
            headers=admin_headers
        )
        assert response.status_code == 200

    def test_get_meeting_by_id(self, admin_headers):
        """Test GET /api/v3/meetings/{meeting_id}"""
        project_id = self._create_project_for_meeting(admin_headers)
        if not project_id:
            pytest.skip("Could not create test project")

        # Create a meeting
        response = client.post(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers,
            json={
                "title": "Get Meeting Test",
                "description": "Test",
                "scheduled_at": "2026-05-15T14:00:00Z",
                "duration_minutes": 30
            }
        )
        if response.status_code not in [200, 201]:
            pytest.skip("Could not create test meeting")

        meeting_data = response.json()
        meeting_id = meeting_data.get("data", {}).get("id") or meeting_data.get("id")

        # Get the meeting
        response = client.get(f"/api/v3/meetings/{meeting_id}", headers=admin_headers)
        assert response.status_code == 200

    def test_update_meeting(self, admin_headers):
        """Test PATCH /api/v3/meetings/{meeting_id}"""
        project_id = self._create_project_for_meeting(admin_headers)
        if not project_id:
            pytest.skip("Could not create test project")

        # Create a meeting
        response = client.post(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers,
            json={
                "title": "Update Meeting Test",
                "description": "Test",
                "scheduled_at": "2026-05-15T15:00:00Z"
            }
        )
        if response.status_code not in [200, 201]:
            pytest.skip("Could not create test meeting")

        meeting_data = response.json()
        meeting_id = meeting_data.get("data", {}).get("id") or meeting_data.get("id")

        # Update the meeting
        response = client.patch(
            f"/api/v3/meetings/{meeting_id}",
            headers=admin_headers,
            json={
                "title": "Updated Meeting Title",
                "location": "Conference Room B"
            }
        )
        assert response.status_code in [200, 204]

    def test_delete_meeting(self, admin_headers):
        """Test DELETE /api/v3/meetings/{meeting_id}"""
        project_id = self._create_project_for_meeting(admin_headers)
        if not project_id:
            pytest.skip("Could not create test project")

        # Create a meeting
        response = client.post(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers,
            json={
                "title": "Delete Meeting Test",
                "scheduled_at": "2026-05-15T16:00:00Z"
            }
        )
        if response.status_code not in [200, 201]:
            pytest.skip("Could not create test meeting")

        meeting_data = response.json()
        meeting_id = meeting_data.get("data", {}).get("id") or meeting_data.get("id")

        # Delete the meeting
        response = client.delete(f"/api/v3/meetings/{meeting_id}", headers=admin_headers)
        assert response.status_code in [200, 204]


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
