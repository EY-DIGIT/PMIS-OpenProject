"""Catalogs module — small read-mostly master tables exposed via GET endpoints.

Currently:
- ``GET /api/v3/project_status_transitions`` — the project status state-machine,
  surfaced from the project_status_transitions table.
- ``GET /api/v3/project_owners`` — whitelist of users allowed to be set as a
  project's ``owner``. Backed by the project_owners table.
- ``POST /api/v3/project_owners/create`` — admin-only catalog management.
- ``DELETE /api/v3/project_owners/{user_id}`` — admin-only deactivation
  (soft via ``active=False``; never hard-deletes).
"""
from .routes import router as catalogs_router  # noqa: F401
