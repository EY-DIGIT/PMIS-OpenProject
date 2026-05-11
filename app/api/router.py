"""Central API router.

Include order matters: FastAPI's Swagger UI groups endpoints by tag in
the order routers are included. The canonical / actively-used surfaces
sit at the top so the FE-facing docs page leads with what's current,
and the legacy / superseded modules (project_members, roles,
permissions, work_packages*, meetings*) are pushed to the bottom.

``master_data_router`` (doc 20) stays where it always was — between the
catalog modules and the comments/attachments tail — to preserve the
existing Swagger layout.
"""
from fastapi import APIRouter

# Active / canonical surface
from .v3.users import router as users_router
from .v3.projects import router as projects_router
from .v3.milestones import milestones_project_router, milestones_router
from .v3.activities import activities_milestone_router, activities_router
from .v3.tasks import tasks_activity_router, tasks_router
from .v3.subtasks import subtasks_task_router, subtasks_router
from .v3.tree import router as tree_router
from .v3.vendors import router as vendors_router
from .v3.resource_types import router as resource_types_router
from .v3.catalogs import catalogs_router
from .v3.master_data import master_data_router
from .v3.comments import router as comments_router
from .v3.attachments import router as attachments_router

# Dashboard (admin-only aggregations across projects / vendors / M / A)
from .v3.dashboard import router as dashboard_router

# Legacy / superseded surfaces (mounted last; bottom of Swagger UI)
from .v3.project_members import (
    projects_router as pm_projects_router,
    memberships_router,
)
from .v3.roles import router as roles_router
from .v3.permissions import permissions_router
from .v3.work_packages import (
    projects_router as wp_projects_router,
    work_packages_router,
)
from .v3.work_package_types import router as work_package_types_router
from .v3.meetings import (
    projects_router as meetings_projects_router,
    meetings_router,
)


# Create API v3 router
api_v3_router = APIRouter(prefix="/api/v3")


# ---------------------------------------------------------------------------
# Active surface — top of Swagger UI
# ---------------------------------------------------------------------------

api_v3_router.include_router(users_router)
api_v3_router.include_router(projects_router)

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

# Catalog modules
api_v3_router.include_router(vendors_router)
api_v3_router.include_router(resource_types_router)
api_v3_router.include_router(catalogs_router)

# Consolidated master-data CRUD (doc 20). Lives under /api/v3/master/*.
# Supersedes the legacy per-catalog endpoints above; those remain
# functional during the FE migration window with a Deprecation header.
api_v3_router.include_router(master_data_router)

# Comments + attachments (polymorphic across M/A/T/S targets)
api_v3_router.include_router(comments_router)
api_v3_router.include_router(attachments_router)

# Dashboard (admin / super_admin only — read-only aggregations)
api_v3_router.include_router(dashboard_router)


# ---------------------------------------------------------------------------
# Legacy / superseded routers — bottom of Swagger UI
# ---------------------------------------------------------------------------
# These are kept registered so existing FE callers keep working during
# the migration window. Their Swagger summaries / responses already
# carry deprecation markers where appropriate.
#
# - project_members:        superseded by doc-41 /api/v3/projects/{id}/role-assignments
# - roles, permissions:     superseded by /api/v3/master/{roles,permissions}
# - work_packages, work_package_types, meetings: less-used admin modules

api_v3_router.include_router(pm_projects_router)
api_v3_router.include_router(memberships_router)
api_v3_router.include_router(roles_router)
api_v3_router.include_router(permissions_router)
api_v3_router.include_router(wp_projects_router)
api_v3_router.include_router(work_packages_router)
api_v3_router.include_router(work_package_types_router)
api_v3_router.include_router(meetings_projects_router)
api_v3_router.include_router(meetings_router)

