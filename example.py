"""
Example usage of the User Service.

This demonstrates the key functionality of the user service implementation.
"""

from user_service import (
    User,
    UserStatus,
    UserCreateService,
    UserUpdateService,
    UserDeleteService,
    UserLoginService,
    UserLogoutService,
    UserChangePasswordService,
    UserRegisterService,
    SystemUser
)


def print_result(operation: str, result):
    """Helper to print service results"""
    print(f"\n{'='*60}")
    print(f"Operation: {operation}")
    print(f"Success: {result.is_success()}")
    if result.message:
        print(f"Message: {result.message}")
    if result.errors:
        print(f"Errors: {result.errors}")
    if result.result:
        if isinstance(result.result, User):
            print(f"User: {result.result}")
            print(f"  ID: {result.result.id}")
            print(f"  Login: {result.result.login}")
            print(f"  Name: {result.result.name()}")
            print(f"  Email: {result.result.mail}")
            print(f"  Status: {result.result.status.name}")
    print(f"{'='*60}")


def example_user_registration():
    """Example: Register a new user"""
    print("\n\n*** USER REGISTRATION EXAMPLE ***")

    register_service = UserRegisterService()
    result = register_service.call({
        'login': 'johndoe',
        'firstname': 'John',
        'lastname': 'Doe',
        'mail': 'john.doe@example.com',
        'password': 'SecurePass123'
    })

    print_result("User Registration", result)
    return result.result if result.is_success() else None


def example_user_creation():
    """Example: Create an active user"""
    print("\n\n*** USER CREATION EXAMPLE ***")

    admin = SystemUser()  # Simulating admin user
    create_service = UserCreateService(user=admin)

    result = create_service.call({
        'login': 'janedoe',
        'firstname': 'Jane',
        'lastname': 'Doe',
        'mail': 'jane.doe@example.com',
        'status': UserStatus.ACTIVE,
        'language': 'en',
        'password': 'AnotherPass456',
        'preferences': {
            'timezone': 'America/New_York',
            'theme': 'dark',
            'comments_sorting': 'desc'
        }
    })

    print_result("User Creation", result)
    return result.result if result.is_success() else None


def example_user_update(user: User):
    """Example: Update user information"""
    print("\n\n*** USER UPDATE EXAMPLE ***")

    admin = SystemUser()
    update_service = UserUpdateService(user=admin, model=user)

    result = update_service.call({
        'firstname': 'Jane Marie',
        'language': 'de',
        'preferences': {
            'theme': 'light',
            'timezone': 'Europe/Berlin'
        }
    })

    print_result("User Update", result)
    return result.result if result.is_success() else None


def example_user_login(user: User):
    """Example: User login"""
    print("\n\n*** USER LOGIN EXAMPLE ***")

    # First, we need to authenticate
    authenticated_user = User.try_to_login(
        user.login,
        'AnotherPass456',
        user_repository=MockUserRepository([user])
    )

    if authenticated_user:
        login_service = UserLoginService(
            authenticated_user,
            request_info={'ip': '127.0.0.1', 'user_agent': 'Mozilla/5.0'}
        )
        result = login_service.call(autologin=True)
        print_result("User Login", result)
        print(f"Session Data: {login_service.get_session_data()}")
        return authenticated_user
    else:
        print("Authentication failed!")
        return None


def example_change_password(user: User):
    """Example: Change user password"""
    print("\n\n*** CHANGE PASSWORD EXAMPLE ***")

    change_pw_service = UserChangePasswordService(user)

    # First attempt with wrong current password
    result = change_pw_service.call(
        current_password='WrongPassword',
        new_password='NewSecurePass789!',
        new_password_confirmation='NewSecurePass789!'
    )
    print_result("Change Password (Wrong Current)", result)

    # Second attempt with correct password
    result = change_pw_service.call(
        current_password='AnotherPass456',
        new_password='NewSecurePass789!',
        new_password_confirmation='NewSecurePass789!'
    )
    print_result("Change Password (Correct)", result)

    # Third attempt with weak password
    result = change_pw_service.call(
        current_password='NewSecurePass789!',
        new_password='weak',
        new_password_confirmation='weak'
    )
    print_result("Change Password (Weak Password)", result)


def example_user_logout(user: User):
    """Example: User logout"""
    print("\n\n*** USER LOGOUT EXAMPLE ***")

    session_data = {'user_id': user.id, 'autologin_token': 'abc123'}
    logout_service = UserLogoutService(user, session_data)

    result = logout_service.call()
    print_result("User Logout", result)
    print(f"Session Data After Logout: {session_data}")


def example_user_deletion(user: User):
    """Example: Delete user"""
    print("\n\n*** USER DELETION EXAMPLE ***")

    admin = SystemUser()
    delete_service = UserDeleteService(user=admin, model=user)

    result = delete_service.call()
    print_result("User Deletion", result)


def example_invited_user():
    """Example: Create an invited user"""
    print("\n\n*** INVITED USER EXAMPLE ***")

    admin = SystemUser()
    create_service = UserCreateService(user=admin)

    result = create_service.call({
        'mail': 'invited.user@example.com',
        'status': UserStatus.INVITED,
        'language': 'en'
    })

    print_result("Invited User Creation", result)


def example_validation_errors():
    """Example: Validation errors"""
    print("\n\n*** VALIDATION ERRORS EXAMPLE ***")

    create_service = UserCreateService()

    # Missing required fields
    result = create_service.call({
        'firstname': 'Test'
        # Missing login, mail, etc.
    })
    print_result("Creation with Missing Fields", result)

    # Invalid email
    result = create_service.call({
        'login': 'testuser',
        'firstname': 'Test',
        'lastname': 'User',
        'mail': 'invalid-email',
        'status': UserStatus.ACTIVE
    })
    print_result("Creation with Invalid Email", result)


class MockUserRepository:
    """Mock repository for testing authentication"""
    def __init__(self, users):
        self.users = users

    def find_by_login_or_email(self, login: str):
        for user in self.users:
            if user.login == login or user.mail == login:
                return user
        return None


def main():
    """Run all examples"""
    print("="*60)
    print("USER SERVICE EXAMPLES")
    print("Based on OpenProject User Service")
    print("="*60)

    # Example 1: User Registration
    registered_user = example_user_registration()

    # Example 2: User Creation
    user = example_user_creation()

    if user:
        # Example 3: User Update
        updated_user = example_user_update(user)

        # Example 4: User Login
        if updated_user:
            logged_in_user = example_user_login(updated_user)

            # Example 5: Change Password
            if logged_in_user:
                example_change_password(logged_in_user)

                # Example 6: User Logout
                example_user_logout(logged_in_user)

        # Example 7: User Deletion
        example_user_deletion(user)

    # Example 8: Invited User
    example_invited_user()

    # Example 9: Validation Errors
    example_validation_errors()

    print("\n\n" + "="*60)
    print("ALL EXAMPLES COMPLETED")
    print("="*60)


if __name__ == '__main__':
    main()
