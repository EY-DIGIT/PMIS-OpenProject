from typing import Optional, Dict
from threading import Lock

from .models.user import User


class InMemoryUserRepository:
    """Simple in-memory repository for users used by the API.

    This is intentionally simple and not thread-safe for production.
    """

    def __init__(self):
        self._by_id: Dict[int, User] = {}
        self._by_login: Dict[str, User] = {}
        self._lock = Lock()
        self._next_id = 1

    def add(self, user: User) -> User:
        with self._lock:
            if not user.id:
                user.id = self._next_id
                self._next_id += 1

            self._by_id[user.id] = user
            if user.login:
                self._by_login[user.login] = user

        return user

    def update(self, user: User) -> User:
        with self._lock:
            self._by_id[user.id] = user
            if user.login:
                self._by_login[user.login] = user
        return user

    def find_by_id(self, user_id: int) -> Optional[User]:
        return self._by_id.get(int(user_id))

    def find_by_login_or_email(self, login_or_email: str) -> Optional[User]:
        # check by login first
        user = self._by_login.get(login_or_email)
        if user:
            return user

        # then scan by email
        for u in self._by_id.values():
            if u.mail == login_or_email:
                return u

        return None

    def delete(self, user_id: int) -> Optional[User]:
        with self._lock:
            user = self._by_id.get(int(user_id))
            if not user:
                return None
            # remove from login index
            if user.login and user.login in self._by_login:
                del self._by_login[user.login]

            del self._by_id[user.id]
            return user


repository = InMemoryUserRepository()
