"""
Script to create an initial admin user.
"""
from app.infrastructure.db.session import SessionLocal, init_db
from app.infrastructure.db.repositories.user_repository import UserRepository
from app.core.security import hash_password

def create_admin_user():
    """Create initial admin user."""
    # Initialize database
    init_db()

    # Create session
    db = SessionLocal()

    try:
        repository = UserRepository(db)

        # Check if admin already exists
        existing_admin = repository.get_by_login("admin")
        if existing_admin:
            print("Admin user already exists!")
            print(f"Login: {existing_admin.login}")
            print(f"Email: {existing_admin.email}")
            return

        # Create admin user
        hashed_password = hash_password("admin123")

        admin_user = repository.create(
            login="admin",
            email="admin@example.com",
            hashed_password=hashed_password,
            first_name="Admin",
            last_name="User",
            admin=True,
            status="active"
        )

        print("Admin user created successfully!")
        print(f"Login: {admin_user.login}")
        print(f"Email: {admin_user.email}")
        print(f"Password: admin123")
        print(f"Admin: {admin_user.admin}")

    except Exception as e:
        print(f"Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_admin_user()
