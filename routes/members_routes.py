"""
Member routes - delegates to existing routers/members.py for now.
"""

try:
    from ..routers.members import router
except ImportError:
    from routers.members import router

# Re-export the existing router
# TODO: Refactor to use MembersController
