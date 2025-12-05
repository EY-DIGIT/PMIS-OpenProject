"""
Simple database initialization script that works standalone.
Run this from the user_service directory: python init_db_simple.py
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from database import Base

# Database configuration
DATABASE_URL = "sqlite:///./openproject.db"

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_tables():
    """Create all tables"""
    print("="*60)
    print("OpenProject Database Initialization")
    print("="*60)
    print("\nImporting models...")

    # Import SQLAlchemy models (must import to register with Base)
    import db_models  # This imports DBUser, DBUserPreference, etc.
    from models.project import Project
    from models.member import Member, MemberRole, Role, RolePermission
    from models.enabled_module import EnabledModule

    print("[OK] Models imported successfully")

    print("\nCreating tables...")
    Base.metadata.create_all(bind=engine)

    # Verify tables
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"\n[OK] Created/verified {len(tables)} tables:")
    for table in sorted(tables):
        print(f"  + {table}")

    return True


def seed_roles():
    """Seed default roles"""
    print("\nSeeding default roles...")

    from models.member import Role, RolePermission

    db = SessionLocal()
    try:
        # Check if roles already exist
        existing_roles = db.query(Role).count()
        if existing_roles > 0:
            print(f"[INFO] Found {existing_roles} existing roles, skipping seed")
            return True

        # Define default roles with permissions
        default_roles = [
            {
                'name': 'Project admin',
                'position': 1,
                'builtin': 0,
                'permissions': [
                    'view_project', 'search_project', 'edit_project',
                    'edit_project_attributes', 'manage_members',
                    'view_members', 'add_subprojects', 'archive_project',
                    'copy_projects'
                ]
            },
            {
                'name': 'Member',
                'position': 2,
                'builtin': 0,
                'permissions': ['view_project', 'search_project', 'view_members']
            },
            {
                'name': 'Reader',
                'position': 3,
                'builtin': 0,
                'permissions': ['view_project', 'search_project']
            },
        ]

        created_count = 0
        for role_data in default_roles:
            # Create role
            role = Role(
                name=role_data['name'],
                position=role_data['position'],
                builtin=role_data['builtin']
            )
            db.add(role)
            db.flush()  # Get role ID

            # Add permissions
            for perm in role_data['permissions']:
                role_perm = RolePermission(role_id=role.id, permission=perm)
                db.add(role_perm)

            created_count += 1
            print(f"  + Created role: {role.name} with {len(role_data['permissions'])} permissions")

        db.commit()
        print(f"\n[OK] Seeded {created_count} default roles")
        return True

    except Exception as e:
        print(f"\n[ERROR] Failed to seed roles: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def verify():
    """Verify the setup"""
    print("\nVerifying setup...")

    from models.member import Role
    from models.project import Project

    db = SessionLocal()
    try:
        role_count = db.query(Role).count()
        project_count = db.query(Project).count()

        print(f"  + Roles: {role_count}")
        print(f"  + Projects: {project_count}")

        if role_count == 0:
            print("\n[WARNING] No roles found!")
            return False

        print("\n[OK] Verification complete")
        return True

    except Exception as e:
        print(f"\n[ERROR] Verification failed: {e}")
        return False
    finally:
        db.close()


def main():
    """Main function"""
    try:
        # Step 1: Create tables
        if not init_tables():
            print("\n[ERROR] Table creation failed")
            return 1

        # Step 2: Seed roles
        if not seed_roles():
            print("\n[ERROR] Role seeding failed")
            return 1

        # Step 3: Verify
        if not verify():
            print("\n[ERROR] Verification failed")
            return 1

        # Success
        print("\n" + "="*60)
        print("[SUCCESS] Database initialized successfully!")
        print("="*60)
        print("\nNext steps:")
        print("  1. Start the FastAPI server:")
        print("     uvicorn user_service.main:app --reload --port 8000")
        print("\n  2. Open API documentation:")
        print("     http://localhost:8000/api/docs")
        print()

        return 0

    except Exception as e:
        print(f"\n[ERROR] Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
