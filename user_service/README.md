# User Service - Python Implementation

A Python implementation of the OpenProject User Service based on the stable/16 branch.

This implementation faithfully recreates the user management functionality from OpenProject, including:
- User CRUD operations (Create, Read, Update, Delete)
- Authentication and authorization
- Password management
- User preferences
- User registration and invitation
- Session management

## Features

### User Models
- **User**: Main user model with authentication and profile management
- **AnonymousUser**: Represents guest/anonymous users
- **SystemUser**: System-level user accounts
- **DeletedUser**: Soft-deleted user representation
- **PlaceholderUser**: Placeholder user instances
- **UserPassword**: Historical password tracking for reuse prevention
- **UserPreference**: User-specific preferences and settings

### Services
- **UserCreateService**: Create new users with validation
- **UserUpdateService**: Update existing user information
- **UserDeleteService**: Soft-delete users
- **UserSetAttributesService**: Set and validate user attributes
- **UserLoginService**: Handle user authentication and session creation
- **UserLogoutService**: Handle user logout and session cleanup
- **UserChangePasswordService**: Change user passwords with validation
- **UserRegisterService**: Self-registration workflow

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Import the module:
```python
from user_service import (
    User,
    UserStatus,
    UserCreateService,
    UserUpdateService,
    # ... other services
)
```

## Usage Examples

### Creating a User

```python
from user_service import UserCreateService, UserStatus

# Create service instance
create_service = UserCreateService()

# Create user
result = create_service.call({
    'login': 'johndoe',
    'firstname': 'John',
    'lastname': 'Doe',
    'mail': 'john@example.com',
    'status': UserStatus.ACTIVE,
    'password': 'SecurePass123',
    'preferences': {
        'timezone': 'America/New_York',
        'theme': 'dark'
    }
})

if result.is_success():
    user = result.result
    print(f"User created: {user.name()}")
else:
    print(f"Errors: {result.errors}")
```

### Authenticating a User

```python
from user_service import User, UserLoginService

# Authenticate
user = User.try_to_login('johndoe', 'SecurePass123', user_repository)

if user:
    # Create login session
    login_service = UserLoginService(user)
    result = login_service.call(autologin=True)

    if result.is_success():
        session_data = login_service.get_session_data()
        print(f"Logged in: {user.name()}")
```

### Updating a User

```python
from user_service import UserUpdateService

# Update service with existing user
update_service = UserUpdateService(model=user)

result = update_service.call({
    'firstname': 'Jane',
    'language': 'de',
    'preferences': {
        'theme': 'light'
    }
})

if result.is_success():
    updated_user = result.result
    print(f"Updated: {updated_user.name()}")
```

### Changing Password

```python
from user_service import UserChangePasswordService

change_pw_service = UserChangePasswordService(user)

result = change_pw_service.call(
    current_password='SecurePass123',
    new_password='NewSecurePass456!',
    new_password_confirmation='NewSecurePass456!'
)

if result.is_success():
    print("Password changed successfully")
else:
    print(f"Errors: {result.errors}")
```

### Deleting a User (Soft Delete)

```python
from user_service import UserDeleteService

delete_service = UserDeleteService(model=user)
result = delete_service.call()

if result.is_success():
    print(f"User deleted: {result.result.status}")
```

### User Registration

```python
from user_service import UserRegisterService

register_service = UserRegisterService()

result = register_service.call({
    'login': 'newuser',
    'firstname': 'New',
    'lastname': 'User',
    'mail': 'newuser@example.com',
    'password': 'Password123'
})

if result.is_success():
    print("Registration successful - activation email sent")
```

## Running Examples

Run the included examples:

```bash
python -m user_service.example
```

This will demonstrate all major features including:
- User registration
- User creation with preferences
- User updates
- Authentication and login
- Password changes
- Logout
- User deletion
- Invited users
- Validation errors

## Architecture

The implementation follows OpenProject's service-oriented architecture:

### Service Pattern
All operations go through service classes that:
1. Validate input parameters
2. Set attributes on models
3. Validate model state
4. Persist changes
5. Return ServiceResult objects

### ServiceResult
All services return a `ServiceResult` object containing:
- `success`: Boolean indicating success/failure
- `result`: The resulting object (e.g., User)
- `errors`: Dictionary of validation errors
- `message`: Optional message

### Model Validation
Models implement their own validation logic:
- Email format validation
- Password strength requirements
- Login uniqueness
- Required field validation

### Security Features
- Password hashing with bcrypt
- Brute-force protection (account locking)
- Password history tracking
- Session management
- Autologin tokens

## Architecture Decisions

### Based on OpenProject stable/16

This implementation is based on the OpenProject stable/16 branch:
- [User Model](https://github.com/opf/openproject/blob/stable/16/app/models/user.rb)
- [User Services](https://github.com/opf/openproject/tree/stable/16/app/services/users)

### Differences from Ruby Implementation

1. **No Database**: This is a standalone implementation without database integration. In production, you would add:
   - SQLAlchemy or another ORM
   - Database persistence in service methods
   - Query functionality

2. **Simplified Authentication**: The `try_to_login` method requires a repository to be injected for testing. In production:
   - Use a proper database query
   - Implement LDAP/OAuth support
   - Add rate limiting

3. **No Background Jobs**: User deletion is immediate rather than queued. In production:
   - Use Celery or similar for background processing
   - Queue deletion jobs
   - Handle cleanup asynchronously

4. **No Email**: Email sending is stubbed. In production:
   - Integrate with email service
   - Send invitation emails
   - Send password reset emails

## Testing

The implementation includes validation and can be tested with:

```python
import unittest
from user_service import User, UserStatus

class TestUser(unittest.TestCase):
    def test_user_creation(self):
        user = User(
            login='testuser',
            mail='test@example.com',
            status=UserStatus.ACTIVE
        )
        self.assertTrue(user.validate())

    def test_password_hashing(self):
        user = User(login='test')
        user.password = 'secret123'
        self.assertTrue(user.check_password('secret123'))
        self.assertFalse(user.check_password('wrong'))
```

## Production Considerations

To use this in production, you should add:

1. **Database Integration**
   - Add SQLAlchemy models
   - Implement repository pattern
   - Add database migrations

2. **Authentication**
   - Add JWT or session tokens
   - Implement OAuth/LDAP
   - Add 2FA support

3. **Authorization**
   - Implement role-based access control
   - Add permission checking
   - Integrate with authorization framework

4. **Email & Notifications**
   - Add email service integration
   - Implement notification system
   - Add email templates

5. **Background Jobs**
   - Add Celery or similar
   - Queue heavy operations
   - Implement job monitoring

6. **Logging & Monitoring**
   - Add structured logging
   - Implement audit trails
   - Add performance monitoring

7. **Testing**
   - Add comprehensive unit tests
   - Add integration tests
   - Add load tests

## License

This implementation is based on OpenProject which is licensed under GPL-3.0.

## Reference

Original OpenProject repository: https://github.com/opf/openproject/tree/stable/16
