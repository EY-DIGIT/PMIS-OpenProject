"""
Comprehensive API Testing Script
Tests all endpoints with detailed input/output documentation
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
TEST_RESULTS = []

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def log_test(test_name, endpoint, method, input_data, expected_status, actual_status,
             response_data, passed, notes=""):
    """Log test results"""
    result = {
        "test_name": test_name,
        "endpoint": endpoint,
        "method": method,
        "input": input_data,
        "expected_status": expected_status,
        "actual_status": actual_status,
        "response": response_data,
        "passed": passed,
        "notes": notes,
        "timestamp": datetime.now().isoformat()
    }
    TEST_RESULTS.append(result)

    status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
    print(f"\n{status} - {test_name}")
    print(f"  Endpoint: {method} {endpoint}")
    print(f"  Expected Status: {expected_status}, Got: {actual_status}")
    if notes:
        print(f"  Notes: {notes}")

def test_health_check():
    """Test 1: Health Check Endpoint"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 1: Health Check Endpoint{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    try:
        response = requests.get(f"{BASE_URL}/health")
        passed = response.status_code == 200 and response.json().get("status") == "healthy"

        log_test(
            test_name="Health Check",
            endpoint="/health",
            method="GET",
            input_data=None,
            expected_status=200,
            actual_status=response.status_code,
            response_data=response.json(),
            passed=passed,
            notes="Should return healthy status with version info"
        )
        return passed
    except Exception as e:
        log_test("Health Check", "/health", "GET", None, 200, 0, str(e), False, f"Exception: {e}")
        return False

def test_root_endpoint():
    """Test 2: Root Endpoint"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 2: Root Endpoint{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    try:
        response = requests.get(f"{BASE_URL}/")
        data = response.json()
        passed = (response.status_code == 200 and
                 data.get("_type") == "Root" and
                 "_links" in data)

        log_test(
            test_name="Root Endpoint",
            endpoint="/",
            method="GET",
            input_data=None,
            expected_status=200,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should return HAL+JSON root with links"
        )
        return passed
    except Exception as e:
        log_test("Root Endpoint", "/", "GET", None, 200, 0, str(e), False, f"Exception: {e}")
        return False

def test_login_success():
    """Test 3: Login with Valid Credentials"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 3: Login with Valid Credentials{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    login_data = {
        "login": "admin",
        "password": "admin12345"
    }

    try:
        response = requests.post(f"{BASE_URL}/api/v3/users/login", json=login_data)
        data = response.json()
        passed = (response.status_code == 200 and
                 "access_token" in data and
                 data.get("token_type") == "bearer")

        log_test(
            test_name="Login - Valid Credentials",
            endpoint="/api/v3/users/login",
            method="POST",
            input_data=login_data,
            expected_status=200,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should return JWT token and user data"
        )

        if passed:
            return data["access_token"]
        return None
    except Exception as e:
        log_test("Login - Valid Credentials", "/api/v3/users/login", "POST",
                login_data, 200, 0, str(e), False, f"Exception: {e}")
        return None

def test_login_invalid_credentials():
    """Test 4: Login with Invalid Credentials"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 4: Login with Invalid Credentials{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    login_data = {
        "login": "admin",
        "password": "wrongpassword"
    }

    try:
        response = requests.post(f"{BASE_URL}/api/v3/users/login", json=login_data)
        data = response.json()
        passed = response.status_code == 401

        log_test(
            test_name="Login - Invalid Credentials",
            endpoint="/api/v3/users/login",
            method="POST",
            input_data=login_data,
            expected_status=401,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should return 401 unauthorized error"
        )
        return passed
    except Exception as e:
        log_test("Login - Invalid Credentials", "/api/v3/users/login", "POST",
                login_data, 401, 0, str(e), False, f"Exception: {e}")
        return False

def test_get_current_user(token):
    """Test 5: Get Current User (/me)"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 5: Get Current User (/me){Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(f"{BASE_URL}/api/v3/users/me", headers=headers)
        data = response.json()
        passed = (response.status_code == 200 and
                 data.get("_type") == "User" and
                 data.get("login") == "admin")

        log_test(
            test_name="Get Current User",
            endpoint="/api/v3/users/me",
            method="GET",
            input_data={"headers": "Authorization: Bearer <token>"},
            expected_status=200,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should return authenticated user's data"
        )
        return passed
    except Exception as e:
        log_test("Get Current User", "/api/v3/users/me", "GET",
                {"headers": "Bearer token"}, 200, 0, str(e), False, f"Exception: {e}")
        return False

def test_get_current_user_no_auth():
    """Test 6: Get Current User Without Authentication"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 6: Get Current User Without Auth{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    try:
        response = requests.get(f"{BASE_URL}/api/v3/users/me")
        data = response.json()
        passed = response.status_code == 401

        log_test(
            test_name="Get Current User - No Auth",
            endpoint="/api/v3/users/me",
            method="GET",
            input_data=None,
            expected_status=401,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should return 401 when no token provided"
        )
        return passed
    except Exception as e:
        log_test("Get Current User - No Auth", "/api/v3/users/me", "GET",
                None, 401, 0, str(e), False, f"Exception: {e}")
        return False

def test_create_user(token):
    """Test 7: Create New User"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 7: Create New User{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    headers = {"Authorization": f"Bearer {token}"}
    user_data = {
        "login": "testuser1",
        "email": "testuser1@example.com",
        "password": "testpass123",
        "firstName": "Test",
        "lastName": "User1",
        "admin": False
    }

    try:
        response = requests.post(f"{BASE_URL}/api/v3/users", json=user_data, headers=headers)
        data = response.json()
        passed = (response.status_code == 201 and
                 data.get("login") == "testuser1" and
                 data.get("_type") == "User")

        log_test(
            test_name="Create User",
            endpoint="/api/v3/users",
            method="POST",
            input_data=user_data,
            expected_status=201,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should create user and return 201 with user data"
        )

        if passed:
            return data.get("id")
        return None
    except Exception as e:
        log_test("Create User", "/api/v3/users", "POST",
                user_data, 201, 0, str(e), False, f"Exception: {e}")
        return None

def test_create_user_duplicate(token):
    """Test 8: Create Duplicate User"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 8: Create Duplicate User{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    headers = {"Authorization": f"Bearer {token}"}
    user_data = {
        "login": "admin",
        "email": "duplicate@example.com",
        "password": "testpass123",
        "firstName": "Duplicate",
        "lastName": "User",
        "admin": False
    }

    try:
        response = requests.post(f"{BASE_URL}/api/v3/users", json=user_data, headers=headers)
        data = response.json()
        passed = response.status_code == 409

        log_test(
            test_name="Create Duplicate User",
            endpoint="/api/v3/users",
            method="POST",
            input_data=user_data,
            expected_status=409,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should return 409 conflict for duplicate login"
        )
        return passed
    except Exception as e:
        log_test("Create Duplicate User", "/api/v3/users", "POST",
                user_data, 409, 0, str(e), False, f"Exception: {e}")
        return False

def test_create_user_invalid_data(token):
    """Test 9: Create User with Invalid Data"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 9: Create User with Invalid Data{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    headers = {"Authorization": f"Bearer {token}"}
    user_data = {
        "login": "ab",  # Too short (min 3)
        "email": "invalidemail",  # Invalid email
        "password": "short",  # Too short (min 8)
        "firstName": "Test",
        "lastName": "User"
    }

    try:
        response = requests.post(f"{BASE_URL}/api/v3/users", json=user_data, headers=headers)
        data = response.json()
        passed = response.status_code == 422

        log_test(
            test_name="Create User - Invalid Data",
            endpoint="/api/v3/users",
            method="POST",
            input_data=user_data,
            expected_status=422,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should return 422 validation error"
        )
        return passed
    except Exception as e:
        log_test("Create User - Invalid Data", "/api/v3/users", "POST",
                user_data, 422, 0, str(e), False, f"Exception: {e}")
        return False

def test_get_user_by_id(token, user_id):
    """Test 10: Get User by ID"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 10: Get User by ID{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(f"{BASE_URL}/api/v3/users/{user_id}", headers=headers)
        data = response.json()
        passed = (response.status_code == 200 and
                 data.get("id") == user_id and
                 data.get("_type") == "User")

        log_test(
            test_name="Get User by ID",
            endpoint=f"/api/v3/users/{user_id}",
            method="GET",
            input_data={"user_id": user_id},
            expected_status=200,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should return user data in HAL+JSON format"
        )
        return passed
    except Exception as e:
        log_test("Get User by ID", f"/api/v3/users/{user_id}", "GET",
                {"user_id": user_id}, 200, 0, str(e), False, f"Exception: {e}")
        return False

def test_get_user_not_found(token):
    """Test 11: Get Non-existent User"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 11: Get Non-existent User{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    headers = {"Authorization": f"Bearer {token}"}
    user_id = 99999

    try:
        response = requests.get(f"{BASE_URL}/api/v3/users/{user_id}", headers=headers)
        data = response.json()
        passed = response.status_code == 200 and data.get("_type") == "Error"

        log_test(
            test_name="Get User - Not Found",
            endpoint=f"/api/v3/users/{user_id}",
            method="GET",
            input_data={"user_id": user_id},
            expected_status=200,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should return error response for non-existent user"
        )
        return passed
    except Exception as e:
        log_test("Get User - Not Found", f"/api/v3/users/{user_id}", "GET",
                {"user_id": user_id}, 404, 0, str(e), False, f"Exception: {e}")
        return False

def test_list_users(token):
    """Test 12: List Users with Pagination"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 12: List Users with Pagination{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    headers = {"Authorization": f"Bearer {token}"}
    params = {"offset": 1, "pageSize": 10}

    try:
        response = requests.get(f"{BASE_URL}/api/v3/users", params=params, headers=headers)
        data = response.json()
        passed = (response.status_code == 200 and
                 data.get("_type") == "Collection" and
                 "_embedded" in data and
                 "total" in data)

        log_test(
            test_name="List Users",
            endpoint="/api/v3/users?offset=1&pageSize=10",
            method="GET",
            input_data=params,
            expected_status=200,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should return paginated collection of users"
        )
        return passed
    except Exception as e:
        log_test("List Users", "/api/v3/users", "GET",
                params, 200, 0, str(e), False, f"Exception: {e}")
        return False

def test_update_user(token, user_id):
    """Test 13: Update User"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 13: Update User{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    headers = {"Authorization": f"Bearer {token}"}
    update_data = {
        "firstName": "Updated",
        "lastName": "Name"
    }

    try:
        response = requests.patch(f"{BASE_URL}/api/v3/users/{user_id}",
                                 json=update_data, headers=headers)
        data = response.json()
        passed = (response.status_code == 200 and
                 data.get("firstName") == "Updated" and
                 data.get("lastName") == "Name")

        log_test(
            test_name="Update User",
            endpoint=f"/api/v3/users/{user_id}",
            method="PATCH",
            input_data=update_data,
            expected_status=200,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should update user fields and return updated data"
        )
        return passed
    except Exception as e:
        log_test("Update User", f"/api/v3/users/{user_id}", "PATCH",
                update_data, 200, 0, str(e), False, f"Exception: {e}")
        return False

def test_update_password(token, user_id):
    """Test 14: Update User Password"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 14: Update User Password{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    headers = {"Authorization": f"Bearer {token}"}
    password_data = {
        "password": "newpassword123"
    }

    try:
        response = requests.patch(f"{BASE_URL}/api/v3/users/{user_id}/password",
                                 json=password_data, headers=headers)
        data = response.json()
        passed = (response.status_code == 200 and
                 data.get("_type") == "Success")

        log_test(
            test_name="Update Password",
            endpoint=f"/api/v3/users/{user_id}/password",
            method="PATCH",
            input_data={"password": "newpassword123"},
            expected_status=200,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should update password and return success message"
        )
        return passed
    except Exception as e:
        log_test("Update Password", f"/api/v3/users/{user_id}/password", "PATCH",
                password_data, 200, 0, str(e), False, f"Exception: {e}")
        return False

def test_login_with_new_password():
    """Test 15: Login with Updated Password"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 15: Login with Updated Password{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    login_data = {
        "login": "testuser1",
        "password": "newpassword123"
    }

    try:
        response = requests.post(f"{BASE_URL}/api/v3/users/login", json=login_data)
        data = response.json()
        passed = response.status_code == 200 and "access_token" in data

        log_test(
            test_name="Login - Updated Password",
            endpoint="/api/v3/users/login",
            method="POST",
            input_data=login_data,
            expected_status=200,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should successfully login with new password"
        )
        return passed
    except Exception as e:
        log_test("Login - Updated Password", "/api/v3/users/login", "POST",
                login_data, 200, 0, str(e), False, f"Exception: {e}")
        return False

def test_delete_user(token, user_id):
    """Test 16: Delete User"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 16: Delete User{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.delete(f"{BASE_URL}/api/v3/users/{user_id}", headers=headers)
        data = response.json()
        passed = (response.status_code == 200 and
                 data.get("_type") == "Success")

        log_test(
            test_name="Delete User",
            endpoint=f"/api/v3/users/{user_id}",
            method="DELETE",
            input_data={"user_id": user_id},
            expected_status=200,
            actual_status=response.status_code,
            response_data=data,
            passed=passed,
            notes="Should delete user and return success message"
        )
        return passed
    except Exception as e:
        log_test("Delete User", f"/api/v3/users/{user_id}", "DELETE",
                {"user_id": user_id}, 200, 0, str(e), False, f"Exception: {e}")
        return False

def test_pagination():
    """Test 17: Pagination with Different Page Sizes"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST 17: Pagination Functionality{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    # First, login to get token
    login_data = {"login": "admin", "password": "admin12345"}
    response = requests.post(f"{BASE_URL}/api/v3/users/login", json=login_data)
    token = response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    # Test different page sizes
    params_list = [
        {"offset": 1, "pageSize": 5},
        {"offset": 1, "pageSize": 1},
        {"offset": 2, "pageSize": 1}
    ]

    all_passed = True
    for params in params_list:
        try:
            response = requests.get(f"{BASE_URL}/api/v3/users", params=params, headers=headers)
            data = response.json()
            passed = (response.status_code == 200 and
                     data.get("pageSize") == params["pageSize"] and
                     data.get("offset") == params["offset"])

            log_test(
                test_name=f"Pagination - offset={params['offset']}, pageSize={params['pageSize']}",
                endpoint="/api/v3/users",
                method="GET",
                input_data=params,
                expected_status=200,
                actual_status=response.status_code,
                response_data=data,
                passed=passed,
                notes="Should return correctly paginated results"
            )
            all_passed = all_passed and passed
        except Exception as e:
            log_test(f"Pagination - {params}", "/api/v3/users", "GET",
                    params, 200, 0, str(e), False, f"Exception: {e}")
            all_passed = False

    return all_passed

def generate_report():
    """Generate comprehensive test report"""
    print(f"\n{Colors.YELLOW}{'='*80}{Colors.END}")
    print(f"{Colors.YELLOW}TEST EXECUTION SUMMARY{Colors.END}")
    print(f"{Colors.YELLOW}{'='*80}{Colors.END}")

    total_tests = len(TEST_RESULTS)
    passed_tests = sum(1 for t in TEST_RESULTS if t["passed"])
    failed_tests = total_tests - passed_tests
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

    print(f"\nTotal Tests: {total_tests}")
    print(f"{Colors.GREEN}Passed: {passed_tests}{Colors.END}")
    print(f"{Colors.RED}Failed: {failed_tests}{Colors.END}")
    print(f"Pass Rate: {pass_rate:.1f}%")

    if failed_tests > 0:
        print(f"\n{Colors.RED}Failed Tests:{Colors.END}")
        for result in TEST_RESULTS:
            if not result["passed"]:
                print(f"  - {result['test_name']}: {result['notes']}")

    # Save detailed report
    with open('test_report.json', 'w') as f:
        json.dump(TEST_RESULTS, f, indent=2)

    print(f"\n{Colors.BLUE}Detailed test report saved to: test_report.json{Colors.END}")

    return passed_tests, failed_tests

def main():
    """Run all tests"""
    print(f"\n{Colors.YELLOW}{'='*80}{Colors.END}")
    print(f"{Colors.YELLOW}COMPREHENSIVE API TESTING{Colors.END}")
    print(f"{Colors.YELLOW}Starting at: {datetime.now().isoformat()}{Colors.END}")
    print(f"{Colors.YELLOW}{'='*80}{Colors.END}")

    # Test 1-2: Public endpoints
    test_health_check()
    test_root_endpoint()

    # Test 3-4: Authentication
    token = test_login_success()
    if not token:
        print(f"\n{Colors.RED}CRITICAL: Cannot proceed without valid token{Colors.END}")
        generate_report()
        return

    test_login_invalid_credentials()

    # Test 5-6: Current user endpoint
    test_get_current_user(token)
    test_get_current_user_no_auth()

    # Test 7-9: User creation
    user_id = test_create_user(token)
    test_create_user_duplicate(token)
    test_create_user_invalid_data(token)

    # Test 10-11: Get user
    if user_id:
        test_get_user_by_id(token, user_id)
    test_get_user_not_found(token)

    # Test 12: List users
    test_list_users(token)

    # Test 13-15: Update operations
    if user_id:
        test_update_user(token, user_id)
        test_update_password(token, user_id)
        test_login_with_new_password()

    # Test 16: Delete user
    if user_id:
        test_delete_user(token, user_id)

    # Test 17: Pagination
    test_pagination()

    # Generate final report
    passed, failed = generate_report()

    print(f"\n{Colors.YELLOW}{'='*80}{Colors.END}")
    print(f"{Colors.YELLOW}TESTING COMPLETE{Colors.END}")
    print(f"{Colors.YELLOW}{'='*80}{Colors.END}\n")

    return failed == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
