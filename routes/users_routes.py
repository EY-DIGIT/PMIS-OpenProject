"""
User routes - delegates to existing api/users.py for now.
"""

from api.users import router

# Re-export the existing router
# TODO: Refactor to use UsersController
