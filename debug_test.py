#!/usr/bin/env python
"""Quick debug script to test login"""
import sys
sys.path.insert(0, '/c/Programming/PMIS_Python')

from app.infrastructure.db.session import SessionLocal, init_db
from app.api.v3.users.services import authenticate_user

# Initialize DB
init_db()

# Test authenticate
db = SessionLocal()
try:
    result = authenticate_user(db, login="admin", password="admin123")
    print(f"Result: {result}")
    print(f"Success: {result.is_success()}")
    if result.is_success():
        print(f"Data: {result.data}")
    else:
        print(f"Error: {result.error}")
except Exception as e:
    import traceback
    print(f"Exception: {e}")
    traceback.print_exc()
finally:
    db.close()
