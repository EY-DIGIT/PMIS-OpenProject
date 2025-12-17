#!/usr/bin/env python3
"""
Debug script to test login and check what's failing.
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

# Test login
response = requests.post(
    f"{BASE_URL}/api/v3/users/login",
    json={"login": "admin", "password": "admin123"},
    timeout=5
)

print(f"Status Code: {response.status_code}")
print(f"Response Headers: {dict(response.headers)}")
print(f"Response Body:")
print(json.dumps(response.json(), indent=2))

if response.status_code != 200:
    print("\n❌ LOGIN FAILED!")
else:
    print("\n✅ LOGIN SUCCESSFUL!")
