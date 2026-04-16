# Project API Enhancements - Quick Reference

## Key Files Modified

| File | Changes |
|------|---------|
| `infrastructure/db/models/project.py` | Added 5 new columns: status, owner, category, start_date, end_date |
| `domain/projects/project.py` | Added 5 new fields to dataclass and to_dict() |
| `api/v3/projects/schemas.py` | Added validators for new fields + PROJECT_STATUS_CHOICES and PROJECT_CATEGORY_CHOICES |
| `infrastructure/db/repositories/project_repository.py` | Updated _to_domain(), create(), update() methods |
| `api/v3/projects/services/create.py` | Added verify_user_exists() + date/owner validation |
| `api/v3/projects/services/update.py` | Added verify_user_exists() + date/owner validation |
| `api/v3/projects/controller.py` | Updated create() and update() methods to pass new fields |

## New Fields Summary

| Field | Type | Validation | Notes |
|-------|------|-----------|-------|
| `status` | String | Enum (new, in_progress, completed, on_hold) | Configured in schemas.py |
| `owner` | String | Username must exist in users table | Via verify_user_exists() |
| `category` | String | Enum (MSAP, MSIP, BSP) | Configured in schemas.py |
| `start_date` | DateTime | Must be future, ISO 8601 format | Optional |
| `end_date` | DateTime | Must be future AND after start_date | Optional |

## Validation Logic at Each Layer

### Schema Layer (Pydantic)
- Status & Category enum validation
- Date future validation
- Date ordering validation (end_date > start_date)
- All validators run at request parsing time

### Service Layer
- Owner username validation via database lookup
- Date future validation (double-check)
- Date ordering validation (double-check with existing data on update)
- Descriptive error messages

## Configuration Files

**To add/modify allowed values, edit:**
- `app/api/v3/projects/schemas.py` lines containing:
  - `PROJECT_STATUS_CHOICES`
  - `PROJECT_CATEGORY_CHOICES`

## Placeholder Functions

**`verify_user_exists(db: Session, username: str) -> bool`**
- Location: `create.py` and `update.py` in services/
- Currently queries user by login via UserRepository
- Can be extended to integrate with external auth service
- Returns True if user exists in system

## Important Notes

1. **Dates are always compared against UTC time** using `datetime.utcnow()`
2. **Owner validation is mandatory** if owner field is provided
3. **All new fields are backward compatible** - existing projects work unchanged
4. **Database migration required** - see PROJECT_API_ENHANCEMENTS.md for SQL

## Example Request

```json
POST /api/v3/projects
{
  "identifier": "digital-transformation",
  "name": "Digital Transformation Initiative",
  "description": "Company-wide digital modernization",
  "status": "new",
  "owner": "alice_smith",
  "category": "MSAP",
  "start_date": "2026-06-01T00:00:00Z",
  "end_date": "2026-12-31T23:59:59Z",
  "active": true,
  "public": true
}
```

## Testing Checklist

- [ ] Create project with all new fields
- [ ] Verify date validation (future dates required)
- [ ] Verify date ordering (end_date > start_date)
- [ ] Verify owner validation (non-existent user rejected)
- [ ] Verify status validation (only allowed values accepted)
- [ ] Verify category validation (only allowed values accepted)
- [ ] Test update with partial fields
- [ ] Test backward compatibility with old requests
- [ ] Verify all new fields appear in GET responses
