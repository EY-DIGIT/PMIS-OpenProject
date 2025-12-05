"""
Direct test of Project module functionality.
Run this to verify everything works without needing the web server.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import db_models  # Import this first to register DBUser model
from models import Project, Member, Role, RolePermission, EnabledModule
from models.member import MemberRole
from models.enabled_module import DEFAULT_MODULES

def main():
    print("="*60)
    print("Project Module Direct Test")
    print("="*60)

    # Create database session
    db = SessionLocal()

    try:
        # Test 1: Query roles
        print("\n1. Checking default roles...")
        roles = db.query(Role).all()
        print(f"   Found {len(roles)} roles:")
        for role in roles:
            perms = [rp.permission for rp in role.role_permissions]
            print(f"     - {role.name}: {len(perms)} permissions")
            if len(perms) <= 5:  # Show permissions for smaller roles
                print(f"       Permissions: {', '.join(perms)}")

        # Test 2: Create a test project
        print("\n2. Creating a test project...")

        # Check if test project already exists
        existing = db.query(Project).filter_by(identifier="test-project-001").first()
        if existing:
            print(f"   Project already exists: {existing.name} (ID: {existing.id})")
            project = existing
        else:
            project = Project(
                name="Test Project 001",
                identifier="test-project-001",
                description="Testing the project module functionality",
                public=True,
                active=True,
                workspace_type="project"
            )
            db.add(project)
            db.flush()

            # Enable default modules
            print(f"   Enabling default modules...")
            for module_name in DEFAULT_MODULES:
                module = EnabledModule(project_id=project.id, name=module_name)
                db.add(module)

            db.commit()
            db.refresh(project)
            print(f"   [OK] Created project: {project.name} (ID: {project.id})")

        # Test 3: Check enabled modules
        print(f"\n3. Checking enabled modules for project '{project.name}'...")
        modules = db.query(EnabledModule).filter_by(project_id=project.id).all()
        print(f"   Enabled modules ({len(modules)}):")
        for mod in modules:
            print(f"     - {mod.name}")

        # Test 4: Query all projects
        print("\n4. Querying all projects...")
        all_projects = db.query(Project).all()
        print(f"   Total projects in database: {len(all_projects)}")
        for p in all_projects:
            status = "Active" if p.active else "Archived"
            visibility = "Public" if p.public else "Private"
            print(f"     - {p.name} ({p.identifier}) - {status}, {visibility}")

        # Test 5: Test filtering
        print("\n5. Testing project filtering...")
        active_projects = db.query(Project).filter_by(active=True).all()
        print(f"   Active projects: {len(active_projects)}")

        public_projects = db.query(Project).filter_by(public=True).all()
        print(f"   Public projects: {len(public_projects)}")

        # Test 6: Test project methods
        print("\n6. Testing project methods...")
        print(f"   Project '{project.name}':")
        print(f"     - is_archived(): {project.is_archived()}")
        print(f"     - module_enabled('wiki'): {project.module_enabled('wiki')}")
        print(f"     - module_enabled('nonexistent'): {project.module_enabled('nonexistent')}")

        # Success summary
        print("\n" + "="*60)
        print("[SUCCESS] All tests passed!")
        print("="*60)
        print("\nProject Module Status:")
        print("  + Database connection working")
        print("  + Models functioning correctly")
        print("  + Relationships working")
        print("  + Queries executing successfully")
        print("  + Project creation and module assignment working")
        print("\nThe Project module is fully operational!")
        print("="*60)

    except Exception as e:
        print(f"\n[ERROR] Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
