"""
Simple test script to verify API functionality.
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
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response: {response.text}")

# Test 1: Health check
print("\n\nTest 1: Health Check")
response = requests.get(f"{BASE_URL}/health")
print_response("Health Check", response)

# Test 2: Root endpoint
print("\n\nTest 2: Root Endpoint")
response = requests.get(f"{BASE_URL}/")
print_response("Root", response)

# Test 3: Create admin user (without auth - should fail)
print("\n\nTest 3: Create User Without Auth (Should Fail)")
user_data = {
    "login": "admin",
    "email": "admin@example.com",
    "password": "admin123",
    "firstName": "Admin",
    "lastName": "User",
    "admin": True
}
response = requests.post(f"{BASE_URL}/api/v3/users", json=user_data)
print_response("Create User Without Auth", response)

print("\n\n" + "="*60)
print("MANUAL SETUP REQUIRED:")
print("="*60)
print("Since we need an admin user to create users, you need to:")
print("1. Create an admin user directly in the database")
print("2. Or modify the code to allow first user creation without auth")
print("\nFor now, let's create a test script that adds an admin via database:")
