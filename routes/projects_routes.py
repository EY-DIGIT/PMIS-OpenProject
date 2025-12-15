"""
Project routes - delegates to existing routers/projects.py for now.
"""

from routers.projects import router

# Re-export the existing router
# TODO: Refactor to use ProjectsController
