# Project API Enhancements - Implementation Guide

## Overview
This document describes the enhancements made to the `/api/v3/projects` endpoint to support advanced project management features including status tracking, ownership, categorization, and date management.

## Changes Summary

### 1. New Fields Added

#### Status Field
- **Field Name:** `status`
- **Type:** String
- **Default Value:** `"new"`
- **Allowed Values:** `["new", "in_progress", "completed", "on_hold"]`
- **Configuration Location:** `app/api/v3/projects/schemas.py` → `PROJECT_STATUS_CHOICES`
- **Validation:** Enum validation at schema and service level

#### Owner Field
- **Field Name:** `owner`
- **Type:** String (username)
- **Default Value:** `None` (optional)
- **Validation:** 
  - Queried against the `users` table via `UserRepository.get_by_login(username)`
  - Raises validation error if user does not exist
  - Function: `verify_user_exists(db, username)` in create/update services
- **Use Case:** Track project ownership and responsibility

#### Category Field
- **Field Name:** `category`
- **Type:** String (enum)
- **Default Value:** `None` (optional)
- **Allowed Values:** `["MSAP", "MSIP", "BSP"]`
- **Configuration Location:** `app/api/v3/projects/schemas.py` → `PROJECT_CATEGORY_CHOICES`
- **Validation:** Enum validation at schema and service level

#### Date Fields
- **Field Names:** `start_date`, `end_date`
- **Type:** DateTime (ISO 8601 format)
- **Default Value:** `None` (optional)
- **Validation Logic:**
  1. Both dates MUST be in the future (> current UTC time)
  2. `end_date` MUST be after `start_date`
  3. If only one date is provided, validation only applies to that date
  4. If updating and new date not provided, existing date is used for comparison

## Validation Logic Explanation

### Date Validation (in `schemas.py`)

```python
@field_validator("start_date", "end_date")
@classmethod
def validate_dates_in_future(cls, v):
    """Validate that dates are in the future."""
    if v is not None and v <= datetime.utcnow():
        raise ValueError("Date must be in the future")
    return v

@field_validator("end_date")
@classmethod
def validate_end_date_after_start_date(cls, v, info):
    """Validate that end_date is after start_date if both are provided."""
    if v is not None and "start_date" in info.data and info.data["start_date"] is not None:
        if v <= info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
    return v
```

**How It Works:**
1. `validate_dates_in_future`: Each date field is independently validated to ensure it's in the future (UTC time)
2. `validate_end_date_after_start_date`: Runs after `start_date` is processed, ensures logical ordering

### Owner Validation (in service layer)

```python
def verify_user_exists(db: Session, username: str) -> bool:
    """Verify if a user exists in the system by username."""
    user_repo = UserRepository(db)
    user = user_repo.get_by_login(username)
    return user is not None
```

**How It Works:**
- Queries the `users` table using the `login` column
- Returns `True` if user found, `False` otherwise
- Service layer checks this before creating/updating project
- Returns descriptive error message if user not found

### Status & Category Validation (in schema layer)

```python
@field_validator("status")
@classmethod
def validate_status(cls, v):
    """Validate that status is from the allowed list."""
    if v not in PROJECT_STATUS_CHOICES:
        raise ValueError(
            f"Invalid status '{v}'. Allowed values: {', '.join(PROJECT_STATUS_CHOICES)}. "
            f"To add more status values, update PROJECT_STATUS_CHOICES in app/api/v3/projects/schemas.py"
        )
    return v
```

**How It Works:**
- Checks value against defined choices at request validation time
- Provides helpful error message directing to configuration location
- Works for both `ProjectCreateRequest` and `ProjectUpdateRequest`

## File Changes

### 1. Database Model (`infrastructure/db/models/project.py`)
- Added 5 new columns: `status`, `owner`, `category`, `start_date`, `end_date`
- Added indexes for new columns for query performance
- Updated `__repr__` to include status for better debugging

### 2. Domain Model (`domain/projects/project.py`)
- Added 5 new fields with appropriate defaults
- Updated `to_dict()` method to include new fields in serialization
- Dates serialized to ISO 8601 format

### 3. Request/Response Schemas (`api/v3/projects/schemas.py`)
- Added `PROJECT_STATUS_CHOICES` and `PROJECT_CATEGORY_CHOICES` constants
- Extended `ProjectCreateRequest` with new fields and validators
- Extended `ProjectUpdateRequest` with new optional fields and validators
- Both request schemas include field validators using Pydantic 2.0 syntax

### 4. Repository (`infrastructure/db/repositories/project_repository.py`)
- Updated `_to_domain()` to map new database columns
- Extended `create()` method signature with new parameters
- Extended `update()` method signature with new parameters
- Both methods handle None values appropriately for optional fields

### 5. Create Service (`api/v3/projects/services/create.py`)
- Added `verify_user_exists()` function for owner validation
- Added validation for future dates
- Added validation for date ordering (end_date > start_date)
- Added owner username validation against users table
- Returns descriptive validation errors for each failure case

### 6. Update Service (`api/v3/projects/services/update.py`)
- Added `verify_user_exists()` function for owner validation
- Added validation for future dates
- Added intelligent date comparison: uses existing date if new one not provided
- Maintains immutability of unmodified fields

### 7. Controller (`api/v3/projects/controller.py`)
- Updated `create()` method to pass new fields to service
- Updated `update()` method to pass new fields to service
- Existing error handling remains unchanged

## Configuration Instructions

### To Add New Project Statuses:
1. Edit `app/api/v3/projects/schemas.py`
2. Modify `PROJECT_STATUS_CHOICES` list:
   ```python
   PROJECT_STATUS_CHOICES = ["new", "in_progress", "completed", "on_hold", "archived"]
   ```
3. Changes apply immediately to all new/updated projects

### To Add New Project Categories:
1. Edit `app/api/v3/projects/schemas.py`
2. Modify `PROJECT_CATEGORY_CHOICES` list:
   ```python
   PROJECT_CATEGORY_CHOICES = ["MSAP", "MSIP", "BSP", "OTHER"]
   ```
3. Changes apply immediately to all new/updated projects

### To Customize Owner Validation:
1. Edit the `verify_user_exists()` function in:
   - `app/api/v3/projects/services/create.py`
   - `app/api/v3/projects/services/update.py`
2. Integrate with your auth service as needed
3. Example integration with external auth:
   ```python
   def verify_user_exists(db: Session, username: str) -> bool:
       """Integrate with external auth service"""
       return AuthService.check_user_exists(username)
   ```

## API Usage Examples

### Create Project with New Fields
```json
POST /api/v3/projects

{
  "identifier": "proj-001",
  "name": "New Infrastructure",
  "description": "Building new infrastructure",
  "status": "new",
  "owner": "johndoe",
  "category": "MSAP",
  "start_date": "2026-05-01T00:00:00Z",
  "end_date": "2026-12-31T23:59:59Z"
}
```

### Update Project
```json
PATCH /api/v3/projects/1

{
  "status": "in_progress",
  "start_date": "2026-04-20T00:00:00Z"
}
```

## Error Response Examples

### Invalid Status
```json
{
  "detail": "Invalid status 'invalid'. Allowed values: new, in_progress, completed, on_hold. To add more status values, update PROJECT_STATUS_CHOICES in app/api/v3/projects/schemas.py"
}
```

### Date in Past
```json
{
  "detail": "Date must be in the future"
}
```

### End Date Before Start Date
```json
{
  "detail": "end_date must be after start_date"
}
```

### Invalid Owner Username
```json
{
  "detail": "Owner user with username 'invalid_user' does not exist. Verify the user exists by checking the users endpoint."
}
```

## Database Migration Required

This implementation requires a database migration to add the new columns. Example migration:

```sql
ALTER TABLE projects ADD COLUMN status VARCHAR(50) DEFAULT 'new' NOT NULL;
ALTER TABLE projects ADD COLUMN owner VARCHAR(255) NULL;
ALTER TABLE projects ADD COLUMN category VARCHAR(50) NULL;
ALTER TABLE projects ADD COLUMN start_date DATETIME NULL;
ALTER TABLE projects ADD COLUMN end_date DATETIME NULL;

CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_owner ON projects(owner);
CREATE INDEX idx_projects_category ON projects(category);
CREATE INDEX idx_projects_start_date ON projects(start_date);
CREATE INDEX idx_projects_end_date ON projects(end_date);
```

## Best Practices

1. **Date Handling:** Always provide dates in ISO 8601 format with timezone information
2. **Owner Assignment:** Verify owner username exists before API call by checking the users endpoint
3. **Status Transitions:** Consider adding business logic to validate status transitions (e.g., can only move from "new" to "in_progress")
4. **Category Assignment:** Consider making category required for certain project types
5. **Date Validation:** The API validates dates are in the future at creation time; consider periodic checks for projects that have passed their end_date

## Compatibility Notes

- **Breaking Changes:** None. All new fields are optional or have sensible defaults
- **Existing Data:** Projects created before this enhancement will have:
  - `status`: "new" (default)
  - `owner`: NULL
  - `category`: NULL
  - `start_date`: NULL
  - `end_date`: NULL
- **Backward Compatibility:** All existing API calls work unchanged
