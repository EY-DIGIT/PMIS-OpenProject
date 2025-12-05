"""
Example usage of the FastAPI User Service.

Demonstrates how to interact with the API using Python requests.
"""

import requests
import json
from typing import Optional

# API base URL
BASE_URL = "http://localhost:8000"
API_V3_URL = f"{BASE_URL}/api/v3"


class OpenProjectAPIClient:
    """Simple API client for OpenProject User Service"""

    def __init__(self, base_url: str = BASE_URL, api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.session = requests.Session()

        if api_key:
            self.session.auth = ("apikey", api_key)

    def create_user(self, user_data: dict) -> dict:
        """Create a new user"""
        response = self.session.post(
            f"{self.base_url}/api/v3/users",
            json=user_data
        )
        response.raise_for_status()
        return response.json()

    def get_user(self, user_id: str) -> dict:
        """Get user by ID (or 'me' for current user)"""
        response = self.session.get(
            f"{self.base_url}/api/v3/users/{user_id}"
        )
        response.raise_for_status()
        return response.json()

    def list_users(self, offset: int = 0, page_size: int = 20) -> dict:
        """List users"""
        response = self.session.get(
            f"{self.base_url}/api/v3/users",
            params={"offset": offset, "pageSize": page_size}
        )
        response.raise_for_status()
        return response.json()

    def update_user(self, user_id: int, user_data: dict) -> dict:
        """Update user"""
        response = self.session.patch(
            f"{self.base_url}/api/v3/users/{user_id}",
            json=user_data
        )
        response.raise_for_status()
        return response.json()

    def delete_user(self, user_id: int) -> bool:
        """Delete user"""
        response = self.session.delete(
            f"{self.base_url}/api/v3/users/{user_id}"
        )
        return response.status_code == 202

    def lock_user(self, user_id: int) -> dict:
        """Lock user account"""
        response = self.session.post(
            f"{self.base_url}/api/v3/users/{user_id}/lock"
        )
        response.raise_for_status()
        return response.json()

    def unlock_user(self, user_id: int) -> dict:
        """Unlock user account"""
        response = self.session.post(
            f"{self.base_url}/api/v3/users/{user_id}/unlock"
        )
        response.raise_for_status()
        return response.json()

    def login(self, username: str, password: str) -> dict:
        """User login"""
        response = requests.post(
            f"{self.base_url}/api/v3/auth/login",
            json={"username": username, "password": password}
        )
        response.raise_for_status()
        return response.json()

    def register(self, registration_data: dict) -> dict:
        """Register new user"""
        response = requests.post(
            f"{self.base_url}/api/v3/auth/register",
            json=registration_data
        )
        response.raise_for_status()
        return response.json()

    def change_password(self, current_password: str, new_password: str) -> dict:
        """Change password"""
        response = self.session.post(
            f"{self.base_url}/api/v3/auth/change-password",
            json={
                "currentPassword": current_password,
                "newPassword": new_password,
                "newPasswordConfirmation": new_password
            }
        )
        response.raise_for_status()
        return response.json()


def print_section(title: str):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_json(data: dict):
    """Pretty print JSON data"""
    print(json.dumps(data, indent=2))


def main():
    """Run examples"""
    print_section("OpenProject User Service API Examples")

    # Initialize client (without API key for public endpoints)
    client = OpenProjectAPIClient()

    # Example 1: Check health
    print_section("1. Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print_json(response.json())
    except Exception as e:
        print(f"Error: {e}")

    # Example 2: Get user schema
    print_section("2. Get User Schema")
    try:
        response = requests.get(f"{API_V3_URL}/users/schema")
        schema = response.json()
        print(f"Schema Type: {schema['_type']}")
        print(f"Available Fields: {', '.join([k for k in schema.keys() if not k.startswith('_')])}")
    except Exception as e:
        print(f"Error: {e}")

    # Example 3: Register a new user
    print_section("3. Register New User")
    try:
        registration_data = {
            "login": "johndoe",
            "firstName": "John",
            "lastName": "Doe",
            "email": "john.doe@example.com",
            "password": "SecurePass123!",
            "language": "en",
            "preferences": {
                "timezone": "America/New_York",
                "theme": "dark"
            }
        }
        user = client.register(registration_data)
        print(f"Created User: {user['login']} (ID: {user['id']})")
        print(f"Status: {user['status']}")
        user_id = user['id']
    except Exception as e:
        print(f"Error: {e}")
        user_id = None

    # Example 4: Login
    print_section("4. User Login")
    try:
        login_response = client.login("johndoe", "SecurePass123!")
        print(f"Login successful!")
        print(f"User: {login_response['user']['name']}")
        print(f"Session ID: {login_response.get('sessionId', 'N/A')}")
    except Exception as e:
        print(f"Error: {e}")

    # Example 5: Create admin user (requires authentication)
    print_section("5. Create Admin User (Requires Auth)")
    print("This example requires API key authentication.")
    print("In production, you would use:")
    print("  client = OpenProjectAPIClient(api_key='YOUR_API_KEY')")
    print("  user = client.create_user({...})")

    # Example 6: Update user
    print_section("6. Update User (Requires Auth)")
    print("Example of updating user preferences:")
    print_json({
        "firstName": "Jane",
        "preferences": {
            "theme": "light",
            "timezone": "Europe/London"
        }
    })

    # Example 7: List users
    print_section("7. List Users (Requires Auth)")
    print("Example response structure:")
    print_json({
        "_type": "Collection",
        "total": 10,
        "count": 10,
        "pageSize": 20,
        "offset": 0,
        "_embedded": {
            "elements": [
                {
                    "_type": "User",
                    "id": 1,
                    "login": "admin",
                    "name": "Admin User",
                    "_links": {
                        "self": {"href": "/api/v3/users/1"}
                    }
                }
            ]
        }
    })

    # Example 8: Lock/Unlock user
    print_section("8. Lock/Unlock User (Requires Admin)")
    print("Lock user:")
    print("  POST /api/v3/users/1/lock")
    print("\nUnlock user:")
    print("  POST /api/v3/users/1/unlock")

    # Example 9: Change password
    print_section("9. Change Password (Requires Auth)")
    print("Example request:")
    print_json({
        "currentPassword": "OldPass123!",
        "newPassword": "NewPass456!",
        "newPasswordConfirmation": "NewPass456!"
    })

    # Example 10: cURL examples
    print_section("10. cURL Examples")
    print("Create user:")
    print("""
curl -X POST http://localhost:8000/api/v3/users \\
  -H "Content-Type: application/json" \\
  -u apikey:YOUR_API_KEY \\
  -d '{
    "login": "testuser",
    "firstName": "Test",
    "lastName": "User",
    "email": "test@example.com",
    "password": "SecurePass123!",
    "admin": false,
    "status": "active"
  }'
""")

    print("\nGet current user:")
    print("""
curl http://localhost:8000/api/v3/users/me \\
  -u apikey:YOUR_API_KEY
""")

    print("\nList users:")
    print("""
curl "http://localhost:8000/api/v3/users?offset=0&pageSize=20" \\
  -u apikey:YOUR_API_KEY
""")

    print_section("API Documentation")
    print("Visit these URLs for more information:")
    print(f"  - Interactive Docs: {BASE_URL}/api/docs")
    print(f"  - ReDoc: {BASE_URL}/api/redoc")
    print(f"  - OpenAPI Spec: {BASE_URL}/api/openapi.json")

    print("\n" + "="*60)
    print("Examples completed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
