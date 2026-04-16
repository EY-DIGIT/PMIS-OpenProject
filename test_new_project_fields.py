"""
Test script for new Project API fields: status, owner, category, start_date, end_date.
Tests validation logic and new functionality.
"""
import sys
sys.path.insert(0, '/c/Programming/PMIS_Python')

from fastapi.testclient import TestClient
from app.main import app
from app.infrastructure.db.session import SessionLocal, init_db
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import time
import json

# Initialize database
init_db()

# Create test client
client = TestClient(app)

def login_as_admin():
    """Login as admin and return token."""
    response = client.post("/api/v3/users/login", json={
        "login": "admin",
        "password": "admin123"
    })
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code} - {response.text}")
        return None
    return response.json()["data"]["access_token"]

def get_unique_identifier(prefix="test"):
    """Generate a unique identifier for testing."""
    timestamp = str(int(time.time()))
    return f"{prefix}-{timestamp}"

def test_new_fields_validation():
    """Test validation of new fields."""
    print("\n=== TEST: New Fields Validation ===")

    token = login_as_admin()
    if not token:
        return False

    headers = {"Authorization": f"Bearer {token}"}

    # Test 1: Valid project with all new fields
    print("\n1. Testing valid project with all new fields...")
    future_start = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    future_end = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()

    response = client.post(
        "/api/v3/projects",
        json={
            "identifier": get_unique_identifier("new-fields"),
            "name": "Test New Fields",
            "description": "Testing new fields",
            "status": "new",
            "owner": "admin",  # admin user should exist
            "category": "MSAP",
            "start_date": future_start,
            "end_date": future_end,
            "active": True,
            "public": False
        },
        headers=headers
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        data = response.json()["data"]
        print("✓ Project created with new fields")
        print(f"  - Status: {data.get('status')}")
        print(f"  - Owner: {data.get('owner')}")
        print(f"  - Category: {data.get('category')}")
        print(f"  - Start Date: {data.get('startDate')}")
        print(f"  - End Date: {data.get('endDate')}")
    else:
        print(f"❌ Failed: {response.text}")
        return False

    # Test 2: Invalid status
    print("\n2. Testing invalid status...")
    response = client.post(
        "/api/v3/projects",
        json={
            "identifier": get_unique_identifier("invalid-status"),
            "name": "Test Invalid Status",
            "status": "invalid_status"
        },
        headers=headers
    )

    if response.status_code == 422:
        print("✓ Invalid status correctly rejected")
    else:
        print(f"❌ Invalid status not rejected: {response.status_code} - {response.text}")
        return False

    # Test 3: Invalid category
    print("\n3. Testing invalid category...")
    response = client.post(
        "/api/v3/projects",
        json={
            "identifier": get_unique_identifier("invalid-category"),
            "name": "Test Invalid Category",
            "category": "INVALID"
        },
        headers=headers
    )

    if response.status_code == 422:
        print("✓ Invalid category correctly rejected")
    else:
        print(f"❌ Invalid category not rejected: {response.status_code} - {response.text}")
        return False

    # Test 4: Date in past
    print("\n4. Testing date in past...")
    past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    response = client.post(
        "/api/v3/projects",
        json={
            "identifier": get_unique_identifier("past-date"),
            "name": "Test Past Date",
            "start_date": past_date
        },
        headers=headers
    )

    if response.status_code == 422:
        print("✓ Past date correctly rejected")
    else:
        print(f"❌ Past date not rejected: {response.status_code} - {response.text}")
        return False

    # Test 5: End date before start date
    print("\n5. Testing end date before start date...")
    future_start = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    future_end = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()

    response = client.post(
        "/api/v3/projects",
        json={
            "identifier": get_unique_identifier("wrong-order"),
            "name": "Test Wrong Date Order",
            "start_date": future_start,
            "end_date": future_end
        },
        headers=headers
    )

    if response.status_code == 422:
        print("✓ Wrong date order correctly rejected")
    else:
        print(f"❌ Wrong date order not rejected: {response.status_code} - {response.text}")
        return False

    # Test 6: Invalid owner
    print("\n6. Testing invalid owner...")
    response = client.post(
        "/api/v3/projects",
        json={
            "identifier": get_unique_identifier("invalid-owner"),
            "name": "Test Invalid Owner",
            "owner": "nonexistent_user"
        },
        headers=headers
    )

    if response.status_code == 400:
        print("✓ Invalid owner correctly rejected")
    else:
        print(f"❌ Invalid owner not rejected: {response.status_code} - {response.text}")
        return False

    return True

def test_update_new_fields():
    """Test updating new fields."""
    print("\n=== TEST: Update New Fields ===")

    token = login_as_admin()
    if not token:
        return False

    headers = {"Authorization": f"Bearer {token}"}

    # First create a project
    response = client.post(
        "/api/v3/projects",
        json={
            "identifier": get_unique_identifier("update-fields"),
            "name": "Test Update Fields",
            "status": "new",
            "active": True
        },
        headers=headers
    )

    if response.status_code != 201:
        print(f"❌ Could not create project for update test: {response.status_code}")
        return False

    project_id = response.json()["data"]["id"]
    print(f"Created project ID: {project_id}")

    # Update with new fields
    future_start = (datetime.now(timezone.utc) + timedelta(days=45)).isoformat()
    future_end = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()

    response = client.patch(
        f"/api/v3/projects/{project_id}",
        json={
            "status": "in_progress",
            "owner": "admin",
            "category": "MSIP",
            "start_date": future_start,
            "end_date": future_end
        },
        headers=headers
    )

    print(f"Update Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()["data"]
        print("✓ Project updated with new fields")
        print(f"  - Status: {data.get('status')}")
        print(f"  - Owner: {data.get('owner')}")
        print(f"  - Category: {data.get('category')}")
        print(f"  - Start Date: {data.get('startDate')}")
        print(f"  - End Date: {data.get('endDate')}")
        return True
    else:
        print(f"❌ Update failed: {response.text}")
        return False

def test_backward_compatibility():
    """Test that old requests still work."""
    print("\n=== TEST: Backward Compatibility ===")

    token = login_as_admin()
    if not token:
        return False

    headers = {"Authorization": f"Bearer {token}"}

    # Create project with only old fields
    response = client.post(
        "/api/v3/projects",
        json={
            "identifier": get_unique_identifier("backward-compat"),
            "name": "Test Backward Compatibility",
            "description": "Testing old fields only",
            "active": True,
            "public": False
        },
        headers=headers
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        data = response.json()["data"]
        print("✓ Backward compatibility maintained")
        print(f"  - Status (default): {data.get('status')}")
        print(f"  - Owner (null): {data.get('owner')}")
        print(f"  - Category (null): {data.get('category')}")
        print(f"  - Start Date (null): {data.get('startDate')}")
        print(f"  - End Date (null): {data.get('endDate')}")
        return True
    else:
        print(f"❌ Backward compatibility broken: {response.text}")
        return False

def main():
    """Run all tests."""
    print("================================================================")
    print("PROJECT API NEW FIELDS COMPREHENSIVE TEST SUITE")
    print("=================================================================")

    tests = [
        test_new_fields_validation,
        test_update_new_fields,
        test_backward_compatibility
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)

    print("\n=================================================================")
    print("TEST RESULTS SUMMARY")
    print("=================================================================")

    test_names = [
        "New Fields Validation",
        "Update New Fields",
        "Backward Compatibility"
    ]

    passed = 0
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✓ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")
        if result:
            passed += 1

    print(f"\nTotal: {passed}/{len(tests)} tests passed")

    if passed == len(tests):
        print("🎉 All new field tests passed!")
        return True
    else:
        print("❌ Some tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)