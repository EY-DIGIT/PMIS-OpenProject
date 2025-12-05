"""
API integration tests for FastAPI User Service.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from user_service.main import app
from user_service.database import Base, get_db
from user_service.models import UserStatus

# Test database
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

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test and drop after"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["_type"] == "Root"


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_user():
    """Test user creation"""
    user_data = {
        "login": "testuser",
        "firstName": "Test",
        "lastName": "User",
        "email": "test@example.com",
        "password": "SecurePass123!",
        "admin": False,
        "status": "active",
        "language": "en"
    }

    response = client.post("/api/v3/users", json=user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["login"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "_links" in data


def test_create_user_validation_error():
    """Test user creation with invalid data"""
    user_data = {
        "login": "test",
        "email": "invalid-email",  # Invalid email
        "password": "short",  # Too short
    }

    response = client.post("/api/v3/users", json=user_data)
    assert response.status_code == 422


def test_get_user_schema():
    """Test getting user schema"""
    response = client.get("/api/v3/users/schema")
    assert response.status_code == 200
    data = response.json()
    assert data["_type"] == "Schema"
    assert "login" in data
    assert "email" in data


def test_register_user():
    """Test user registration"""
    registration_data = {
        "login": "newuser",
        "firstName": "New",
        "lastName": "User",
        "email": "new@example.com",
        "password": "SecurePass123!",
        "language": "en"
    }

    response = client.post("/api/v3/auth/register", json=registration_data)
    assert response.status_code == 201
    data = response.json()
    assert data["login"] == "newuser"
    assert data["status"] == "registered"


def test_api_documentation():
    """Test that OpenAPI docs are accessible"""
    response = client.get("/api/docs")
    assert response.status_code == 200

    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    openapi = response.json()
    assert openapi["info"]["title"] == "OpenProject User Service API"


def test_cors_headers():
    """Test CORS headers are present"""
    response = client.options(
        "/api/v3/users",
        headers={"Origin": "http://localhost:4200"}
    )
    assert "access-control-allow-origin" in response.headers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
