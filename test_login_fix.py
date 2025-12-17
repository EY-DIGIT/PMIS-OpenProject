#!/usr/bin/env python3
"""
Test script to verify login fix works correctly.
Tests admin bootstrap and login endpoint.
"""
import time
import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"

def test_login():
    """Test login endpoint with admin credentials."""
    print("\n" + "="*60)
    print("Testing Login Endpoint")
    print("="*60)
    
    # Wait for server to be ready
    max_retries = 5
    for i in range(max_retries):
        try:
            response = requests.post(
                f"{BASE_URL}/api/v3/users/login",
                json={"login": "admin", "password": "admin123"},
                timeout=2
            )
            
            print(f"✓ Server responded")
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("\n✓ LOGIN SUCCESSFUL!")
                print(f"  Token Type: {data.get('data', {}).get('token_type')}")
                token = data.get('data', {}).get('access_token')
                if token:
                    print(f"  Access Token: {token[:40]}...")
                user_data = data.get('data', {}).get('user')
                if user_data:
                    print(f"  User ID: {user_data.get('id')}")
                    print(f"  Login: {user_data.get('login')}")
                    print(f"  Email: {user_data.get('email')}")
                    print(f"  Is Admin: {user_data.get('admin')}")
                return True, token
            else:
                print(f"\n✗ LOGIN FAILED!")
                print(f"Response: {response.text}")
                return False, None
        except requests.exceptions.ConnectionError:
            if i < max_retries - 1:
                print(f"Waiting for server... (attempt {i+1}/{max_retries})")
                time.sleep(1)
            else:
                print("✗ Could not connect to server after retries")
                return False, None
        except Exception as e:
            print(f"✗ Error: {e}")
            return False, None


def test_protected_endpoint(token):
    """Test accessing a protected endpoint with valid token."""
    print("\n" + "="*60)
    print("Testing Protected Endpoint Access")
    print("="*60)
    
    if not token:
        print("✗ No token available to test")
        return False
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v3/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✓ PROTECTED ENDPOINT ACCESS SUCCESSFUL!")
            user = data.get('data')
            if user:
                print(f"  User: {user.get('login')} ({user.get('email')})")
                print(f"  Is Admin: {user.get('admin')}")
            return True
        else:
            print("✗ PROTECTED ENDPOINT ACCESS FAILED!")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_invalid_credentials():
    """Test login with invalid password."""
    print("\n" + "="*60)
    print("Testing Invalid Credentials")
    print("="*60)
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v3/users/login",
            json={"login": "admin", "password": "wrongpassword"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print("✓ INVALID CREDENTIALS CORRECTLY REJECTED!")
            print(f"  Error: {response.json().get('error', 'No error message')}")
            return True
        else:
            print(f"✗ Expected 401, got {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_admin_bootstrap():
    """Test that admin user was created during init_db()."""
    print("\n" + "="*60)
    print("Testing Admin Bootstrap")
    print("="*60)
    
    from app.infrastructure.db.session import SessionLocal
    from app.infrastructure.db.models.user import UserModel
    
    db = SessionLocal()
    try:
        admin = db.query(UserModel).filter(UserModel.login == "admin").first()
        
        if admin:
            print("✓ ADMIN USER CREATED!")
            print(f"  Login: {admin.login}")
            print(f"  Email: {admin.email}")
            print(f"  Is Admin: {admin.admin}")
            print(f"  Status: {admin.status}")
            print(f"  Created At: {admin.created_at}")
            return True
        else:
            print("✗ NO ADMIN USER FOUND!")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print(f"Testing Authentication Fix - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Admin bootstrap
    print("\n[1/4] Admin Bootstrap Test")
    bootstrap_ok = test_admin_bootstrap()
    
    # Test 2: Login endpoint
    print("\n[2/4] Login Endpoint Test")
    login_ok, token = test_login()
    
    # Test 3: Protected endpoint
    print("\n[3/4] Protected Endpoint Test")
    protected_ok = test_protected_endpoint(token) if login_ok else False
    
    # Test 4: Invalid credentials
    print("\n[4/4] Invalid Credentials Test")
    invalid_ok = test_invalid_credentials()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Admin Bootstrap:      {'✓ PASS' if bootstrap_ok else '✗ FAIL'}")
    print(f"Login Endpoint:       {'✓ PASS' if login_ok else '✗ FAIL'}")
    print(f"Protected Endpoint:   {'✓ PASS' if protected_ok else '✗ FAIL'}")
    print(f"Invalid Credentials:  {'✓ PASS' if invalid_ok else '✗ FAIL'}")
    
    overall = bootstrap_ok and login_ok and protected_ok and invalid_ok
    print(f"\nOverall: {'✓ ALL TESTS PASSED' if overall else '✗ SOME TESTS FAILED'}")
    
    exit(0 if overall else 1)
