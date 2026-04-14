from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum
import re
import hashlib
import secrets
from passlib.context import CryptContext

# Password hashing context using argon2
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class UserStatus(Enum):
    """User status enumeration"""
    ACTIVE = 1
    REGISTERED = 2
    INVITED = 3
    LOCKED = 4
    DELETED = 5


class User:
    """
    User model representing a system user with authentication and profile management.

    Based on OpenProject's User model from stable/16 branch.
    """

    # Class configuration
    MAX_LOGIN_LENGTH = 256
    MAX_NAME_LENGTH = 256
    # Python's re doesn't support \p{L}, using a-zA-Z for basic Latin letters
    # For full Unicode support, use the regex module instead of re
    LOGIN_PATTERN = re.compile(r'^[a-zA-Z0-9_\-@.+ ]*$')

    def __init__(
        self,
        id: Optional[int] = None,
        login: Optional[str] = None,
        firstname: Optional[str] = None,
        lastname: Optional[str] = None,
        mail: Optional[str] = None,
        status: UserStatus = UserStatus.REGISTERED,
        admin: bool = False,
        language: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.login = login
        self.firstname = firstname
        self.lastname = lastname
        self.mail = mail
        self.status = status
        self.admin = admin
        self.language = language or 'en'
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)

        # Authentication fields
        self._password_digest: Optional[str] = None
        self.failed_login_count: int = 0
        self.last_failed_login_on: Optional[datetime] = None
        self.force_password_change: bool = False
        self.last_login_on: Optional[datetime] = None

        # Preferences
        self.preference: Optional['UserPreference'] = None

        # Password history
        self.passwords: List['UserPassword'] = []

        # External authentication
        self.ldap_auth_source_id: Optional[int] = None
        self.uses_external_auth: bool = False

        # Tokens
        self.api_tokens: List[str] = []
        self.rss_token: Optional[str] = None

        # Validation errors
        self.errors: Dict[str, List[str]] = {}

    @property
    def password(self) -> None:
        """Password is write-only"""
        return None

    @password.setter
    def password(self, clear_password: Optional[str]):
        """Set password with argon2id hashing"""
        if clear_password:
            self._password_digest = pwd_context.hash(clear_password)

    def check_password(self, clear_password: str) -> bool:
        """
        Verify password against stored hash.

        Args:
            clear_password: Plain text password to verify

        Returns:
            True if password matches, False otherwise
        """
        if not self._password_digest or not clear_password:
            return False

        try:
            return pwd_context.verify(clear_password, self._password_digest)
        except Exception:
            return False

    def random_password(self, length: int = 16) -> str:
        """
        Generate a random password.

        Args:
            length: Length of password to generate

        Returns:
            Random password string
        """
        alphabet = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*'
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        self.password = password
        return password

    def name(self, formatter: str = 'full') -> str:
        """
        Format user display name.

        Args:
            formatter: Format type ('full', 'firstname', 'lastname', 'username')

        Returns:
            Formatted name string
        """
        if formatter == 'full':
            if self.firstname and self.lastname:
                return f"{self.firstname} {self.lastname}"
            return self.login or 'Anonymous'
        elif formatter == 'firstname':
            return self.firstname or self.login or 'Anonymous'
        elif formatter == 'lastname':
            return self.lastname or self.login or 'Anonymous'
        elif formatter == 'username':
            return self.login or 'Anonymous'
        return self.login or 'Anonymous'

    def change_password_allowed(self) -> bool:
        """
        Check if password change is allowed.

        Returns:
            True if password can be changed, False otherwise
        """
        return not self.uses_external_auth and not self.is_builtin()

    def password_expired(self) -> bool:
        """
        Check if password has expired.

        Returns:
            True if password expired, False otherwise
        """
        # Implementation would check password age against policy
        return False

    def is_active(self) -> bool:
        """Check if user is active"""
        return self.status == UserStatus.ACTIVE

    def is_registered(self) -> bool:
        """Check if user is registered but not yet activated"""
        return self.status == UserStatus.REGISTERED

    def is_invited(self) -> bool:
        """Check if user has been invited"""
        return self.status == UserStatus.INVITED

    def is_locked(self) -> bool:
        """Check if user account is locked"""
        return self.status == UserStatus.LOCKED

    def is_deleted(self) -> bool:
        """Check if user is deleted"""
        return self.status == UserStatus.DELETED

    def is_builtin(self) -> bool:
        """Check if user is a built-in system user"""
        return isinstance(self, (AnonymousUser, SystemUser))

    def lock(self):
        """Lock user account"""
        self.status = UserStatus.LOCKED
        self.updated_at = datetime.now(timezone.utc)

    def unlock(self):
        """Unlock user account"""
        if self.status == UserStatus.LOCKED:
            self.status = UserStatus.ACTIVE
            self.failed_login_count = 0
            self.last_failed_login_on = None
            self.updated_at = datetime.now(timezone.utc)

    def activate(self):
        """Activate registered user"""
        if self.status == UserStatus.REGISTERED:
            self.status = UserStatus.ACTIVE
            self.updated_at = datetime.now(timezone.utc)

    def record_failed_login(self):
        """Record a failed login attempt"""
        self.failed_login_count += 1
        self.last_failed_login_on = datetime.now(timezone.utc)

        # Lock account after too many failures (configurable threshold)
        if self.failed_login_count >= 5:
            self.lock()

    def record_successful_login(self):
        """Record a successful login"""
        self.failed_login_count = 0
        self.last_failed_login_on = None
        self.last_login_on = datetime.now(timezone.utc)

    def validate(self) -> bool:
        """
        Validate user attributes.

        Returns:
            True if valid, False otherwise
        """
        self.errors.clear()

        # Validate login
        if not self.login:
            self.errors.setdefault('login', []).append('Login is required')
        elif len(self.login) > self.MAX_LOGIN_LENGTH:
            self.errors.setdefault('login', []).append(
                f'Login must be at most {self.MAX_LOGIN_LENGTH} characters'
            )

        # Validate email
        if not self.is_builtin() and not self.mail:
            self.errors.setdefault('mail', []).append('Email is required')
        elif self.mail and not self._validate_email(self.mail):
            self.errors.setdefault('mail', []).append('Email format is invalid')

        # Validate name fields
        if self.firstname and len(self.firstname) > self.MAX_NAME_LENGTH:
            self.errors.setdefault('firstname', []).append(
                f'First name must be at most {self.MAX_NAME_LENGTH} characters'
            )

        if self.lastname and len(self.lastname) > self.MAX_NAME_LENGTH:
            self.errors.setdefault('lastname', []).append(
                f'Last name must be at most {self.MAX_NAME_LENGTH} characters'
            )

        return len(self.errors) == 0

    @staticmethod
    def _validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @classmethod
    def try_to_login(cls, login: str, password: str, user_repository=None) -> Optional['User']:
        """
        Attempt to authenticate a user.

        Args:
            login: Username or email
            password: Clear text password
            user_repository: Repository to find users (injected for testing)

        Returns:
            User object if authentication successful, None otherwise
        """
        if not login or not password:
            return None

        # Find user by login or email (would use repository/database in production)
        user = user_repository.find_by_login_or_email(login) if user_repository else None

        if not user:
            return None

        # Check if user is locked
        if user.is_locked():
            return None

        # Verify password
        if user.check_password(password):
            user.record_successful_login()
            return user
        else:
            user.record_failed_login()
            return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary representation"""
        return {
            'id': self.id,
            'login': self.login,
            'firstname': self.firstname,
            'lastname': self.lastname,
            'mail': self.mail,
            'status': self.status.name,
            'admin': self.admin,
            'language': self.language,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login_on': self.last_login_on.isoformat() if self.last_login_on else None,
        }

    def __repr__(self) -> str:
        return f"<User(id={self.id}, login='{self.login}', status={self.status.name})>"


class AnonymousUser(User):
    """Represents an anonymous/guest user"""

    def __init__(self):
        super().__init__(
            id=0,
            login='anonymous',
            firstname='Anonymous',
            lastname='User',
            status=UserStatus.ACTIVE
        )

    def is_builtin(self) -> bool:
        return True

    def validate(self) -> bool:
        return True


class SystemUser(User):
    """Represents a system-level user account"""

    def __init__(self):
        super().__init__(
            id=-1,
            login='system',
            firstname='System',
            lastname='User',
            status=UserStatus.ACTIVE
        )

    def is_builtin(self) -> bool:
        return True

    def validate(self) -> bool:
        return True


class DeletedUser(User):
    """Represents a deleted user"""

    def __init__(self, original_id: int):
        super().__init__(
            id=original_id,
            login=f'deleted_user_{original_id}',
            firstname='Deleted',
            lastname='User',
            status=UserStatus.DELETED
        )


class PlaceholderUser(User):
    """Represents a placeholder user"""

    def __init__(self, id: Optional[int] = None, name: str = 'Placeholder'):
        super().__init__(
            id=id,
            login=f'placeholder_{id}' if id else 'placeholder',
            firstname=name,
            lastname='Placeholder',
            status=UserStatus.ACTIVE
        )
