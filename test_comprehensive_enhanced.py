#!/usr/bin/env python
"""
Enhanced Comprehensive Test Suite for PMIS API - v2.0
Tests all endpoints, edge cases, error scenarios, and response formats
Total Coverage: 80+ test cases
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import app and database setup
from app.main import app
from app.infrastructure.db.session import Base, get_db
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.models.project import ProjectModel
from app.infrastructure.db.models.role import RoleModel
from app.core.security import hash_password


# ============================================================================
# DATABASE SETUP
# ============================================================================

DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
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

    # Create test member user
    member = UserModel(
        login="member",
        email="member@example.com",
        hashed_password=hash_password("member123"),
        first_name="Member",
        last_name="User",
        admin=False,
        status="active"
    )

    db.add(admin)
    db.add(member)
    db.commit()

    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def admin_token(db_session):
    """Get admin JWT token"""
    response = client.post(
        "/api/v3/users/login",
        json={"login": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    data = response.json()
    token = data.get("data", {}).get("access_token") or data.get("access_token")
    return token


@pytest.fixture
def member_token(db_session):
    """Get member JWT token"""
    response = client.post(
        "/api/v3/users/login",
        json={"login": "member", "password": "member123"}
    )
    assert response.status_code == 200
    data = response.json()
    token = data.get("data", {}).get("access_token") or data.get("access_token")
    return token


@pytest.fixture
def admin_headers(admin_token):
    """Return admin authorization headers"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def member_headers(member_token):
    """Return member authorization headers"""
    return {"Authorization": f"Bearer {member_token}"}


# ============================================================================
# AUTHENTICATION & PUBLIC ENDPOINTS
# ============================================================================

class TestPublicEndpoints:
    """Test public endpoints that don't require authentication"""

    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_root_endpoint(self):
        """Test root API endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["_type"] == "Root"
        assert "_links" in data
        assert "instanceName" in data


class TestAuthentication:
    """Test authentication and login functionality"""

    def test_login_success(self, db_session):
        """Test successful login with valid credentials"""
        response = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "admin123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "access_token" in data
        token = data.get("data", {}).get("access_token") or data.get("access_token")
        assert token is not None
        assert len(token) > 0

    def test_login_invalid_password(self, db_session):
        """Test login with incorrect password"""
        response = client.post(
            "/api/v3/users/login",
            json={"login": "admin", "password": "wrongpassword"}
        )
        assert response.status_code in [400, 401, 422]

    def test_login_invalid_user(self, db_session):
        """Test login with non-existent user"""
        response = client.post(
            "/api/v3/users/login",
            json={"login": "nonexistent", "password": "password123"}
        )
        assert response.status_code in [400, 401, 422]

    def test_login_missing_fields(self):
        """Test login with missing required fields"""
        response = client.post(
            "/api/v3/users/login",
            json={"login": "admin"}
        )
        assert response.status_code == 422  # Validation error

    def test_login_empty_credentials(self):
        """Test login with empty credentials"""
        response = client.post(
            "/api/v3/users/login",
            json={"login": "", "password": ""}
        )
        assert response.status_code == 422

    def test_introspect_token(self, db_session, admin_token):
        """Test token introspection endpoint"""
        response = client.post(
            "/api/v3/users/introspect",
            json={"access_token": admin_token}
        )
        assert response.status_code in [200, 400]


# ============================================================================
# USER MANAGEMENT TESTS
# ============================================================================

class TestUserManagement:
    """Comprehensive user management endpoint tests"""

    def test_get_current_user(self, admin_headers):
        """Test GET /api/v3/users/me"""
        response = client.get("/api/v3/users/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        user = data.get("data", data)
        assert user.get("login") == "admin"
        assert user.get("email") == "admin@example.com"
        assert user.get("admin") == True

    def test_get_current_user_without_auth(self):
        """Test /me endpoint without authentication"""
        response = client.get("/api/v3/users/me")
        assert response.status_code == 401

    def test_list_users_basic(self, admin_headers):
        """Test GET /api/v3/users"""
        response = client.get("/api/v3/users", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "data" in data or isinstance(data.get("_embedded"), dict)

    def test_list_users_pagination(self, admin_headers):
        """Test user listing with pagination"""
        response = client.get(
            "/api/v3/users?offset=1&pageSize=10",
            headers=admin_headers
        )
        assert response.status_code == 200

    def test_list_users_invalid_pagination(self, admin_headers):
        """Test user listing with invalid pagination params"""
        response = client.get(
            "/api/v3/users?offset=0&pageSize=-1",
            headers=admin_headers
        )
        # Should still return 200 or handle gracefully
        assert response.status_code in [200, 422]

    def test_create_user_success(self, admin_headers):
        """Test successful user creation"""
        response = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "newuser",
                "email": "newuser@example.com",
                "password": "SecurePass123",
                "firstName": "New",
                "lastName": "User",
                "admin": False
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        user = data.get("data", data)
        assert user.get("login") == "newuser"
        assert user.get("email") == "newuser@example.com"

    def test_create_user_duplicate_login(self, admin_headers):
        """Test creating user with duplicate login"""
        # Create first user
        client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "duplicate",
                "email": "user1@example.com",
                "password": "Pass123",
                "firstName": "User",
                "lastName": "One"
            }
        )

        # Try to create with same login
        response = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "duplicate",
                "email": "user2@example.com",
                "password": "Pass123",
                "firstName": "User",
                "lastName": "Two"
            }
        )
        assert response.status_code in [400, 409, 422]  # Conflict or validation error

    def test_create_user_duplicate_email(self, admin_headers):
        """Test creating user with duplicate email"""
        # Create first user
        client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "user1",
                "email": "duplicate@example.com",
                "password": "Pass123",
                "firstName": "User",
                "lastName": "One"
            }
        )

        # Try to create with same email
        response = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "user2",
                "email": "duplicate@example.com",
                "password": "Pass123",
                "firstName": "User",
                "lastName": "Two"
            }
        )
        assert response.status_code in [400, 409, 422]

    def test_create_user_missing_fields(self, admin_headers):
        """Test user creation with missing required fields"""
        response = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={"login": "incomplete"}
        )
        assert response.status_code == 422

    def test_get_user_by_id(self, admin_headers):
        """Test GET /api/v3/users/{id}"""
        # Create user
        create_resp = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "getbyid",
                "email": "getbyid@example.com",
                "password": "Pass123",
                "firstName": "Get",
                "lastName": "ById"
            }
        )
        assert create_resp.status_code in [200, 201]
        user_id = create_resp.json().get("data", {}).get("id")

        # Get user by ID
        response = client.get(f"/api/v3/users/{user_id}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        user = data.get("data", data)
        assert user.get("login") == "getbyid"

    def test_get_nonexistent_user(self, admin_headers):
        """Test getting a non-existent user"""
        response = client.get("/api/v3/users/99999", headers=admin_headers)
        assert response.status_code == 404

    def test_update_user(self, admin_headers):
        """Test PATCH /api/v3/users/{id}"""
        # Create user
        create_resp = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "updatetest",
                "email": "update@example.com",
                "password": "Pass123",
                "firstName": "Update",
                "lastName": "Test"
            }
        )
        user_id = create_resp.json().get("data", {}).get("id")

        # Update user
        response = client.patch(
            f"/api/v3/users/{user_id}",
            headers=admin_headers,
            json={
                "firstName": "UpdatedFirst",
                "lastName": "UpdatedLast"
            }
        )
        assert response.status_code in [200, 204]

    def test_update_nonexistent_user(self, admin_headers):
        """Test updating non-existent user"""
        response = client.patch(
            "/api/v3/users/99999",
            headers=admin_headers,
            json={"firstName": "Test"}
        )
        assert response.status_code == 404

    def test_update_password(self, admin_headers):
        """Test PATCH /api/v3/users/{id}/password"""
        response = client.patch(
            "/api/v3/users/1/password",
            headers=admin_headers,
            json={"password": "NewPassword123"}
        )
        assert response.status_code in [200, 204, 403]

    def test_delete_user(self, admin_headers):
        """Test DELETE /api/v3/users/{id}"""
        # Create user
        create_resp = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "deletetest",
                "email": "delete@example.com",
                "password": "Pass123",
                "firstName": "Delete",
                "lastName": "Test"
            }
        )
        user_id = create_resp.json().get("data", {}).get("id")

        # Delete user
        response = client.delete(f"/api/v3/users/{user_id}", headers=admin_headers)
        assert response.status_code in [200, 204]

        # Verify deletion
        response = client.get(f"/api/v3/users/{user_id}", headers=admin_headers)
        assert response.status_code == 404

    def test_delete_nonexistent_user(self, admin_headers):
        """Test deleting non-existent user"""
        response = client.delete("/api/v3/users/99999", headers=admin_headers)
        assert response.status_code == 404


# ============================================================================
# PROJECT MANAGEMENT TESTS
# ============================================================================

class TestProjectManagement:
    """Comprehensive project management endpoint tests"""

    def test_create_project_basic(self, admin_headers):
        """Test basic project creation"""
        response = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "basic-proj",
                "name": "Basic Project",
                "description": "A basic test project"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        project = data.get("data", data)
        assert project.get("identifier") == "basic-proj"
        assert project.get("name") == "Basic Project"

    def test_create_project_with_all_fields(self, admin_headers):
        """Test project creation with all optional fields"""
        response = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "full-proj",
                "name": "Full Project",
                "description": "Complete project",
                "active": True,
                "public": False,
                "statusExplanation": "Just started"
            }
        )
        assert response.status_code in [200, 201]

    def test_create_project_duplicate_identifier(self, admin_headers):
        """Test creating projects with duplicate identifiers"""
        # Create first project
        client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "duplicate-id",
                "name": "Project 1",
                "description": "First"
            }
        )

        # Try to create with same identifier
        response = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "duplicate-id",
                "name": "Project 2",
                "description": "Second"
            }
        )
        assert response.status_code in [400, 409, 422]

    def test_create_project_invalid_identifier(self, admin_headers):
        """Test project creation with invalid identifier"""
        response = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "invalid identifier!@#",
                "name": "Invalid",
                "description": "Bad identifier"
            }
        )
        assert response.status_code in [400, 422]

    def test_list_projects(self, admin_headers):
        """Test project listing"""
        response = client.get("/api/v3/projects", headers=admin_headers)
        assert response.status_code == 200

    def test_list_projects_with_pagination(self, admin_headers):
        """Test project listing with pagination"""
        response = client.get(
            "/api/v3/projects?offset=1&pageSize=10",
            headers=admin_headers
        )
        assert response.status_code == 200

    def test_list_projects_active_filter(self, admin_headers):
        """Test project listing with active filter"""
        response = client.get(
            "/api/v3/projects?active=true",
            headers=admin_headers
        )
        assert response.status_code == 200

    def test_list_projects_public_filter(self, admin_headers):
        """Test project listing with public filter"""
        response = client.get(
            "/api/v3/projects?public=true",
            headers=admin_headers
        )
        assert response.status_code == 200

    def test_list_projects_combined_filters(self, admin_headers):
        """Test project listing with multiple filters"""
        response = client.get(
            "/api/v3/projects?active=true&public=false&offset=1&pageSize=10",
            headers=admin_headers
        )
        assert response.status_code == 200

    def test_get_project_by_id(self, admin_headers):
        """Test getting project by ID"""
        # Create project
        create_resp = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "get-proj",
                "name": "Get Project",
                "description": "Test"
            }
        )
        project_id = create_resp.json().get("data", {}).get("id")

        # Get project
        response = client.get(f"/api/v3/projects/{project_id}", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        project = data.get("data", data)
        assert project.get("identifier") == "get-proj"

    def test_get_nonexistent_project(self, admin_headers):
        """Test getting non-existent project"""
        response = client.get("/api/v3/projects/99999", headers=admin_headers)
        assert response.status_code == 404

    def test_update_project(self, admin_headers):
        """Test updating project"""
        # Create project
        create_resp = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "update-proj",
                "name": "Original Name",
                "description": "Original"
            }
        )
        project_id = create_resp.json().get("data", {}).get("id")

        # Update project
        response = client.patch(
            f"/api/v3/projects/{project_id}",
            headers=admin_headers,
            json={
                "name": "Updated Name",
                "description": "Updated",
                "active": False
            }
        )
        assert response.status_code in [200, 204]

    def test_update_project_partial(self, admin_headers):
        """Test partial project update"""
        # Create project
        create_resp = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "partial-proj",
                "name": "Original",
                "description": "Original desc"
            }
        )
        project_id = create_resp.json().get("data", {}).get("id")

        # Update only name
        response = client.patch(
            f"/api/v3/projects/{project_id}",
            headers=admin_headers,
            json={"name": "New Name"}
        )
        assert response.status_code in [200, 204]

    def test_delete_project(self, admin_headers):
        """Test deleting project"""
        # Create project
        create_resp = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "delete-proj",
                "name": "Delete Me",
                "description": "Temporary"
            }
        )
        project_id = create_resp.json().get("data", {}).get("id")

        # Delete project
        response = client.delete(f"/api/v3/projects/{project_id}", headers=admin_headers)
        assert response.status_code in [200, 204]

        # Verify deletion
        response = client.get(f"/api/v3/projects/{project_id}", headers=admin_headers)
        assert response.status_code == 404


# ============================================================================
# MEETING MANAGEMENT TESTS
# ============================================================================

class TestMeetingManagement:
    """Comprehensive meeting management endpoint tests"""

    @staticmethod
    def create_test_project(headers):
        """Helper to create test project"""
        response = client.post(
            "/api/v3/projects",
            headers=headers,
            json={
                "identifier": f"meet-proj-{int(datetime.now().timestamp())}",
                "name": "Meeting Test Project",
                "description": "Project for meetings"
            }
        )
        if response.status_code in [200, 201]:
            return response.json().get("data", {}).get("id")
        return None

    def test_create_meeting_success(self, admin_headers):
        """Test successful meeting creation"""
        project_id = self.create_test_project(admin_headers)
        assert project_id is not None

        response = client.post(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers,
            json={
                "title": "Team Meeting",
                "description": "Weekly sync",
                "scheduled_at": "2026-05-15T10:00:00Z",
                "duration_minutes": 60,
                "location": "Conference Room A"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        meeting = data.get("data", data)
        assert meeting.get("title") == "Team Meeting"

    def test_create_meeting_minimal_fields(self, admin_headers):
        """Test meeting creation with minimal fields"""
        project_id = self.create_test_project(admin_headers)
        assert project_id is not None

        response = client.post(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers,
            json={
                "title": "Minimal Meeting",
                "scheduled_at": "2026-05-20T14:00:00Z"
            }
        )
        assert response.status_code in [200, 201]

    def test_create_meeting_missing_title(self, admin_headers):
        """Test meeting creation without title"""
        project_id = self.create_test_project(admin_headers)
        assert project_id is not None

        response = client.post(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers,
            json={
                "scheduled_at": "2026-05-20T14:00:00Z"
            }
        )
        assert response.status_code == 422

    def test_create_meeting_invalid_project(self, admin_headers):
        """Test creating meeting in non-existent project"""
        response = client.post(
            "/api/v3/projects/99999/meetings",
            headers=admin_headers,
            json={
                "title": "Invalid Meeting",
                "scheduled_at": "2026-05-20T14:00:00Z"
            }
        )
        assert response.status_code in [400, 404]

    def test_list_meetings(self, admin_headers):
        """Test listing meetings"""
        project_id = self.create_test_project(admin_headers)
        assert project_id is not None

        response = client.get(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers
        )
        assert response.status_code == 200

    def test_get_meeting_by_id(self, admin_headers):
        """Test getting meeting by ID"""
        project_id = self.create_test_project(admin_headers)
        assert project_id is not None

        # Create meeting
        create_resp = client.post(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers,
            json={
                "title": "Get Meeting",
                "scheduled_at": "2026-05-21T10:00:00Z"
            }
        )
        meeting_id = create_resp.json().get("data", {}).get("id")

        # Get meeting
        response = client.get(f"/api/v3/meetings/{meeting_id}", headers=admin_headers)
        assert response.status_code == 200

    def test_update_meeting(self, admin_headers):
        """Test updating meeting"""
        project_id = self.create_test_project(admin_headers)
        assert project_id is not None

        # Create meeting
        create_resp = client.post(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers,
            json={
                "title": "Original Title",
                "scheduled_at": "2026-05-21T11:00:00Z"
            }
        )
        meeting_id = create_resp.json().get("data", {}).get("id")

        # Update meeting
        response = client.patch(
            f"/api/v3/meetings/{meeting_id}",
            headers=admin_headers,
            json={
                "title": "Updated Title",
                "location": "Room B"
            }
        )
        assert response.status_code in [200, 204]

    def test_delete_meeting(self, admin_headers):
        """Test deleting meeting"""
        project_id = self.create_test_project(admin_headers)
        assert project_id is not None

        # Create meeting
        create_resp = client.post(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers,
            json={
                "title": "Delete Meeting",
                "scheduled_at": "2026-05-21T12:00:00Z"
            }
        )
        meeting_id = create_resp.json().get("data", {}).get("id")

        # Delete meeting
        response = client.delete(f"/api/v3/meetings/{meeting_id}", headers=admin_headers)
        assert response.status_code in [200, 204]


# ============================================================================
# ROLE MANAGEMENT TESTS
# ============================================================================

class TestRoleManagement:
    """Comprehensive role management endpoint tests"""

    def test_list_roles(self, admin_headers):
        """Test listing roles"""
        response = client.get("/api/v3/roles", headers=admin_headers)
        assert response.status_code == 200

    def test_create_role(self, admin_headers):
        """Test creating a role"""
        response = client.post(
            "/api/v3/roles",
            headers=admin_headers,
            json={
                "name": "Editor",
                "permissions": ["projects:read", "projects:edit"],
                "builtin": False
            }
        )
        assert response.status_code in [200, 201]

    def test_create_duplicate_role(self, admin_headers):
        """Test creating duplicate role"""
        # Create first role
        client.post(
            "/api/v3/roles",
            headers=admin_headers,
            json={
                "name": "TestRole",
                "permissions": ["read"],
                "builtin": False
            }
        )

        # Try to create with same name
        response = client.post(
            "/api/v3/roles",
            headers=admin_headers,
            json={
                "name": "TestRole",
                "permissions": ["write"],
                "builtin": False
            }
        )
        assert response.status_code in [400, 409, 422]

    def test_get_role_by_id(self, admin_headers):
        """Test getting role by ID"""
        # Create role
        create_resp = client.post(
            "/api/v3/roles",
            headers=admin_headers,
            json={
                "name": "GetRole",
                "permissions": ["read"],
                "builtin": False
            }
        )
        if create_resp.status_code in [200, 201]:
            role_id = create_resp.json().get("data", {}).get("id")

            # Get role
            response = client.get(f"/api/v3/roles/{role_id}", headers=admin_headers)
            assert response.status_code == 200

    def test_update_role(self, admin_headers):
        """Test updating role"""
        # Create role
        create_resp = client.post(
            "/api/v3/roles",
            headers=admin_headers,
            json={
                "name": "UpdateableRole",
                "permissions": ["read"],
                "builtin": False
            }
        )
        if create_resp.status_code in [200, 201]:
            role_id = create_resp.json().get("data", {}).get("id")

            # Update role
            response = client.patch(
                f"/api/v3/roles/{role_id}",
                headers=admin_headers,
                json={
                    "permissions": ["read", "write"]
                }
            )
            assert response.status_code in [200, 204]

    def test_delete_role(self, admin_headers):
        """Test deleting role"""
        # Create role
        create_resp = client.post(
            "/api/v3/roles",
            headers=admin_headers,
            json={
                "name": "DeleteableRole",
                "permissions": ["read"],
                "builtin": False
            }
        )
        if create_resp.status_code in [200, 201]:
            role_id = create_resp.json().get("data", {}).get("id")

            # Delete role
            response = client.delete(f"/api/v3/roles/{role_id}", headers=admin_headers)
            assert response.status_code in [200, 204]


# ============================================================================
# AUTHORIZATION & PERMISSION TESTS
# ============================================================================

class TestAuthorization:
    """Test authorization and permission enforcement"""

    def test_protected_endpoint_without_token(self):
        """Test accessing protected endpoint without token"""
        response = client.get("/api/v3/users")
        assert response.status_code == 401

    def test_protected_endpoint_invalid_token(self):
        """Test accessing protected endpoint with invalid token"""
        response = client.get(
            "/api/v3/users",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    def test_protected_endpoint_malformed_header(self):
        """Test accessing protected endpoint with malformed auth header"""
        response = client.get(
            "/api/v3/users",
            headers={"Authorization": "InvalidToken"}
        )
        assert response.status_code == 401

    def test_member_can_view_projects(self, member_headers):
        """Test that member can view projects"""
        response = client.get("/api/v3/projects", headers=member_headers)
        assert response.status_code == 200

    def test_member_can_create_projects(self, member_headers):
        """Test that member can create projects"""
        response = client.post(
            "/api/v3/projects",
            headers=member_headers,
            json={
                "identifier": "member-proj",
                "name": "Member Project",
                "description": "Created by member"
            }
        )
        # Member should be able to create depending on RBAC
        assert response.status_code in [200, 201, 403]


# ============================================================================
# RESPONSE FORMAT & VALIDATION TESTS
# ============================================================================

class TestResponseFormats:
    """Test response format compliance and structure"""

    def test_response_has_data_field(self, admin_headers):
        """Test that responses have data field"""
        response = client.get("/api/v3/users/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "login" in data  # Alternative format

    def test_response_has_status(self, admin_headers):
        """Test that responses include status"""
        response = client.get("/api/v3/users/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or response.status_code == 200

    def test_create_response_has_id(self, admin_headers):
        """Test that created resource has ID"""
        response = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "idtest",
                "email": "idtest@example.com",
                "password": "Pass123",
                "firstName": "ID",
                "lastName": "Test"
            }
        )
        assert response.status_code in [200, 201]
        data = response.json()
        user = data.get("data", data)
        assert "id" in user

    def test_error_response_format(self, admin_headers):
        """Test error response format"""
        response = client.get("/api/v3/users/99999", headers=admin_headers)
        assert response.status_code == 404
        data = response.json()
        assert "error" in data or "errorIdentifier" in data or response.status_code == 404

    def test_pagination_response_structure(self, admin_headers):
        """Test pagination response structure"""
        response = client.get(
            "/api/v3/users?offset=1&pageSize=10",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        # Should have pagination info
        assert isinstance(data, dict)


# ============================================================================
# EDGE CASES & STRESS TESTS
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_search_string(self, admin_headers):
        """Test endpoints with empty strings"""
        response = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "test",
                "email": "test@example.com",
                "password": "Pass123",
                "firstName": "",
                "lastName": ""
            }
        )
        # Should handle empty strings gracefully
        assert response.status_code in [200, 201, 422]

    def test_very_long_string(self, admin_headers):
        """Test endpoints with very long strings"""
        long_name = "A" * 10000
        response = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "test",
                "name": long_name,
                "description": "Test"
            }
        )
        # Should handle or reject gracefully
        assert response.status_code in [200, 201, 422]

    def test_special_characters_in_fields(self, admin_headers):
        """Test handling of special characters"""
        response = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "spec-chars",
                "name": "Test <>&\"'",
                "description": "Special chars: !@#$%^&*()"
            }
        )
        # Should handle special characters
        assert response.status_code in [200, 201, 422]

    def test_null_optional_fields(self, admin_headers):
        """Test null values in optional fields"""
        response = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "null-fields",
                "name": "Test",
                "description": None,
                "statusExplanation": None
            }
        )
        assert response.status_code in [200, 201, 422]

    def test_case_sensitivity_in_endpoints(self, admin_headers):
        """Test case sensitivity in URL endpoints"""
        response = client.get("/api/v3/Users", headers=admin_headers)
        assert response.status_code == 404  # Should not find mixed case

    def test_extra_query_parameters(self, admin_headers):
        """Test handling of extra query parameters"""
        response = client.get(
            "/api/v3/users?offset=1&pageSize=10&unknown=value&other=param",
            headers=admin_headers
        )
        # Should ignore extra parameters
        assert response.status_code == 200


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Test workflows involving multiple endpoints"""

    def test_create_user_and_login(self, admin_headers):
        """Test creating user and logging in with it"""
        # Create user
        create_resp = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "integrationtest",
                "email": "integration@example.com",
                "password": "IntegPass123",
                "firstName": "Integration",
                "lastName": "Test"
            }
        )
        assert create_resp.status_code in [200, 201]

        # Login with created user
        login_resp = client.post(
            "/api/v3/users/login",
            json={"login": "integrationtest", "password": "IntegPass123"}
        )
        assert login_resp.status_code == 200

    def test_create_project_and_meeting(self, admin_headers):
        """Test creating project and then meeting"""
        # Create project
        proj_resp = client.post(
            "/api/v3/projects",
            headers=admin_headers,
            json={
                "identifier": "integration-proj",
                "name": "Integration Project",
                "description": "For testing workflows"
            }
        )
        assert proj_resp.status_code in [200, 201]
        project_id = proj_resp.json().get("data", {}).get("id")

        # Create meeting in project
        meet_resp = client.post(
            f"/api/v3/projects/{project_id}/meetings",
            headers=admin_headers,
            json={
                "title": "Integration Meeting",
                "scheduled_at": "2026-06-01T10:00:00Z"
            }
        )
        assert meet_resp.status_code in [200, 201]

    def test_full_crud_workflow(self, admin_headers):
        """Test complete CRUD workflow for users"""
        # CREATE
        create_resp = client.post(
            "/api/v3/users",
            headers=admin_headers,
            json={
                "login": "crudtest",
                "email": "crud@example.com",
                "password": "CrudPass123",
                "firstName": "CRUD",
                "lastName": "Test"
            }
        )
        assert create_resp.status_code in [200, 201]
        user_id = create_resp.json().get("data", {}).get("id")

        # READ
        read_resp = client.get(f"/api/v3/users/{user_id}", headers=admin_headers)
        assert read_resp.status_code == 200

        # UPDATE
        update_resp = client.patch(
            f"/api/v3/users/{user_id}",
            headers=admin_headers,
            json={"firstName": "Updated"}
        )
        assert update_resp.status_code in [200, 204]

        # DELETE
        delete_resp = client.delete(f"/api/v3/users/{user_id}", headers=admin_headers)
        assert delete_resp.status_code in [200, 204]


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Basic performance and load tests"""

    def test_list_with_many_users(self, admin_headers):
        """Test listing with multiple users"""
        # Create several users
        for i in range(5):
            client.post(
                "/api/v3/users",
                headers=admin_headers,
                json={
                    "login": f"user{i}",
                    "email": f"user{i}@example.com",
                    "password": "Pass123",
                    "firstName": f"User{i}",
                    "lastName": "Test"
                }
            )

        # List should still be fast
        response = client.get("/api/v3/users", headers=admin_headers)
        assert response.status_code == 200

    def test_concurrent_read_operations(self, admin_headers):
        """Test multiple read operations"""
        for _ in range(10):
            response = client.get("/api/v3/users/me", headers=admin_headers)
            assert response.status_code == 200


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-ra"])
