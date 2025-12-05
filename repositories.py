"""
Repository pattern for database operations.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from .db_models import DBUser, DBUserPreference, DBUserPassword, DBAPIToken
from .models import User, UserStatus, UserPreference, UserPassword
import bcrypt


class UserRepository:
    """Repository for User database operations"""

    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, user_id: int) -> Optional[User]:
        """Find user by ID"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        return self._to_domain_model(db_user) if db_user else None

    def find_by_login(self, login: str) -> Optional[User]:
        """Find user by login"""
        db_user = self.db.query(DBUser).filter(DBUser.login == login).first()
        return self._to_domain_model(db_user) if db_user else None

    def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email"""
        db_user = self.db.query(DBUser).filter(DBUser.mail == email).first()
        return self._to_domain_model(db_user) if db_user else None

    def find_by_login_or_email(self, login_or_email: str) -> Optional[User]:
        """Find user by login or email"""
        db_user = self.db.query(DBUser).filter(
            or_(DBUser.login == login_or_email, DBUser.mail == login_or_email)
        ).first()
        return self._to_domain_model(db_user) if db_user else None

    def find_by_api_key(self, api_key: str) -> Optional[User]:
        """Find user by API key"""
        db_user = self.db.query(DBUser).filter(DBUser.api_key == api_key).first()
        return self._to_domain_model(db_user) if db_user else None

    def find_by_api_token(self, token: str) -> Optional[User]:
        """Find user by API token"""
        db_token = self.db.query(DBAPIToken).filter(DBAPIToken.token == token).first()
        if db_token:
            db_user = self.db.query(DBUser).filter(DBUser.id == db_token.user_id).first()
            return self._to_domain_model(db_user) if db_user else None
        return None

    def list_users(
        self,
        offset: int = 0,
        limit: int = 20,
        status: Optional[int] = None,
        search: Optional[str] = None
    ) -> tuple[List[User], int]:
        """
        List users with pagination and filtering.

        Returns:
            Tuple of (users list, total count)
        """
        query = self.db.query(DBUser)

        # Apply filters
        if status is not None:
            query = query.filter(DBUser.status == status)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    DBUser.login.ilike(search_pattern),
                    DBUser.firstname.ilike(search_pattern),
                    DBUser.lastname.ilike(search_pattern),
                    DBUser.mail.ilike(search_pattern)
                )
            )

        # Get total count
        total = query.count()

        # Apply pagination
        db_users = query.offset(offset).limit(limit).all()

        users = [self._to_domain_model(db_user) for db_user in db_users]
        return users, total

    def create(self, user: User) -> User:
        """Create new user"""
        db_user = self._to_db_model(user)
        self.db.add(db_user)

        # Create preference if it exists
        if user.preference:
            db_pref = DBUserPreference(
                user_id=db_user.id,
                timezone=user.preference.timezone,
                hide_mail=user.preference.hide_mail,
                comments_sorting=user.preference.comments_sorting,
                warn_on_leaving_unsaved=user.preference.warn_on_leaving_unsaved,
                theme=user.preference.theme,
                notification_settings=user.preference.notification_settings
            )
            self.db.add(db_pref)

        self.db.commit()
        self.db.refresh(db_user)
        return self._to_domain_model(db_user)

    def update(self, user: User) -> User:
        """Update existing user"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user.id).first()
        if not db_user:
            raise ValueError(f"User with id {user.id} not found")

        # Update fields
        db_user.login = user.login
        db_user.firstname = user.firstname
        db_user.lastname = user.lastname
        db_user.mail = user.mail
        db_user.status = user.status.value
        db_user.admin = user.admin
        db_user.language = user.language
        db_user.password_digest = user._password_digest
        db_user.failed_login_count = user.failed_login_count
        db_user.last_failed_login_on = user.last_failed_login_on
        db_user.force_password_change = user.force_password_change
        db_user.last_login_on = user.last_login_on
        db_user.ldap_auth_source_id = user.ldap_auth_source_id
        db_user.uses_external_auth = user.uses_external_auth

        # Update preference if it exists
        if user.preference:
            db_pref = self.db.query(DBUserPreference).filter(
                DBUserPreference.user_id == user.id
            ).first()

            if db_pref:
                db_pref.timezone = user.preference.timezone
                db_pref.hide_mail = user.preference.hide_mail
                db_pref.comments_sorting = user.preference.comments_sorting
                db_pref.warn_on_leaving_unsaved = user.preference.warn_on_leaving_unsaved
                db_pref.theme = user.preference.theme
                db_pref.notification_settings = user.preference.notification_settings
            else:
                db_pref = DBUserPreference(
                    user_id=user.id,
                    timezone=user.preference.timezone,
                    hide_mail=user.preference.hide_mail,
                    comments_sorting=user.preference.comments_sorting,
                    warn_on_leaving_unsaved=user.preference.warn_on_leaving_unsaved,
                    theme=user.preference.theme,
                    notification_settings=user.preference.notification_settings
                )
                self.db.add(db_pref)

        self.db.commit()
        self.db.refresh(db_user)
        return self._to_domain_model(db_user)

    def delete(self, user_id: int) -> bool:
        """Delete user (soft delete by setting status to DELETED)"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if not db_user:
            return False

        db_user.status = UserStatus.DELETED.value
        self.db.commit()
        return True

    def hard_delete(self, user_id: int) -> bool:
        """Permanently delete user"""
        db_user = self.db.query(DBUser).filter(DBUser.id == user_id).first()
        if not db_user:
            return False

        self.db.delete(db_user)
        self.db.commit()
        return True

    def _to_domain_model(self, db_user: DBUser) -> User:
        """Convert database model to domain model"""
        user = User(
            id=db_user.id,
            login=db_user.login,
            firstname=db_user.firstname,
            lastname=db_user.lastname,
            mail=db_user.mail,
            status=UserStatus(db_user.status),
            admin=db_user.admin,
            language=db_user.language,
            created_at=db_user.created_at,
            updated_at=db_user.updated_at
        )

        user._password_digest = db_user.password_digest
        user.failed_login_count = db_user.failed_login_count
        user.last_failed_login_on = db_user.last_failed_login_on
        user.force_password_change = db_user.force_password_change
        user.last_login_on = db_user.last_login_on
        user.ldap_auth_source_id = db_user.ldap_auth_source_id
        user.uses_external_auth = db_user.uses_external_auth

        # Load preference if it exists
        if db_user.preference:
            user.preference = UserPreference(
                id=db_user.preference.id,
                user_id=db_user.preference.user_id,
                timezone=db_user.preference.timezone,
                hide_mail=db_user.preference.hide_mail,
                comments_sorting=db_user.preference.comments_sorting,
                warn_on_leaving_unsaved=db_user.preference.warn_on_leaving_unsaved,
                theme=db_user.preference.theme,
                notification_settings=db_user.preference.notification_settings
            )

        return user

    def _to_db_model(self, user: User) -> DBUser:
        """Convert domain model to database model"""
        return DBUser(
            id=user.id,
            login=user.login,
            firstname=user.firstname,
            lastname=user.lastname,
            mail=user.mail,
            status=user.status.value,
            admin=user.admin,
            language=user.language,
            password_digest=user._password_digest,
            failed_login_count=user.failed_login_count,
            last_failed_login_on=user.last_failed_login_on,
            force_password_change=user.force_password_change,
            last_login_on=user.last_login_on,
            ldap_auth_source_id=user.ldap_auth_source_id,
            uses_external_auth=user.uses_external_auth,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
