"""
Simple validation test for Roles module (no pytest dependency).
"""
from app.api.v3.roles.services.create import create_role
from app.api.v3.roles.services.get import get_role_by_id, get_role_by_name
from app.api.v3.roles.services.list import list_roles
from app.api.v3.roles.services.update import update_role
from app.api.v3.roles.services.delete import delete_role
from app.infrastructure.db.session import get_db, Base, engine


def test_roles_module():
    """Test the Roles module functionality."""
    print("\n" + "="*60)
    print("TESTING ROLES MODULE")
    print("="*60)

    # Setup database
    Base.metadata.create_all(bind=engine)
    db = next(get_db())

    try:
        # Test 1: Create role
        print("\n[1/7] Testing create_role...")
        result = create_role(
            db=db,
            name="Editor",
            permissions=["projects:view", "projects:edit"],
            builtin=False
        )
        assert result.is_success(), f"Failed to create role: {result.error}"
        assert result.data.name == "Editor"
        print("[PASS] create_role works")

        role_id = result.data.id

        # Test 2: Get role by ID
        print("[2/7] Testing get_role_by_id...")
        result = get_role_by_id(db=db, role_id=role_id)
        assert result.is_success(), f"Failed to get role: {result.error}"
        assert result.data.name == "Editor"
        print("[PASS] get_role_by_id works")

        # Test 3: Get role by name
        print("[3/7] Testing get_role_by_name...")
        result = get_role_by_name(db=db, name="Editor")
        assert result.is_success(), f"Failed to get role by name: {result.error}"
        assert result.data.id == role_id
        print("[PASS] get_role_by_name works")

        # Test 4: Create builtin role
        print("[4/7] Testing create builtin role...")
        result = create_role(
            db=db,
            name="Admin",
            permissions=["*"],
            builtin=True
        )
        assert result.is_success(), f"Failed to create builtin role: {result.error}"
        assert result.data.builtin is True
        print("[PASS] Builtin role creation works")

        builtin_role_id = result.data.id

        # Test 5: List roles
        print("[5/7] Testing list_roles...")
        result = list_roles(db=db, offset=0, limit=20)
        assert result.is_success(), f"Failed to list roles: {result.error}"
        roles, total = result.data
        assert total == 2, f"Expected 2 roles, got {total}"
        assert len(roles) == 2
        print(f"[PASS] list_roles works (found {total} roles)")

        # Test 6: Update role
        print("[6/7] Testing update_role...")
        result = update_role(
            db=db,
            role_id=role_id,
            name="Reviewer",
            permissions=["projects:view", "projects:comment"]
        )
        assert result.is_success(), f"Failed to update role: {result.error}"
        assert result.data.name == "Reviewer"
        print("[PASS] update_role works")

        # Test 7: Verify builtin role cannot be modified
        print("[7/7] Testing builtin role protection...")
        result = update_role(
            db=db,
            role_id=builtin_role_id,
            name="SuperAdmin"
        )
        assert result.is_failure(), "Builtin role should not be modifiable"
        assert result.error_type == "forbidden"
        print("[PASS] Builtin role protection works")

        # Additional test: Delete non-builtin role
        print("\n[BONUS] Testing delete_role...")
        result = delete_role(db=db, role_id=role_id)
        assert result.is_success(), f"Failed to delete role: {result.error}"
        print("[PASS] delete_role works")

        # Additional test: Cannot delete builtin role
        print("[BONUS] Testing builtin role deletion protection...")
        result = delete_role(db=db, role_id=builtin_role_id)
        assert result.is_failure(), "Builtin role should not be deletable"
        assert result.error_type == "forbidden"
        print("[PASS] Builtin role deletion protection works")

        print("\n" + "="*60)
        print("ALL TESTS PASSED!")
        print("="*60)
        return True

    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    success = test_roles_module()
    exit(0 if success else 1)
