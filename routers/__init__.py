"""FastAPI routers for Project module"""
try:
    from .projects import router as projects_router
    from .members import router as members_router
except ImportError:
    from routers.projects import router as projects_router
    from routers.members import router as members_router

__all__ = [
    'projects_router',
    'members_router',
]
