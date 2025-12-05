"""
Database initialization script for Project module.

Creates all necessary tables and seeds default data.
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, inspect

# Try relative imports first, then absolute
try:
    from .database import SessionLocal, Base, engine
    from .utils.permissions import seed_default_roles
except ImportError:
    from database import SessionLocal, Base, engine
    from utils.permissions import seed_default_roles


def init_project_tables():
    """Create all project-related tables"""
    print("Creating project module tables...")

    # Import all models to register them with Base
    try:
        from .models import (
            Project, Member, MemberRole, Role, RolePermission, EnabledModule
        )
    except ImportError:
        from models import (
            Project, Member, MemberRole, Role, RolePermission, EnabledModule
        )

    # Import User from db_models (SQLAlchemy model)
    try:
        from .db_models import DBUser
    except ImportError:
        from db_models import DBUser

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Check what tables were created
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"\nCreated/verified {len(tables)} tables:")
    for table in sorted(tables):
        print(f"  + {table}")

    print("\nProject module tables initialized successfully!")


def seed_default_data():
    """Seed default roles and permissions"""
    print("\nSeeding default data...")

    db = SessionLocal()
    try:
        # Seed default roles
        created_roles = seed_default_roles(db)

        if created_roles:
            print(f"\n[OK] Seeded {len(created_roles)} default roles")
        else:
            print("\n[OK] Default roles already exist")

        print("\nDefault data seeded successfully!")

    except Exception as e:
        print(f"\n[ERROR] Error seeding data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def verify_setup():
    """Verify the setup is correct"""
    print("\nVerifying setup...")

    db = SessionLocal()
    try:
        try:
            from .models import Role, Project
        except ImportError:
            from models import Role, Project

        # Check roles
        role_count = db.query(Role).count()
        print(f"  + Roles: {role_count}")

        # Check projects
        project_count = db.query(Project).count()
        print(f"  + Projects: {project_count}")

        if role_count == 0:
            print("\n[WARNING] No roles found. Run seed_default_data() to create default roles.")

        print("\n[OK] Setup verification complete!")

    except Exception as e:
        print(f"\n[ERROR] Error verifying setup: {e}")
        raise
    finally:
        db.close()


def main():
    """Main initialization function"""
    print("="*60)
    print("OpenProject Project Module - Database Initialization")
    print("="*60)

    try:
        # Step 1: Create tables
        init_project_tables()

        # Step 2: Seed default data
        seed_default_data()

        # Step 3: Verify setup
        verify_setup()

        print("\n" + "="*60)
        print("[SUCCESS] Initialization complete!")
        print("="*60)
        print("\nYou can now start the FastAPI server:")
        print("  uvicorn main:app --reload --port 8000")
        print("\nAPI documentation will be available at:")
        print("  http://localhost:8000/docs")

    except Exception as e:
        print(f"\n[ERROR] Initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
