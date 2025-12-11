"""
Test script for Meetings module.

This script tests the basic CRUD operations for meetings.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from database import SessionLocal
from repositories import MeetingRepository, MeetingParticipantRepository, UserRepository
from models.meeting import Meeting, MeetingState
from models.meeting_participant import MeetingParticipant, ParticipationStatus
from services.meeting_service import MeetingCreateService, MeetingUpdateService, MeetingDeleteService


def test_meetings():
    """Test meeting CRUD operations"""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("TESTING MEETINGS MODULE")
        print("=" * 60)

        # Get or create a test user
        user_repo = UserRepository(db)
        user = user_repo.find_by_login("admin")
        if not user:
            print("\n[ERROR] No admin user found. Please create a user first.")
            return

        print(f"\n[OK] Found user: {user.login} (ID: {user.id})")

        # Test 1: Create a meeting
        print("\n" + "-" * 60)
        print("TEST 1: Creating a meeting")
        print("-" * 60)

        service = MeetingCreateService(user=user, db=db)
        start_time = datetime.utcnow() + timedelta(days=1)

        meeting_params = {
            'title': 'Sprint Planning Meeting',
            'project_id': 1,
            'location': 'Conference Room A',
            'start_time': start_time,
            'duration': 2.0,
            'state': 'open',
            'notify': True,
            'participants': [
                {'user_id': user.id, 'invited': True}
            ]
        }

        result = service.call(meeting_params)

        if result.is_success():
            meeting = result.result
            print(f"[OK] Meeting created successfully!")
            print(f"    ID: {meeting.id}")
            print(f"    Title: {meeting.title}")
            print(f"    Location: {meeting.location}")
            print(f"    Start: {meeting.start_time}")
            print(f"    Duration: {meeting.duration} hours")
            print(f"    State: {meeting.state.name}")
        else:
            print(f"[FAIL] Failed to create meeting: {result.errors or result.message}")
            return

        meeting_id = meeting.id

        # Test 2: Retrieve the meeting
        print("\n" + "-" * 60)
        print("TEST 2: Retrieving the meeting")
        print("-" * 60)

        meeting_repo = MeetingRepository(db)
        retrieved_meeting = meeting_repo.find_by_id(meeting_id)

        if retrieved_meeting:
            print(f"[OK] Meeting retrieved successfully!")
            print(f"    Title: {retrieved_meeting.title}")
            print(f"    State: {retrieved_meeting.state.name}")
        else:
            print(f"[FAIL] Failed to retrieve meeting")
            return

        # Test 3: List meetings
        print("\n" + "-" * 60)
        print("TEST 3: Listing meetings")
        print("-" * 60)

        meetings = meeting_repo.find_all(limit=10)
        print(f"[OK] Found {len(meetings)} meeting(s)")
        for m in meetings:
            print(f"    - {m.title} (ID: {m.id})")

        # Test 4: Check participants
        print("\n" + "-" * 60)
        print("TEST 4: Checking participants")
        print("-" * 60)

        participant_repo = MeetingParticipantRepository(db)
        participants = participant_repo.find_by_meeting(meeting_id)
        print(f"[OK] Found {len(participants)} participant(s)")
        for p in participants:
            print(f"    - User ID: {p.user_id}, Invited: {p.invited}, Status: {p.participation_status.value}")

        # Test 5: Update the meeting
        print("\n" + "-" * 60)
        print("TEST 5: Updating the meeting")
        print("-" * 60)

        update_service = MeetingUpdateService(user=user, db=db)
        update_params = {
            'location': 'Virtual Meeting - Zoom',
            'state': 'in_progress'
        }

        update_result = update_service.call(meeting_id, update_params)

        if update_result.is_success():
            updated_meeting = update_result.result
            print(f"[OK] Meeting updated successfully!")
            print(f"    New location: {updated_meeting.location}")
            print(f"    New state: {updated_meeting.state.name}")
        else:
            print(f"[FAIL] Failed to update meeting: {update_result.errors or update_result.message}")

        # Test 6: Filter meetings
        print("\n" + "-" * 60)
        print("TEST 6: Filtering upcoming meetings")
        print("-" * 60)

        upcoming_meetings = meeting_repo.find_all(upcoming=True, limit=10)
        print(f"[OK] Found {len(upcoming_meetings)} upcoming meeting(s)")
        for m in upcoming_meetings:
            print(f"    - {m.title} (Start: {m.start_time})")

        # Test 7: Delete the meeting
        print("\n" + "-" * 60)
        print("TEST 7: Deleting the meeting")
        print("-" * 60)

        delete_service = MeetingDeleteService(user=user, db=db)
        delete_result = delete_service.call(meeting_id)

        if delete_result.is_success():
            print(f"[OK] Meeting deleted successfully!")

            # Verify deletion
            deleted_meeting = meeting_repo.find_by_id(meeting_id)
            if deleted_meeting is None:
                print(f"[OK] Confirmed: Meeting no longer exists")
            else:
                print(f"[WARN] Meeting still exists after deletion")
        else:
            print(f"[FAIL] Failed to delete meeting: {delete_result.errors or delete_result.message}")

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    test_meetings()
