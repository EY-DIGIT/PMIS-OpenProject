"""
API endpoint test for Roles module.
"""
from fastapi.testclient import TestClient
from app.main import app
from app.infrastructure.db.session import Base, engine


def test_roles_api():
    """Test the Roles API endpoints."""
    print("\n" + "="*60)
    print("TESTING ROLES API ENDPOINTS")
    print("="*60)

    # Setup database
    Base.metadata.create_all(bind=engine)

    client = TestClient(app)

    try:
        # Test 1: List roles (should be empty initially, but requires auth)
        print("\n[1/5] Testing GET /api/v3/roles (without auth)...")
        response = client.get("/api/v3/roles")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Authorization check works (status {response.status_code})")

        # Test 2: Create role (without auth)
        print("[2/5] Testing POST /api/v3/roles (without auth)...")
        response = client.post("/api/v3/roles", json={
            "name": "Editor",
            "permissions": ["projects:view"]
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Authorization check works (status {response.status_code})")

        # Test 3: Get specific role (without auth)
        print("[3/5] Testing GET /api/v3/roles/1 (without auth)...")
        response = client.get("/api/v3/roles/1")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Authorization check works (status {response.status_code})")

        # Test 4: Update role (without auth)
        print("[4/5] Testing PATCH /api/v3/roles/1 (without auth)...")
        response = client.patch("/api/v3/roles/1", json={"name": "Reviewer"})
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Authorization check works (status {response.status_code})")

        # Test 5: Delete role (without auth)
        print("[5/5] Testing DELETE /api/v3/roles/1 (without auth)...")
        response = client.delete("/api/v3/roles/1")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Authorization check works (status {response.status_code})")

        print("\n" + "="*60)
        print("✓ ALL API ENDPOINT TESTS PASSED!")
        print("✓ Routes are properly registered")
        print("✓ RBAC authentication is enforced")
        print("="*60)
        return True

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    success = test_roles_api()
    exit(0 if success else 1)
