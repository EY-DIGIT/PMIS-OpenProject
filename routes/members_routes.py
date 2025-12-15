"""
Member routes - delegates to existing routers/members.py for now.
"""

from routers.members import router

# Re-export the existing router
# TODO: Refactor to use MembersController
