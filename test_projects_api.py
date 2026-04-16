"""
Test script for Project API endpoints.
Tests all CRUD operations and validates responses.
"""
import sys
sys.path.insert(0, '/c/Users/WC544QK/Downloads/PMIS-OpenProject')

from fastapi.testclient import TestClient
from app.main import app
from app.infrastructure.db.session import SessionLocal, init_db
from sqlalchemy.orm import Session
import time

# Initialize database
init_db()

# Create test client
client = TestClient(app)

def get_unique_identifier(prefix="test"):
    """Generate a unique identifier for testing."""
    timestamp = str(int(time.time()))
    return f"{prefix}-{timestamp}"

def test_create_project():
    """Test creating a project."""
    print("\n=== TEST: Create Project ===")
    
    # First, let's get a token (use admin user)
    login_response = client.post("/api/v3/users/login", json={
        "login": "admin",
        "password": "admin123"
    })
    
    if login_response.status_code != 200:
        print(f"ERROR: Could not login. Status: {login_response.status_code}")
        print(f"Response: {login_response.text}")
        return False
    
    token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create project
    response = client.post(
        "/api/v3/projects",
        json={
            "identifier": get_unique_identifier("api-test"),
            "name": "Test Project",
            "description": "A test project",
            "active": True,
            "public": False
        },
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 201:
        print("✓ Project created successfully")
        # Return the project ID for use in other tests
        project_data = response.json()["data"]
        return True, project_data["id"]
    else:
        print("✗ Failed to create project")
        return False, None


def test_list_projects():
    """Test listing projects."""
    print("\n=== TEST: List Projects ===")
    
    # Get token
    login_response = client.post("/api/v3/users/login", json={
        "login": "admin",
        "password": "admin123"
    })
    token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # List projects
    response = client.get(
        "/api/v3/projects?offset=1&pageSize=20",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    resp_json = response.json()
    print(f"Total projects: {resp_json['data']['total']}")
    
    if response.status_code == 200:
        print("✓ Projects listed successfully")
        return True
    else:
        print("✗ Failed to list projects")
        return False


def test_get_project(project_id):
    """Test getting a project by ID."""
    print("\n=== TEST: Get Project ===")
    
    # Get token
    login_response = client.post("/api/v3/users/login", json={
        "login": "admin",
        "password": "admin123"
    })
    token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get project
    response = client.get(
        f"/api/v3/projects/{project_id}",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Project: {response.json()['data']['name']}")
        print("✓ Project retrieved successfully")
        return True
    else:
        print(f"Response: {response.json()}")
        print("✗ Failed to get project")
        return False


def test_update_project(project_id):
    """Test updating a project."""
    print("\n=== TEST: Update Project ===")
    
    # Get token
    login_response = client.post("/api/v3/users/login", json={
        "login": "admin",
        "password": "admin123"
    })
    token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Update project
    response = client.patch(
        f"/api/v3/projects/{project_id}",
        json={
            "name": "Updated Test Project"
        },
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Updated project: {response.json()['data']['name']}")
        print("✓ Project updated successfully")
        return True
    else:
        print(f"Response: {response.json()}")
        print("✗ Failed to update project")
        return False


def test_delete_project(project_id):
    """Test deleting a project."""
    print("\n=== TEST: Delete Project ===")
    
    # Get token
    login_response = client.post("/api/v3/users/login", json={
        "login": "admin",
        "password": "admin123"
    })
    token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Delete project
    response = client.delete(
        f"/api/v3/projects/{project_id}",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 204:
        print("✓ Project deleted successfully")
        return True
    else:
        print(f"Response: {response.json()}")
        print("✗ Failed to delete project")
        return False


def test_response_format(project_id):
    """Test that responses follow the correct format."""
    print("\n=== TEST: Response Format ===")
    
    # Get token
    login_response = client.post("/api/v3/users/login", json={
        "login": "admin",
        "password": "admin123"
    })
    token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get project
    response = client.get(
        f"/api/v3/projects/{project_id}",
        headers=headers
    )
    
    if response.status_code != 200:
        print("✗ Failed to get project")
        return False
    
    data = response.json()
    
    # Check envelope
    checks = [
        ("has 'data' key", "data" in data),
        ("has 'message' key", "message" in data),
        ("has 'error' key", "error" in data),
        ("has 'status' key", "status" in data),
        ("status is 200", data.get("status") == 200),
    ]
    
    if data.get("data"):
        project = data["data"]
        checks.extend([
            ("has '_type' field", "_type" in project),
            ("has '_links' field", "_links" in project),
            ("_type is 'Project'", project.get("_type") == "Project"),
            ("has 'id' field", "id" in project),
            ("has 'identifier' field", "identifier" in project),
            ("has 'name' field", "name" in project),
            ("has 'active' field", "active" in project),
            ("has 'public' field", "public" in project),
            ("has 'createdAt' field", "createdAt" in project),
            ("has 'updatedAt' field", "updatedAt" in project),
            # New fields
            ("has 'status' field", "status" in project),
            ("has 'owner' field", "owner" in project),
            ("has 'category' field", "category" in project),
            ("has 'startDate' field", "startDate" in project),
            ("has 'endDate' field", "endDate" in project),
        ])
    
    all_passed = True
    for check_name, check_result in checks:
        status = "✓" if check_result else "✗"
        print(f"{status} {check_name}")
        all_passed = all_passed and check_result
    
    return all_passed


if __name__ == "__main__":
    print("=" * 60)
    print("PROJECT API COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    
    # Create a project first and get its ID
    create_result, project_id = test_create_project()
    
    if not create_result or not project_id:
        print("\n❌ Cannot proceed with tests - project creation failed")
        sys.exit(1)
    
    # Run other tests with the created project ID
    results = {
        "Create Project": create_result,
        "List Projects": test_list_projects(),
        "Get Project": test_get_project(project_id),
        "Update Project": test_update_project(project_id),
        "Response Format": test_response_format(project_id),
        "Delete Project": test_delete_project(project_id),
    }
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)
