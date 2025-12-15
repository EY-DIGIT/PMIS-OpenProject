"""
Routes package - URL routing and endpoint definitions.

Routes are thin wrappers that:
1. Apply authorization checks
2. Extract request parameters
3. Call controllers
4. Return responses
"""

from routes.meetings_routes import router as meetings_router
from routes.projects_routes import router as projects_router
from routes.users_routes import router as users_router
from routes.members_routes import router as members_router
from routes.auth_routes import router as auth_router

__all__ = [
    'meetings_router',
    'projects_router',
    'users_router',
    'members_router',
    'auth_router',
]
