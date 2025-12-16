"""
Comprehensive API test script.
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def print_response(title, response):
    """Print formatted response."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response: {response.text}")

def test_api():
    """Run comprehensive API tests."""

    # Test 1: Health check
    print("\n\n=== TEST 1: Health Check ===")
    response = requests.get(f"{BASE_URL}/health")
    print_response("Health Check", response)
    assert response.status_code == 200

    # Test 2: Root endpoint
    print("\n\n=== TEST 2: Root Endpoint ===")
    response = requests.get(f"{BASE_URL}/")
    print_response("Root", response)
    assert response.status_code == 200

    # Test 3: Login as admin
    print("\n\n=== TEST 3: Login as Admin ===")
    login_data = {
        "login": "admin",
        "password": "admin12345"
    }
    response = requests.post(f"{BASE_URL}/api/v3/users/login", json=login_data)
    print_response("Login", response)
    assert response.status_code == 200

    token_data = response.json()
    access_token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Test 4: Get current user (/me endpoint)
    print("\n\n=== TEST 4: Get Current User (/me) ===")
    response = requests.get(f"{BASE_URL}/api/v3/users/me", headers=headers)
    print_response("Get Current User", response)
    assert response.status_code == 200

    # Test 5: Create a new user
    print("\n\n=== TEST 5: Create New User ===")
    new_user_data = {
        "login": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "firstName": "Test",
        "lastName": "User",
        "admin": False
    }
    response = requests.post(f"{BASE_URL}/api/v3/users", json=new_user_data, headers=headers)
    print_response("Create User", response)
    assert response.status_code == 201

    created_user = response.json()
    user_id = created_user["id"]

    # Test 6: Get user by ID
    print("\n\n=== TEST 6: Get User by ID ===")
    response = requests.get(f"{BASE_URL}/api/v3/users/{user_id}", headers=headers)
    print_response("Get User by ID", response)
    assert response.status_code == 200

    # Test 7: List all users
    print("\n\n=== TEST 7: List All Users ===")
    response = requests.get(f"{BASE_URL}/api/v3/users?offset=1&pageSize=10", headers=headers)
    print_response("List Users", response)
    assert response.status_code == 200

    # Test 8: Update user
    print("\n\n=== TEST 8: Update User ===")
    update_data = {
        "firstName": "Updated",
        "lastName": "Name"
    }
    response = requests.patch(f"{BASE_URL}/api/v3/users/{user_id}", json=update_data, headers=headers)
    print_response("Update User", response)
    assert response.status_code == 200

    # Test 9: Update user password
    print("\n\n=== TEST 9: Update User Password ===")
    password_data = {
        "password": "newpassword123"
    }
    response = requests.patch(f"{BASE_URL}/api/v3/users/{user_id}/password", json=password_data, headers=headers)
    print_response("Update Password", response)
    assert response.status_code == 200

    # Test 10: Login with new password
    print("\n\n=== TEST 10: Login with New Password ===")
    login_data = {
        "login": "testuser",
        "password": "newpassword123"
    }
    response = requests.post(f"{BASE_URL}/api/v3/users/login", json=login_data)
    print_response("Login with New Password", response)
    assert response.status_code == 200

    # Test 11: Try to access protected endpoint without auth (should fail)
    print("\n\n=== TEST 11: Access Protected Endpoint Without Auth (Should Fail) ===")
    response = requests.get(f"{BASE_URL}/api/v3/users/{user_id}")
    print_response("Access Without Auth", response)
    assert response.status_code == 401

    # Test 12: Delete user
    print("\n\n=== TEST 12: Delete User ===")
    response = requests.delete(f"{BASE_URL}/api/v3/users/{user_id}", headers=headers)
    print_response("Delete User", response)
    assert response.status_code == 200

    # Test 13: Try to get deleted user (should fail)
    print("\n\n=== TEST 13: Get Deleted User (Should Fail) ===")
    response = requests.get(f"{BASE_URL}/api/v3/users/{user_id}", headers=headers)
    print_response("Get Deleted User", response)
    assert response.status_code == 404

    print("\n\n" + "="*60)
    print("ALL TESTS PASSED!")
    print("="*60)

if __name__ == "__main__":
    try:
        test_api()
    except AssertionError as e:
        print(f"\n\nTEST FAILED: {e}")
    except requests.exceptions.ConnectionError:
        print("\n\nERROR: Cannot connect to server. Make sure the server is running on http://localhost:8000")
    except Exception as e:
        print(f"\n\nERROR: {e}")
