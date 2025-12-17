#!/usr/bin/env python
"""Check that all required files exist."""
import os
import sys

files = [
    'app/domain/roles/__init__.py',
    'app/domain/roles/role.py',
    'app/infrastructure/db/models/role.py',
    'app/infrastructure/db/repositories/role_repository.py',
    'app/api/v3/roles/__init__.py',
    'app/api/v3/roles/routes.py',
    'app/api/v3/roles/controller.py',
    'app/api/v3/roles/schemas.py',
    'app/api/v3/roles/permissions.py',
    'app/api/v3/roles/services/__init__.py',
    'app/api/v3/roles/services/create.py',
    'app/api/v3/roles/services/get.py',
    'app/api/v3/roles/services/list.py',
    'app/api/v3/roles/services/update.py',
    'app/api/v3/roles/services/delete.py',
]

print("\nChecking Roles Module Files:")
print("="*60)

all_exist = True
for f in files:
    if os.path.exists(f):
        print(f"[OK] {f}")
    else:
        print(f"[MISSING] {f}")
        all_exist = False

print("="*60)
if all_exist:
    print("Status: ALL FILES PRESENT")
    sys.exit(0)
else:
    print("Status: SOME FILES MISSING")
    sys.exit(1)
