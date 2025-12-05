# Quick Start Guide - User Service

## Installation

```bash
pip install bcrypt
```

## Basic Usage

### 1. Create a User

```python
from user_service import UserCreateService, UserStatus

service = UserCreateService()
result = service.call({
    'login': 'johndoe',
    'firstname': 'John',
    'lastname': 'Doe',
    'mail': 'john@example.com',
    'password': 'SecurePass123',
    'status': UserStatus.ACTIVE,
    'preferences': {
        'timezone': 'America/New_York',
        'theme': 'dark'
    }
})

if result.is_success():
    user = result.result
    print(f"Created: {user.name()}")
else:
    print(f"Errors: {result.errors}")
```

### 2. Update a User

```python
from user_service import UserUpdateService

service = UserUpdateService(model=user)
result = service.call({
    'firstname': 'Jane',
    'preferences': {'theme': 'light'}
})
```

### 3. Authenticate a User

```python
from user_service import User, UserLoginService

# Try to login
user = User.try_to_login('johndoe', 'SecurePass123', user_repository)

if user:
    # Create session
    login_service = UserLoginService(user)
    result = login_service.call(autologin=True)
    session_data = login_service.get_session_data()
```

### 4. Change Password

```python
from user_service import UserChangePasswordService

service = UserChangePasswordService(user)
result = service.call(
    current_password='SecurePass123',
    new_password='NewSecurePass456!',
    new_password_confirmation='NewSecurePass456!'
)
```

### 5. Delete a User

```python
from user_service import UserDeleteService

service = UserDeleteService(model=user)
result = service.call()
```

## Working with ServiceResult

All services return a `ServiceResult` object:

```python
result = service.call(params)

if result.is_success():
    data = result.result
    print(result.message)
else:
    print(result.errors)  # Dictionary of field -> [error messages]
```

## User Status Types

```python
from user_service import UserStatus

UserStatus.ACTIVE       # Active user
UserStatus.REGISTERED   # Registered, pending activation
UserStatus.INVITED      # Invited user
UserStatus.LOCKED       # Account locked
UserStatus.DELETED      # Soft deleted
```

## Run Tests

```bash
python -m user_service.test_user_service -v
```

## Run Examples

```bash
python -m user_service.example
```

## Common Patterns

### Check User Status

```python
user.is_active()
user.is_locked()
user.is_deleted()
```

### Validate User

```python
if user.validate():
    # User is valid
else:
    print(user.errors)
```

### Work with Preferences

```python
# Create user with preferences
result = UserCreateService().call({
    'login': 'test',
    'mail': 'test@example.com',
    'preferences': {
        'timezone': 'Europe/London',
        'theme': 'dark',
        'comments_sorting': 'desc'
    }
})

# Access preferences
user.preference.timezone
user.preference.theme
```

## Error Handling

```python
result = service.call(params)

if result.is_failure():
    for field, errors in result.errors.items():
        print(f"{field}: {', '.join(errors)}")
```
