"""
Central API router.
"""
from fastapi import APIRouter
from .v3.users import router as users_router
from .v3.projects import router as projects_router
from .v3.project_members import projects_router as pm_projects_router, memberships_router

# Create API v3 router
api_v3_router = APIRouter(prefix="/api/v3")

# Include module routers
api_v3_router.include_router(users_router)
api_v3_router.include_router(projects_router)
api_v3_router.include_router(pm_projects_router)
api_v3_router.include_router(memberships_router)
