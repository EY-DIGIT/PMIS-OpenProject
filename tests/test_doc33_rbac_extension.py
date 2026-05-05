"""Doc 33 (change 2) — RBAC extension tests.

Two surfaces this commit added:

1. ``GET /api/v3/master/permissions/by-module`` — module-grouped view
   of the permission catalog so the FE can render a permission picker
   tree without parsing codes client-side.

2. RBAC artifact cleanup — the ``Role`` enum, ``ROLE_PERMISSIONS``
   dict, and the helpers ``has_permission`` / ``get_role_permissions``
   were deleted from ``app/core/rbac.py``. The ``Permission`` enum
   stays as a transitional bridge.

Pre-existing functionality this exercises (already shipped in doc 21B):
- ``POST /api/v3/master/permissions/create`` accepts a runtime
  permission code; user-defined codes appear alongside built-ins in
  every catalog view.
"""
import pytest


# ===========================================================================
# Module-grouped permissions endpoint
# ===========================================================================

class TestPermissionsByModule:
    def test_response_shape(self, client, admin_user, admin_headers):
        r = client.get(
            "/api/v3/master/permissions/by-module",
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["_type"] == "PermissionsByModule"
        assert "moduleCount" in data
        assert "totalPermissions" in data
        modules = data["_embedded"]["modules"]
        assert isinstance(modules, list)
        assert len(modules) > 0
        # Every entry has the expected shape.
        for m in modules:
            assert m["_type"] == "PermissionModule"
            assert isinstance(m["module"], str)
            assert isinstance(m["count"], int)
            assert isinstance(m["permissions"], list)
            assert m["count"] == len(m["permissions"])

    def test_built_in_modules_present(self, client, admin_user, admin_headers):
        r = client.get(
            "/api/v3/master/permissions/by-module",
            headers=admin_headers,
        )
        modules = {m["module"] for m in r.json()["data"]["_embedded"]["modules"]}
        for must_have in (
            "users", "projects", "milestones", "activities", "tasks",
            "subtasks", "comments", "attachments", "rbac", "permissions",
            "roles", "master_data",
        ):
            assert must_have in modules, f"module {must_have} missing"

    def test_permissions_within_module_sorted_by_code(self, client, admin_user, admin_headers):
        r = client.get(
            "/api/v3/master/permissions/by-module",
            headers=admin_headers,
        )
        for m in r.json()["data"]["_embedded"]["modules"]:
            codes = [p["code"] for p in m["permissions"]]
            assert codes == sorted(codes), (
                f"module {m['module']} permissions not sorted: {codes}"
            )

    def test_modules_sorted_alphabetically(self, client, admin_user, admin_headers):
        r = client.get(
            "/api/v3/master/permissions/by-module",
            headers=admin_headers,
        )
        modules = [m["module"] for m in r.json()["data"]["_embedded"]["modules"]]
        assert modules == sorted(modules)

    def test_runtime_added_module_appears(self, client, admin_user, admin_headers):
        # Add a runtime permission with a brand-new module prefix.
        create = client.post(
            "/api/v3/master/permissions/create",
            json={
                "code": "custom_module:my_action",
                "name": "Custom test perm",
                "description": "Doc 33 change 2 — runtime registration test.",
            },
            headers=admin_headers,
        )
        assert create.status_code == 201, create.text
        # by-module response now buckets it under custom_module.
        r = client.get(
            "/api/v3/master/permissions/by-module",
            headers=admin_headers,
        )
        data = r.json()["data"]
        bucket = next(
            (m for m in data["_embedded"]["modules"]
             if m["module"] == "custom_module"),
            None,
        )
        assert bucket is not None, "custom_module bucket missing"
        codes = [p["code"] for p in bucket["permissions"]]
        assert "custom_module:my_action" in codes
        # And the entry is marked as not built-in.
        entry = next(p for p in bucket["permissions"] if p["code"] == "custom_module:my_action")
        assert entry["isBuiltin"] is False


# ===========================================================================
# Runtime permission registration (existing functionality, regression-pinned)
# ===========================================================================

class TestRuntimePermissionRegistration:
    def test_create_custom_permission(self, client, admin_user, admin_headers):
        r = client.post(
            "/api/v3/master/permissions/create",
            json={
                "code": "feature_x:trigger",
                "name": "Trigger feature X",
                "description": "Custom permission for feature X.",
            },
            headers=admin_headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()["data"]
        assert body["code"] == "feature_x:trigger"
        assert body["isBuiltin"] is False

    def test_duplicate_code_rejected(self, client, admin_user, admin_headers):
        client.post(
            "/api/v3/master/permissions/create",
            json={
                "code": "dup_test:once",
                "name": "First time",
                "description": "first",
            },
            headers=admin_headers,
        )
        r = client.post(
            "/api/v3/master/permissions/create",
            json={
                "code": "dup_test:once",
                "name": "Second time",
                "description": "second",
            },
            headers=admin_headers,
        )
        assert r.status_code == 409, r.text

    def test_builtin_cannot_be_deleted(self, client, admin_user, admin_headers):
        # Try to delete a built-in code (e.g. projects:create).
        r = client.delete(
            "/api/v3/master/permissions/projects:create",
            headers=admin_headers,
        )
        assert r.status_code == 403, r.text

    def test_custom_permission_can_be_deleted(self, client, admin_user, admin_headers):
        client.post(
            "/api/v3/master/permissions/create",
            json={
                "code": "delete_me:now",
                "name": "Delete-me",
                "description": "to delete",
            },
            headers=admin_headers,
        )
        r = client.delete(
            "/api/v3/master/permissions/delete_me:now",
            headers=admin_headers,
        )
        assert r.status_code == 204, r.text


# ===========================================================================
# RBAC artifact cleanup
# ===========================================================================

class TestRBACArtifactCleanup:
    def test_role_enum_removed(self):
        """Doc 33 change 2: ``Role`` enum was deleted."""
        from app.core import rbac as rbac_module
        assert not hasattr(rbac_module, "Role"), (
            "Doc 33 change 2: Role enum should be deleted from app/core/rbac.py"
        )

    def test_role_permissions_dict_removed(self):
        from app.core import rbac as rbac_module
        assert not hasattr(rbac_module, "ROLE_PERMISSIONS")

    def test_has_permission_helper_removed(self):
        from app.core import rbac as rbac_module
        assert not hasattr(rbac_module, "has_permission")

    def test_get_role_permissions_helper_removed(self):
        from app.core import rbac as rbac_module
        assert not hasattr(rbac_module, "get_role_permissions")

    def test_permission_enum_kept_as_bridge(self):
        """The ``Permission`` enum is intentionally kept — every
        ``app/api/v3/*/permissions.py`` re-export shim still imports it.
        Will be deprecated separately."""
        from app.core.rbac import Permission
        # A few sample codes to confirm the enum is intact.
        assert Permission.USERS_CREATE.value == "users:create"
        assert Permission.PROJECTS_PUBLISH.value == "projects:publish"
