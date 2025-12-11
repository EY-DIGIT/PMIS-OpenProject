"""
Initialize database with meeting tables.

This script creates all the necessary tables for the meetings module.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from database import Base, engine
import db_models


def init_meetings_tables():
    """Create all meeting-related tables"""
    print("Creating meeting tables...")

    # This will create all tables defined in db_models.py
    Base.metadata.create_all(bind=engine)

    print("[OK] Meeting tables created successfully!")
    print("\nCreated tables:")
    print("  - meetings")
    print("  - recurring_meetings")
    print("  - scheduled_meetings")
    print("  - meeting_participants")
    print("  - meeting_sections")
    print("  - meeting_agenda_items")
    print("  - meeting_outcomes")


if __name__ == "__main__":
    init_meetings_tables()
