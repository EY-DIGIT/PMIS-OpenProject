"""
Unit tests for the User Service implementation.
"""

import unittest
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from user_service import (
    User,
    UserStatus,
    AnonymousUser,
    SystemUser,
    UserPreference,
    UserCreateService,
    UserUpdateService,
    UserDeleteService,
    UserChangePasswordService,
    UserRegisterService,
    UserLoginService,
    UserLogoutService,
    ServiceResult
)


class TestUser(unittest.TestCase):
    """Test User model"""

    def test_user_creation(self):
        """Test basic user creation"""
        user = User(
            login='testuser',
            firstname='Test',
            lastname='User',
            mail='test@example.com',
            status=UserStatus.ACTIVE
        )
        self.assertEqual(user.login, 'testuser')
        self.assertEqual(user.name(), 'Test User')
        self.assertTrue(user.is_active())

    def test_password_hashing(self):
        """Test password hashing and verification"""
        user = User(login='test')
        user.password = 'SecurePassword123'

        self.assertTrue(user.check_password('SecurePassword123'))
        self.assertFalse(user.check_password('WrongPassword'))

    def test_user_validation(self):
        """Test user validation"""
        # Valid user
        user = User(
            login='valid',
            mail='valid@example.com',
            firstname='Test',
            lastname='User'
        )
        self.assertTrue(user.validate())

        # Invalid user - missing email
        invalid_user = User(
            login='invalid',
            firstname='Test'
        )
        self.assertFalse(invalid_user.validate())
        self.assertIn('mail', invalid_user.errors)

    def test_user_status_checks(self):
        """Test user status helper methods"""
        user = User(status=UserStatus.ACTIVE)
        self.assertTrue(user.is_active())
        self.assertFalse(user.is_locked())

        user.lock()
        self.assertTrue(user.is_locked())

        user.unlock()
        self.assertTrue(user.is_active())

    def test_failed_login_attempts(self):
        """Test failed login tracking"""
        user = User(login='test', status=UserStatus.ACTIVE)

        for i in range(4):
            user.record_failed_login()
            self.assertFalse(user.is_locked())

        # 5th failed attempt should lock
        user.record_failed_login()
        self.assertTrue(user.is_locked())

    def test_builtin_users(self):
        """Test built-in user types"""
        anon = AnonymousUser()
        self.assertTrue(anon.is_builtin())

        system = SystemUser()
        self.assertTrue(system.is_builtin())

        regular = User(login='regular')
        self.assertFalse(regular.is_builtin())


class TestUserServices(unittest.TestCase):
    """Test User services"""

    def test_user_create_service(self):
        """Test user creation service"""
        service = UserCreateService()

        result = service.call({
            'login': 'newuser',
            'firstname': 'New',
            'lastname': 'User',
            'mail': 'new@example.com',
            'status': UserStatus.ACTIVE,
            'password': 'Password123'
        })

        self.assertTrue(result.is_success())
        self.assertIsNotNone(result.result)
        self.assertEqual(result.result.login, 'newuser')

    def test_user_create_validation_error(self):
        """Test user creation with validation errors"""
        service = UserCreateService()

        result = service.call({
            'login': 'baduser',
            'mail': 'invalid-email',  # Invalid email
            'status': UserStatus.ACTIVE
        })

        self.assertTrue(result.is_failure())
        self.assertIn('mail', result.errors)

    def test_user_update_service(self):
        """Test user update service"""
        # Create user first
        user = User(
            login='updatetest',
            firstname='Original',
            mail='original@example.com',
            status=UserStatus.ACTIVE
        )

        # Update user
        service = UserUpdateService(model=user)
        result = service.call({
            'firstname': 'Updated',
            'lastname': 'Name'
        })

        self.assertTrue(result.is_success())
        self.assertEqual(result.result.firstname, 'Updated')
        self.assertEqual(result.result.lastname, 'Name')

    def test_user_delete_service(self):
        """Test user deletion service"""
        user = User(
            login='deletetest',
            mail='delete@example.com',
            status=UserStatus.ACTIVE
        )

        service = UserDeleteService(model=user)
        result = service.call()

        self.assertTrue(result.is_success())
        self.assertTrue(result.result.is_deleted())

    def test_user_register_service(self):
        """Test user registration service"""
        service = UserRegisterService()

        result = service.call({
            'login': 'registered',
            'firstname': 'Registered',
            'lastname': 'User',
            'mail': 'registered@example.com',
            'password': 'Password123'
        })

        self.assertTrue(result.is_success())
        self.assertTrue(result.result.is_registered())

    def test_change_password_service(self):
        """Test password change service"""
        user = User(login='pwtest', mail='pw@example.com', status=UserStatus.ACTIVE)
        user.password = 'OldPassword123'

        service = UserChangePasswordService(user)

        # Test successful password change
        result = service.call(
            current_password='OldPassword123',
            new_password='NewPassword456!',
            new_password_confirmation='NewPassword456!'
        )

        self.assertTrue(result.is_success())
        self.assertTrue(user.check_password('NewPassword456!'))

    def test_change_password_wrong_current(self):
        """Test password change with wrong current password"""
        user = User(login='pwtest', mail='pw@example.com', status=UserStatus.ACTIVE)
        user.password = 'OldPassword123'

        service = UserChangePasswordService(user)

        result = service.call(
            current_password='WrongPassword',
            new_password='NewPassword456!',
            new_password_confirmation='NewPassword456!'
        )

        self.assertTrue(result.is_failure())
        self.assertIn('current_password', result.errors)

    def test_change_password_mismatch(self):
        """Test password change with mismatched confirmation"""
        user = User(login='pwtest', mail='pw@example.com', status=UserStatus.ACTIVE)
        user.password = 'OldPassword123'

        service = UserChangePasswordService(user)

        result = service.call(
            current_password='OldPassword123',
            new_password='NewPassword456!',
            new_password_confirmation='DifferentPassword456!'
        )

        self.assertTrue(result.is_failure())
        self.assertIn('password_confirmation', result.errors)

    def test_change_password_weak(self):
        """Test password change with weak password"""
        user = User(login='pwtest', mail='pw@example.com', status=UserStatus.ACTIVE)
        user.password = 'OldPassword123'

        service = UserChangePasswordService(user)

        result = service.call(
            current_password='OldPassword123',
            new_password='weak',
            new_password_confirmation='weak'
        )

        self.assertTrue(result.is_failure())
        self.assertIn('password', result.errors)

    def test_login_service(self):
        """Test login service"""
        user = User(
            login='logintest',
            mail='login@example.com',
            status=UserStatus.ACTIVE
        )

        service = UserLoginService(user)
        result = service.call(autologin=True)

        self.assertTrue(result.is_success())
        self.assertIn('user_id', service.get_session_data())
        self.assertIn('autologin_token', service.get_session_data())

    def test_logout_service(self):
        """Test logout service"""
        user = User(login='logouttest')
        session_data = {'user_id': 123, 'token': 'abc'}

        service = UserLogoutService(user, session_data)
        result = service.call()

        self.assertTrue(result.is_success())
        self.assertEqual(len(session_data), 0)


class TestServiceResult(unittest.TestCase):
    """Test ServiceResult"""

    def test_success_result(self):
        """Test success result creation"""
        result = ServiceResult.success_result(result={'data': 'test'})

        self.assertTrue(result.is_success())
        self.assertFalse(result.is_failure())
        self.assertEqual(result.result, {'data': 'test'})

    def test_failure_result(self):
        """Test failure result creation"""
        errors = {'field': ['error message']}
        result = ServiceResult.failure_result(errors=errors)

        self.assertTrue(result.is_failure())
        self.assertFalse(result.is_success())
        self.assertEqual(result.errors, errors)

    def test_add_error(self):
        """Test adding errors to result"""
        result = ServiceResult()
        result.add_error('field1', 'error1')
        result.add_error('field1', 'error2')
        result.add_error('field2', 'error3')

        self.assertIn('field1', result.errors)
        self.assertEqual(len(result.errors['field1']), 2)
        self.assertIn('field2', result.errors)


class TestUserPreference(unittest.TestCase):
    """Test UserPreference model"""

    def test_preference_creation(self):
        """Test preference creation"""
        pref = UserPreference(
            user_id=1,
            timezone='America/New_York',
            theme='dark',
            comments_sorting='desc'
        )

        self.assertEqual(pref.timezone, 'America/New_York')
        self.assertEqual(pref.theme, 'dark')
        self.assertEqual(pref.comments_sorting, 'desc')

    def test_preference_to_dict(self):
        """Test preference serialization"""
        pref = UserPreference(user_id=1, timezone='UTC')
        data = pref.to_dict()

        self.assertIn('timezone', data)
        self.assertIn('theme', data)
        self.assertEqual(data['user_id'], 1)


if __name__ == '__main__':
    unittest.main()
