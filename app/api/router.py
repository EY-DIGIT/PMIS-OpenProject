"""
Central API router.
"""
from fastapi import APIRouter
from .v3.users import router as users_router
from .v3.projects import router as projects_router
from .v3.project_members import projects_router as pm_projects_router, memberships_router
from .v3.roles import router as roles_router
from .v3.work_packages import projects_router as wp_projects_router, work_packages_router
from .v3.work_package_types import router as work_package_types_router
from .v3.meetings import projects_router as meetings_projects_router, meetings_router
from .v3.milestones import milestones_project_router, milestones_router
from .v3.activities import activities_milestone_router, activities_router
from .v3.tasks import tasks_activity_router, tasks_router
from .v3.subtasks import subtasks_task_router, subtasks_router
from .v3.tree import router as tree_router

# Create API v3 router
api_v3_router = APIRouter(prefix="/api/v3")

# Include module routers
api_v3_router.include_router(users_router)
api_v3_router.include_router(projects_router)
api_v3_router.include_router(pm_projects_router)
api_v3_router.include_router(memberships_router)
api_v3_router.include_router(roles_router)
api_v3_router.include_router(wp_projects_router)
api_v3_router.include_router(work_packages_router)
api_v3_router.include_router(work_package_types_router)
api_v3_router.include_router(meetings_projects_router)
api_v3_router.include_router(meetings_router)

# M/A/T/S hierarchy
api_v3_router.include_router(milestones_project_router)
api_v3_router.include_router(milestones_router)
api_v3_router.include_router(activities_milestone_router)
api_v3_router.include_router(activities_router)
api_v3_router.include_router(tasks_activity_router)
api_v3_router.include_router(tasks_router)
api_v3_router.include_router(subtasks_task_router)
api_v3_router.include_router(subtasks_router)
api_v3_router.include_router(tree_router)

