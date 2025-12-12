"""
User routes - delegates to existing api/users.py for now.
"""

try:
    from ..api.users import router
except ImportError:
    from api.users import router

# Re-export the existing router
# TODO: Refactor to use UsersController
