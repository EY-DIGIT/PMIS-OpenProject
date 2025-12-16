"""
Central API router.
"""
from fastapi import APIRouter
from .v3.users import router as users_router

# Create API v3 router
api_v3_router = APIRouter(prefix="/api/v3")

# Include module routers
api_v3_router.include_router(users_router)
