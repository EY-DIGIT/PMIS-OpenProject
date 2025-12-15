"""
Repository pattern for database operations.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from db_models import DBUser, DBUserPreference, DBUserPassword, DBAPIToken
from models import User, UserStatus, UserPreference, UserPassword
import bcrypt


class UserRepository:
    """Repository for User database operations"""

    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, user_id: int, exclude_deleted: bool = False) -> Optional[User]:
        """
        Find user by ID.

        Args:
            user_id: The user ID to find
            exclude_deleted: If True, return None for deleted users (default: False)

        Returns:
            User object or None if not found
        """
        query = self.db.query(DBUser).filter(DBUser.id == user_id)

        if exclude_deleted:
            query = query.filter(DBUser.status != UserStatus.DELETED.value)

        db_user = query.first()
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
        search: Optional[str] = None,
        exclude_deleted: bool = True
    ) -> tuple[List[User], int]:
        """
        List users with pagination and filtering.

        Args:
            offset: Starting index for pagination
            limit: Number of users to return
            status: Filter by specific status (optional)
            search: Search term for login, name, or email (optional)
            exclude_deleted: Exclude users with DELETED status (default: True)

        Returns:
            Tuple of (users list, total count)
        """
        query = self.db.query(DBUser)

        # By default, exclude deleted users (matches OpenProject behavior)
        if exclude_deleted:
            query = query.filter(DBUser.status != UserStatus.DELETED.value)

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


# Meeting Repositories


class MeetingRepository:
    """Repository for Meeting database operations"""

    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, meeting_id: int) -> Optional['Meeting']:
        """Find meeting by ID"""
        from db_models import DBMeeting
        from models.meeting import Meeting, MeetingState

        db_meeting = self.db.query(DBMeeting).filter(DBMeeting.id == meeting_id).first()
        return self._to_domain_model(db_meeting) if db_meeting else None

    def find_all(
        self,
        project_id: Optional[int] = None,
        state: Optional[str] = None,
        upcoming: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> List['Meeting']:
        """Find meetings with filters"""
        from db_models import DBMeeting
        from datetime import datetime

        query = self.db.query(DBMeeting)

        if project_id:
            query = query.filter(DBMeeting.project_id == project_id)

        if state:
            from models.meeting import MeetingState
            state_value = MeetingState[state.upper()].value
            query = query.filter(DBMeeting.state == state_value)

        if upcoming:
            query = query.filter(DBMeeting.start_time >= datetime.utcnow())

        query = query.order_by(DBMeeting.start_time.desc())
        query = query.offset(offset).limit(limit)

        return [self._to_domain_model(db_meeting) for db_meeting in query.all()]

    def count(self, project_id: Optional[int] = None) -> int:
        """Count meetings"""
        from db_models import DBMeeting

        query = self.db.query(DBMeeting)
        if project_id:
            query = query.filter(DBMeeting.project_id == project_id)

        return query.count()

    def create(self, meeting: 'Meeting') -> 'Meeting':
        """Create a new meeting"""
        from db_models import DBMeeting

        db_meeting = self._to_db_model(meeting)
        self.db.add(db_meeting)
        self.db.flush()
        self.db.refresh(db_meeting)

        return self._to_domain_model(db_meeting)

    def update(self, meeting: 'Meeting') -> 'Meeting':
        """Update an existing meeting"""
        from db_models import DBMeeting
        from datetime import datetime, timezone

        db_meeting = self.db.query(DBMeeting).filter(DBMeeting.id == meeting.id).first()
        if not db_meeting:
            return None

        # Update fields
        db_meeting.title = meeting.title
        db_meeting.location = meeting.location
        db_meeting.start_time = meeting.start_time
        db_meeting.duration = meeting.duration
        db_meeting.state = meeting.state.value
        db_meeting.lock_version = meeting.lock_version
        db_meeting.notify = meeting.notify
        db_meeting.updated_at = datetime.now(timezone.utc)

        self.db.flush()
        self.db.refresh(db_meeting)

        return self._to_domain_model(db_meeting)

    def delete(self, meeting_id: int) -> bool:
        """Delete a meeting"""
        from db_models import DBMeeting

        db_meeting = self.db.query(DBMeeting).filter(DBMeeting.id == meeting_id).first()
        if not db_meeting:
            return False

        self.db.delete(db_meeting)
        self.db.flush()
        return True

    def _to_domain_model(self, db_meeting: 'DBMeeting') -> 'Meeting':
        """Convert DB model to domain model"""
        if not db_meeting:
            return None

        from models.meeting import Meeting, MeetingState

        return Meeting(
            id=db_meeting.id,
            title=db_meeting.title,
            author_id=db_meeting.author_id,
            project_id=db_meeting.project_id,
            location=db_meeting.location,
            start_time=db_meeting.start_time,
            duration=db_meeting.duration,
            state=MeetingState(db_meeting.state),
            lock_version=db_meeting.lock_version,
            recurring_meeting_id=db_meeting.recurring_meeting_id,
            template=db_meeting.template,
            notify=db_meeting.notify,
            uid=db_meeting.uid,
            created_at=db_meeting.created_at,
            updated_at=db_meeting.updated_at,
        )

    def _to_db_model(self, meeting: 'Meeting') -> 'DBMeeting':
        """Convert domain model to DB model"""
        from db_models import DBMeeting
        from datetime import datetime, timezone
        import uuid

        return DBMeeting(
            id=meeting.id,
            title=meeting.title,
            author_id=meeting.author_id,
            project_id=meeting.project_id,
            location=meeting.location,
            start_time=meeting.start_time,
            duration=meeting.duration,
            state=meeting.state.value,
            lock_version=meeting.lock_version,
            recurring_meeting_id=meeting.recurring_meeting_id,
            template=meeting.template,
            notify=meeting.notify,
            uid=meeting.uid or str(uuid.uuid4()),
            created_at=meeting.created_at or datetime.now(timezone.utc),
            updated_at=meeting.updated_at or datetime.now(timezone.utc),
        )


class MeetingParticipantRepository:
    """Repository for MeetingParticipant database operations"""

    def __init__(self, db: Session):
        self.db = db

    def find_by_meeting(self, meeting_id: int) -> List['MeetingParticipant']:
        """Find all participants for a meeting"""
        from db_models import DBMeetingParticipant

        db_participants = self.db.query(DBMeetingParticipant).filter(
            DBMeetingParticipant.meeting_id == meeting_id
        ).all()

        return [self._to_domain_model(p) for p in db_participants]

    def create(self, participant: 'MeetingParticipant') -> 'MeetingParticipant':
        """Create a new participant"""
        from db_models import DBMeetingParticipant

        db_participant = self._to_db_model(participant)
        self.db.add(db_participant)
        self.db.flush()
        self.db.refresh(db_participant)

        return self._to_domain_model(db_participant)

    def update(self, participant: 'MeetingParticipant') -> 'MeetingParticipant':
        """Update an existing participant"""
        from db_models import DBMeetingParticipant
        from datetime import datetime, timezone

        db_participant = self.db.query(DBMeetingParticipant).filter(
            DBMeetingParticipant.id == participant.id
        ).first()

        if not db_participant:
            return None

        db_participant.invited = participant.invited
        db_participant.attended = participant.attended
        db_participant.participation_status = participant.participation_status.value
        db_participant.updated_at = datetime.now(timezone.utc)

        self.db.flush()
        self.db.refresh(db_participant)

        return self._to_domain_model(db_participant)

    def delete(self, participant_id: int) -> bool:
        """Delete a participant"""
        from db_models import DBMeetingParticipant

        db_participant = self.db.query(DBMeetingParticipant).filter(
            DBMeetingParticipant.id == participant_id
        ).first()

        if not db_participant:
            return False

        self.db.delete(db_participant)
        self.db.flush()
        return True

    def _to_domain_model(self, db_participant: 'DBMeetingParticipant') -> 'MeetingParticipant':
        """Convert DB model to domain model"""
        if not db_participant:
            return None

        from models.meeting_participant import MeetingParticipant, ParticipationStatus

        return MeetingParticipant(
            id=db_participant.id,
            user_id=db_participant.user_id,
            meeting_id=db_participant.meeting_id,
            email=db_participant.email,
            name=db_participant.name,
            invited=db_participant.invited,
            attended=db_participant.attended,
            participation_status=ParticipationStatus(db_participant.participation_status),
            created_at=db_participant.created_at,
            updated_at=db_participant.updated_at,
        )

    def _to_db_model(self, participant: 'MeetingParticipant') -> 'DBMeetingParticipant':
        """Convert domain model to DB model"""
        from db_models import DBMeetingParticipant
        from datetime import datetime, timezone

        return DBMeetingParticipant(
            id=participant.id,
            user_id=participant.user_id,
            meeting_id=participant.meeting_id,
            email=participant.email,
            name=participant.name,
            invited=participant.invited,
            attended=participant.attended,
            participation_status=participant.participation_status.value,
            created_at=participant.created_at or datetime.now(timezone.utc),
            updated_at=participant.updated_at or datetime.now(timezone.utc),
        )
