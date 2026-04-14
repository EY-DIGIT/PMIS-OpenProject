#!/usr/bin/env python
"""
Comprehensive API Testing Script
Tests all available endpoints with admin credentials
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "admin123"

# Test results storage
test_results = {
    "timestamp": datetime.now().isoformat(),
    "total_tests": 0,
    "passed": 0,
    "failed": 0,
    "errors": [],
    "endpoints_tested": {}
}

def print_section(title):
    """Print a formatted section title"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def log_test(endpoint, method, status_code, description, success=True, error_msg=None):
    """Log test result"""
    test_results["total_tests"] += 1
    if success:
        test_results["passed"] += 1
        status = "✅ PASS"
    else:
        test_results["failed"] += 1
        status = "❌ FAIL"
    
    key = f"{method} {endpoint}"
    if key not in test_results["endpoints_tested"]:
        test_results["endpoints_tested"][key] = {
            "status": status,
            "status_code": status_code,
            "description": description,
            "error": error_msg
        }
    
    print(f"{status} | {method:6} {endpoint:60} | {status_code} | {description}")
    if error_msg:
        print(f"       └─ Error: {error_msg}")

# Step 1: Login
print_section("1. AUTHENTICATION")
print("Testing login endpoint...\n")

try:
    response = requests.post(
        f"{BASE_URL}/api/v3/users/login",
        json={"login": ADMIN_LOGIN, "password": ADMIN_PASSWORD},
        timeout=10
    )
    
    if response.status_code == 200:
        auth_data = response.json()
        token = auth_data.get("token") or auth_data.get("access_token")
        if not token:
            # Try to extract from response structure
            if "data" in auth_data:
                token = auth_data["data"].get("token") or auth_data["data"].get("access_token")
        
        if token:
            log_test("/api/v3/users/login", "POST", 200, "Admin login successful", success=True)
            headers = {"Authorization": f"Bearer {token}"}
            print(f"✓ Token obtained: {token[:20]}...\n")
        else:
            log_test("/api/v3/users/login", "POST", 200, "Login returned 200 but no token found", success=False, error_msg="No token in response")
            print(f"Response: {json.dumps(auth_data, indent=2)}")
            headers = {}
    else:
        log_test("/api/v3/users/login", "POST", response.status_code, f"Login failed", success=False, error_msg=response.text)
        print(f"Response: {response.text}")
        headers = {}
except Exception as e:
    log_test("/api/v3/users/login", "POST", 0, "Login error", success=False, error_msg=str(e))
    print(f"Exception: {str(e)}")
    headers = {}

if not headers:
    print("\n❌ Cannot proceed without valid authentication token")
    exit(1)

# Step 2: Test User Endpoints
print_section("2. USER ENDPOINTS")

endpoints_user = [
    ("GET", "/api/v3/users/me", "Get current user"),
    ("GET", "/api/v3/users", "List all users"),
]

for method, endpoint, desc in endpoints_user:
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=10)
        log_test(endpoint, method, response.status_code, desc, success=response.status_code in [200, 201, 204])
        if response.status_code not in [200, 201, 204]:
            print(f"       Response: {response.text[:200]}")
    except Exception as e:
        log_test(endpoint, method, 0, desc, success=False, error_msg=str(e))

# Test creating a user
print("\nTesting user creation...\n")
try:
    response = requests.post(
        f"{BASE_URL}/api/v3/users",
        headers=headers,
        json={
            "login": "testuser1",
            "email": "test1@example.com",
            "password": "Test@123456",
            "first_name": "Test",
            "last_name": "User"
        },
        timeout=10
    )
    log_test("/api/v3/users", "POST", response.status_code, "Create user", success=response.status_code in [200, 201])
    if response.status_code in [200, 201]:
        user_data = response.json()
        test_user_id = user_data.get("id") or user_data.get("data", {}).get("id")
        print(f"       User ID: {test_user_id}")
    else:
        print(f"       Response: {response.text[:300]}")
        test_user_id = None
except Exception as e:
    log_test("/api/v3/users", "POST", 0, "Create user", success=False, error_msg=str(e))
    test_user_id = None

# Test getting specific user
if test_user_id:
    try:
        response = requests.get(f"{BASE_URL}/api/v3/users/{test_user_id}", headers=headers, timeout=10)
        log_test(f"/api/v3/users/{test_user_id}", "GET", response.status_code, "Get user by ID", success=response.status_code in [200, 201])
    except Exception as e:
        log_test(f"/api/v3/users/{test_user_id}", "GET", 0, "Get user by ID", success=False, error_msg=str(e))

# Step 3: Test Project Endpoints
print_section("3. PROJECT ENDPOINTS")

try:
    response = requests.post(
        f"{BASE_URL}/api/v3/projects",
        headers=headers,
        json={
            "identifier": f"test-proj-{datetime.now().timestamp()}",
            "name": "Test Project",
            "description": "Test project for API testing"
        },
        timeout=10
    )
    log_test("/api/v3/projects", "POST", response.status_code, "Create project", success=response.status_code in [200, 201])
    if response.status_code in [200, 201]:
        proj_data = response.json()
        test_project_id = proj_data.get("id") or proj_data.get("data", {}).get("id")
        print(f"       Project ID: {test_project_id}")
    else:
        print(f"       Response: {response.text[:300]}")
        test_project_id = None
except Exception as e:
    log_test("/api/v3/projects", "POST", 0, "Create project", success=False, error_msg=str(e))
    test_project_id = None

# List projects
try:
    response = requests.get(f"{BASE_URL}/api/v3/projects", headers=headers, timeout=10)
    log_test("/api/v3/projects", "GET", response.status_code, "List projects", success=response.status_code in [200, 201])
except Exception as e:
    log_test("/api/v3/projects", "GET", 0, "List projects", success=False, error_msg=str(e))

# Get specific project
if test_project_id:
    try:
        response = requests.get(f"{BASE_URL}/api/v3/projects/{test_project_id}", headers=headers, timeout=10)
        log_test(f"/api/v3/projects/{test_project_id}", "GET", response.status_code, "Get project by ID", success=response.status_code in [200, 201])
    except Exception as e:
        log_test(f"/api/v3/projects/{test_project_id}", "GET", 0, "Get project by ID", success=False, error_msg=str(e))

# Step 4: Test Role Endpoints
print_section("4. ROLE ENDPOINTS")

try:
    response = requests.get(f"{BASE_URL}/api/v3/roles", headers=headers, timeout=10)
    log_test("/api/v3/roles", "GET", response.status_code, "List roles", success=response.status_code in [200, 201])
    if response.status_code in [200, 201]:
        roles_data = response.json()
        roles_list = roles_data.get("_embedded", {}).get("elements", []) or roles_data.get("data", [])
        if roles_list:
            test_role_id = roles_list[0].get("id")
            print(f"       Found {len(roles_list)} roles, first ID: {test_role_id}")
        else:
            test_role_id = None
    else:
        test_role_id = None
        print(f"       Response: {response.text[:300]}")
except Exception as e:
    log_test("/api/v3/roles", "GET", 0, "List roles", success=False, error_msg=str(e))
    test_role_id = None

# Get specific role
if test_role_id:
    try:
        response = requests.get(f"{BASE_URL}/api/v3/roles/{test_role_id}", headers=headers, timeout=10)
        log_test(f"/api/v3/roles/{test_role_id}", "GET", response.status_code, "Get role by ID", success=response.status_code in [200, 201])
    except Exception as e:
        log_test(f"/api/v3/roles/{test_role_id}", "GET", 0, "Get role by ID", success=False, error_msg=str(e))

# Step 5: Test Work Package Type Endpoints
print_section("5. WORK PACKAGE TYPE ENDPOINTS")

try:
    response = requests.get(f"{BASE_URL}/api/v3/work_package_types", headers=headers, timeout=10)
    log_test("/api/v3/work_package_types", "GET", response.status_code, "List work package types", success=response.status_code in [200, 201])
    if response.status_code in [200, 201]:
        wp_types = response.json()
        types_list = wp_types.get("_embedded", {}).get("elements", []) or wp_types.get("data", [])
        if types_list:
            test_type_id = types_list[0].get("id")
            print(f"       Found {len(types_list)} types, first ID: {test_type_id}")
        else:
            test_type_id = None
    else:
        test_type_id = None
except Exception as e:
    log_test("/api/v3/work_package_types", "GET", 0, "List work package types", success=False, error_msg=str(e))
    test_type_id = None

# Get specific work package type
if test_type_id:
    try:
        response = requests.get(f"{BASE_URL}/api/v3/work_package_types/{test_type_id}", headers=headers, timeout=10)
        log_test(f"/api/v3/work_package_types/{test_type_id}", "GET", response.status_code, "Get work package type", success=response.status_code in [200, 201])
    except Exception as e:
        log_test(f"/api/v3/work_package_types/{test_type_id}", "GET", 0, "Get work package type", success=False, error_msg=str(e))

# Step 6: Test Work Package Endpoints
print_section("6. WORK PACKAGE ENDPOINTS")

if test_project_id:
    # Create work package
    try:
        response = requests.post(
            f"{BASE_URL}/api/v3/projects/{test_project_id}/work_packages",
            headers=headers,
            json={
                "subject": "Test Work Package",
                "description": "Test work package for API testing",
                "type": test_type_id or "Task"
            },
            timeout=10
        )
        log_test(f"/api/v3/projects/{test_project_id}/work_packages", "POST", response.status_code, "Create work package", success=response.status_code in [200, 201])
        if response.status_code in [200, 201]:
            wp_data = response.json()
            test_wp_id = wp_data.get("id") or wp_data.get("data", {}).get("id")
            print(f"       Work Package ID: {test_wp_id}")
        else:
            print(f"       Response: {response.text[:300]}")
            test_wp_id = None
    except Exception as e:
        log_test(f"/api/v3/projects/{test_project_id}/work_packages", "POST", 0, "Create work package", success=False, error_msg=str(e))
        test_wp_id = None

    # List work packages
    try:
        response = requests.get(f"{BASE_URL}/api/v3/projects/{test_project_id}/work_packages", headers=headers, timeout=10)
        log_test(f"/api/v3/projects/{test_project_id}/work_packages", "GET", response.status_code, "List work packages", success=response.status_code in [200, 201])
    except Exception as e:
        log_test(f"/api/v3/projects/{test_project_id}/work_packages", "GET", 0, "List work packages", success=False, error_msg=str(e))

# Get specific work package
if test_wp_id:
    try:
        response = requests.get(f"{BASE_URL}/api/v3/work_packages/{test_wp_id}", headers=headers, timeout=10)
        log_test(f"/api/v3/work_packages/{test_wp_id}", "GET", response.status_code, "Get work package", success=response.status_code in [200, 201])
    except Exception as e:
        log_test(f"/api/v3/work_packages/{test_wp_id}", "GET", 0, "Get work package", success=False, error_msg=str(e))

# Step 7: Test Meeting Endpoints
print_section("7. MEETING ENDPOINTS")

if test_project_id:
    # Create meeting
    try:
        response = requests.post(
            f"{BASE_URL}/api/v3/projects/{test_project_id}/meetings",
            headers=headers,
            json={
                "title": "Test Meeting",
                "description": "Test meeting for API testing",
                "scheduled_at": "2026-04-15T10:00:00Z",
                "duration_minutes": 60,
                "location": "Conference Room"
            },
            timeout=10
        )
        log_test(f"/api/v3/projects/{test_project_id}/meetings", "POST", response.status_code, "Create meeting", success=response.status_code in [200, 201])
        if response.status_code in [200, 201]:
            mtg_data = response.json()
            test_meeting_id = mtg_data.get("id") or mtg_data.get("data", {}).get("id")
            print(f"       Meeting ID: {test_meeting_id}")
        else:
            print(f"       Response: {response.text[:300]}")
            test_meeting_id = None
    except Exception as e:
        log_test(f"/api/v3/projects/{test_project_id}/meetings", "POST", 0, "Create meeting", success=False, error_msg=str(e))
        test_meeting_id = None

    # List meetings
    try:
        response = requests.get(f"{BASE_URL}/api/v3/projects/{test_project_id}/meetings", headers=headers, timeout=10)
        log_test(f"/api/v3/projects/{test_project_id}/meetings", "GET", response.status_code, "List meetings", success=response.status_code in [200, 201])
    except Exception as e:
        log_test(f"/api/v3/projects/{test_project_id}/meetings", "GET", 0, "List meetings", success=False, error_msg=str(e))

# Get specific meeting
if test_meeting_id:
    try:
        response = requests.get(f"{BASE_URL}/api/v3/meetings/meetings/{test_meeting_id}", headers=headers, timeout=10)
        log_test(f"/api/v3/meetings/meetings/{test_meeting_id}", "GET", response.status_code, "Get meeting", success=response.status_code in [200, 201])
    except Exception as e:
        log_test(f"/api/v3/meetings/meetings/{test_meeting_id}", "GET", 0, "Get meeting", success=False, error_msg=str(e))

# Step 8: Test Membership Endpoints
print_section("8. MEMBERSHIP ENDPOINTS")

if test_project_id and test_user_id:
    # Add member to project
    try:
        response = requests.post(
            f"{BASE_URL}/api/v3/memberships",
            headers=headers,
            json={
                "user": {"id": test_user_id},
                "project": {"id": test_project_id},
                "roles": [{"id": test_role_id or 1}]
            },
            timeout=10
        )
        log_test("/api/v3/memberships", "POST", response.status_code, "Add member to project", success=response.status_code in [200, 201])
        if response.status_code in [200, 201]:
            mem_data = response.json()
            test_member_id = mem_data.get("id") or mem_data.get("data", {}).get("id")
            print(f"       Membership ID: {test_member_id}")
        else:
            print(f"       Response: {response.text[:300]}")
            test_member_id = None
    except Exception as e:
        log_test("/api/v3/memberships", "POST", 0, "Add member to project", success=False, error_msg=str(e))
        test_member_id = None

# List memberships
try:
    response = requests.get(f"{BASE_URL}/api/v3/memberships", headers=headers, timeout=10)
    log_test("/api/v3/memberships", "GET", response.status_code, "List memberships", success=response.status_code in [200, 201])
except Exception as e:
    log_test("/api/v3/memberships", "GET", 0, "List memberships", success=False, error_msg=str(e))

# Step 9: Test Token Introspection
print_section("9. TOKEN INTROSPECTION")

try:
    response = requests.post(
        f"{BASE_URL}/api/v3/users/introspect",
        json={"token": token},
        timeout=10
    )
    log_test("/api/v3/users/introspect", "POST", response.status_code, "Introspect token", success=response.status_code in [200, 201])
except Exception as e:
    log_test("/api/v3/users/introspect", "POST", 0, "Introspect token", success=False, error_msg=str(e))

# Final Summary
print_section("TEST SUMMARY")
print(f"Total Tests:  {test_results['total_tests']}")
print(f"Passed:       {test_results['passed']} ✅")
print(f"Failed:       {test_results['failed']} ❌")
print(f"Success Rate: {(test_results['passed']/test_results['total_tests']*100):.1f}%")

# Save results to file
results_file = "test_results.json"
with open(results_file, "w") as f:
    json.dump(test_results, f, indent=2)
print(f"\nDetailed results saved to: {results_file}")
