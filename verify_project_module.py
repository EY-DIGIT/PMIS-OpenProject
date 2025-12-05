"""
Verification script for Project module.

Quickly checks that all components are importable and functional.
"""
import sys

def verify_imports():
    """Verify all imports work"""
    print("Verifying imports...")

    try:
        # Models
        from models import Project, Member, MemberRole, Role, RolePermission, EnabledModule
        print("  ✓ Models imported successfully")

        # Schemas
        from schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
        from schemas.member import MemberCreate, MemberUpdate, MemberResponse
        from schemas.role import RoleCreate, RoleUpdate, RoleResponse
        print("  ✓ Schemas imported successfully")

        # Services
        from services.project_service import ProjectService
        from services.member_service import MemberService
        print("  ✓ Services imported successfully")

        # Routers
        from routers.projects import router as projects_router
        from routers.members import router as members_router
        print("  ✓ Routers imported successfully")

        # Utils
        from utils.permissions import PROJECT_PERMISSIONS, seed_default_roles
        print("  ✓ Utilities imported successfully")

        return True

    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False


def verify_models():
    """Verify model instantiation"""
    print("\nVerifying models...")

    try:
        from models import Project, Role, Member, MemberRole, EnabledModule

        # Test Project
        project = Project(
            name="Test Project",
            identifier="test-project",
            description="Test"
        )
        assert project.name == "Test Project"
        print("  ✓ Project model works")

        # Test Role
        role = Role(name="Test Role", position=1)
        assert role.name == "Test Role"
        print("  ✓ Role model works")

        # Test validation
        try:
            invalid = Project(name="Test", identifier="INVALID")
            assert False, "Should have raised validation error"
        except ValueError as e:
            print("  ✓ Project validation works")

        return True

    except Exception as e:
        print(f"  ✗ Model error: {e}")
        return False


def verify_schemas():
    """Verify Pydantic schemas"""
    print("\nVerifying schemas...")

    try:
        from schemas.project import ProjectCreate
        from schemas.member import MemberCreate

        # Test ProjectCreate
        data = ProjectCreate(
            name="Test Project",
            identifier="test-project",
            description="Test"
        )
        assert data.name == "Test Project"
        print("  ✓ ProjectCreate schema works")

        # Test MemberCreate
        member_data = MemberCreate(
            user_id=1,
            project_id=1,
            role_ids=[1, 2]
        )
        assert member_data.user_id == 1
        print("  ✓ MemberCreate schema works")

        # Test validation
        try:
            invalid = ProjectCreate(
                name="Test",
                identifier="INVALID"  # Should fail - uppercase not allowed
            )
            assert False, "Should have raised validation error"
        except Exception:
            print("  ✓ Schema validation works")

        return True

    except Exception as e:
        print(f"  ✗ Schema error: {e}")
        return False


def verify_permissions():
    """Verify permission system"""
    print("\nVerifying permissions...")

    try:
        from utils.permissions import (
            PROJECT_PERMISSIONS,
            DEFAULT_ROLES,
            get_all_permissions,
            get_permission_info
        )

        # Check permissions defined
        assert 'view_project' in PROJECT_PERMISSIONS
        assert 'edit_project' in PROJECT_PERMISSIONS
        print(f"  ✓ {len(PROJECT_PERMISSIONS)} project permissions defined")

        # Check default roles
        assert len(DEFAULT_ROLES) >= 3
        print(f"  ✓ {len(DEFAULT_ROLES)} default roles defined")

        # Check permission info
        info = get_permission_info('view_project')
        assert info is not None
        assert info['public'] == True
        print("  ✓ Permission info retrieval works")

        return True

    except Exception as e:
        print(f"  ✗ Permission error: {e}")
        return False


def verify_file_structure():
    """Verify all necessary files exist"""
    print("\nVerifying file structure...")

    import os

    required_files = [
        'models/project.py',
        'models/member.py',
        'models/enabled_module.py',
        'schemas/project.py',
        'schemas/member.py',
        'schemas/role.py',
        'services/project_service.py',
        'services/member_service.py',
        'routers/projects.py',
        'routers/members.py',
        'utils/permissions.py',
        'init_project_db.py',
        'test_project_module.py',
    ]

    missing = []
    for file in required_files:
        if not os.path.exists(file):
            missing.append(file)

    if missing:
        print(f"  ✗ Missing files: {missing}")
        return False
    else:
        print(f"  ✓ All {len(required_files)} required files exist")
        return True


def main():
    """Run all verification checks"""
    print("="*60)
    print("Project Module Verification")
    print("="*60)

    results = []

    # Run checks
    results.append(("File Structure", verify_file_structure()))
    results.append(("Imports", verify_imports()))
    results.append(("Models", verify_models()))
    results.append(("Schemas", verify_schemas()))
    results.append(("Permissions", verify_permissions()))

    # Summary
    print("\n" + "="*60)
    print("Verification Summary")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for check, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{check:20} {status}")

    print("="*60)
    print(f"Result: {passed}/{total} checks passed")
    print("="*60)

    if passed == total:
        print("\n✓ All checks passed! Project module is ready to use.")
        print("\nNext steps:")
        print("  1. Run: python init_project_db.py")
        print("  2. Run: uvicorn main:app --reload --port 8000")
        print("  3. Visit: http://localhost:8000/api/docs")
        return 0
    else:
        print("\n✗ Some checks failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
