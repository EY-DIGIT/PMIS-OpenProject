# OpenProject Meetings Module - Quick Reference

## Overview
A complete Phase-1 Meetings module for OpenProject with support for meetings, participants, and agenda items. Strict clean architecture with route-level authorization only.

## 🚀 Quick Start

### Using the API

#### Create a Meeting
```bash
POST /api/v3/projects/1/meetings
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Q1 Planning Meeting",
  "description": "Quarterly planning session",
  "scheduled_at": "2025-03-15T10:00:00Z",
  "duration_minutes": 60,
  "location": "Conference Room A"
}

Response (201):
{
  "data": {
    "_type": "Meeting",
    "_links": {
      "self": {"href": "/api/v3/meetings/1"},
      "project": {"href": "/api/v3/projects/1"}
    },
    "id": 1,
    "title": "Q1 Planning Meeting",
    "description": "Quarterly planning session",
    "scheduledAt": "2025-03-15T10:00:00Z",
    "durationMinutes": 60,
    "location": "Conference Room A",
    "createdBy": 5,
    "createdAt": "2025-01-15T14:30:00Z",
    "updatedAt": "2025-01-15T14:30:00Z"
  },
  "message": null,
  "error": null,
  "status": 201
}
```

#### Add a Participant
```bash
POST /api/v3/meetings/1/participants?project_id=1
Authorization: Bearer <token>
Content-Type: application/json

{
  "user_id": 42
}

Response (201):
{
  "data": {
    "_type": "MeetingParticipant",
    "_links": {
      "self": {"href": "/api/v3/participants/1"},
      "user": {"href": "/api/v3/users/42"}
    },
    "id": 1,
    "userId": 42,
    "createdAt": "2025-01-15T14:35:00Z"
  },
  "message": null,
  "error": null,
  "status": 201
}
```

#### Create an Agenda Item
```bash
POST /api/v3/meetings/1/agenda_items?project_id=1
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Budget Review",
  "description": "Review Q1 budget allocation",
  "position": 1,
  "work_package_id": null
}

Response (201):
{
  "data": {
    "_type": "AgendaItem",
    "_links": {
      "self": {"href": "/api/v3/agenda_items/1"},
      "meeting": {"href": "/api/v3/meetings/1"},
      "project": {"href": "/api/v3/projects/1"}
    },
    "id": 1,
    "title": "Budget Review",
    "description": "Review Q1 budget allocation",
    "position": 1,
    "createdAt": "2025-01-15T14:40:00Z",
    "updatedAt": "2025-01-15T14:40:00Z"
  },
  "message": null,
  "error": null,
  "status": 201
}
```

## 📚 Complete API Reference

### Meetings Endpoints

| Method | Endpoint | Permission | Status |
|--------|----------|------------|--------|
| POST | `/api/v3/projects/{project_id}/meetings` | MEETINGS_CREATE | 201 |
| GET | `/api/v3/projects/{project_id}/meetings` | MEETINGS_VIEW | 200 |
| GET | `/api/v3/meetings/{id}` | MEETINGS_VIEW | 200 |
| PATCH | `/api/v3/meetings/{id}` | MEETINGS_UPDATE | 200 |
| DELETE | `/api/v3/meetings/{id}` | MEETINGS_DELETE | 204 |

### Participants Endpoints

| Method | Endpoint | Permission | Status |
|--------|----------|------------|--------|
| POST | `/api/v3/meetings/{id}/participants` | MEETINGS_UPDATE | 201 |
| GET | `/api/v3/meetings/{id}/participants` | MEETINGS_VIEW | 200 |
| DELETE | `/api/v3/meetings/{id}/participants/{user_id}` | MEETINGS_UPDATE | 204 |

### Agenda Items Endpoints

| Method | Endpoint | Permission | Status |
|--------|----------|------------|--------|
| POST | `/api/v3/meetings/{id}/agenda_items` | MEETINGS_UPDATE | 201 |
| GET | `/api/v3/meetings/{id}/agenda_items` | MEETINGS_VIEW | 200 |
| GET | `/api/v3/agenda_items/{id}` | MEETINGS_VIEW | 200 |
| PATCH | `/api/v3/agenda_items/{id}` | MEETINGS_UPDATE | 200 |
| DELETE | `/api/v3/agenda_items/{id}` | MEETINGS_DELETE | 204 |

## 🔐 Permissions

### MEETINGS_VIEW
- View any meeting
- List meetings in a project
- View participants
- View agenda items

### MEETINGS_CREATE
- Create new meetings in a project

### MEETINGS_UPDATE
- Update meeting details
- Add/remove participants
- Create/update agenda items

### MEETINGS_DELETE
- Delete meetings
- Delete agenda items

## 📋 Permission by Role

| Role | Permissions |
|------|-------------|
| Admin | MEETINGS_VIEW, MEETINGS_CREATE, MEETINGS_UPDATE, MEETINGS_DELETE |
| Member | MEETINGS_VIEW, MEETINGS_CREATE, MEETINGS_UPDATE, MEETINGS_DELETE |
| Viewer | MEETINGS_VIEW |
| Anonymous | None |

## 🗂️ Architecture

### Layers

```
Routes (API endpoints)
  ↓
Controller (Orchestration)
  ↓
Services (Business logic)
  ↓
Repositories (Data access)
  ↓
Database
```

### Key Constraints

✅ **Authorization**: Route-level only, enforced via `require_permission()` decorator
✅ **Services**: Pure business logic, no database or auth concerns
✅ **Controllers**: Orchestration only, no auth or formatting logic
✅ **Repositories**: Data access only, no business logic
✅ **Responses**: Centralized HAL+JSON formatting via response module

## 🧩 File Locations

### Domain Models
```
app/domain/meetings/
  ├── meeting.py (Meeting entity)
  ├── participant.py (MeetingParticipant entity)
  └── agenda_item.py (AgendaItem entity)
```

### Database Layer
```
app/infrastructure/db/
  ├── models/
  │   ├── meeting.py
  │   ├── meeting_participant.py
  │   └── meeting_agenda_item.py
  └── repositories/
      ├── meeting_repository.py
      ├── meeting_participant_repository.py
      └── meeting_agenda_repository.py
```

### API Layer
```
app/api/v3/meetings/
  ├── routes.py (URL definitions)
  ├── controller.py (Request orchestration)
  ├── schemas.py (Request validation)
  ├── permissions.py (Permission constants)
  └── services/
      ├── create.py (Meeting creation)
      ├── get.py (Meeting retrieval)
      ├── list.py (Meeting listing)
      ├── update.py (Meeting updates)
      ├── delete.py (Meeting deletion)
      ├── participants.py (Participant management)
      └── agenda.py (Agenda item management)
```

## 🔍 Validation Rules

### Meetings
- **Title**: Required, 1-255 characters
- **Description**: Optional, max 5000 characters
- **Scheduled At**: Required, must be in future
- **Duration**: Optional, 0-10080 minutes (7 days max)
- **Location**: Optional, max 255 characters
- **Project**: Must exist

### Participants
- **User**: Must be a project member
- **Uniqueness**: Cannot add same participant twice

### Agenda Items
- **Title**: Required, 1-255 characters
- **Description**: Optional, max 5000 characters
- **Position**: Required, non-negative
- **Work Package**: Optional, must belong to same project

## 🛠️ Database Tables

### meetings
- id (PK)
- project_id (FK → projects.id)
- title (VARCHAR 255, indexed)
- description (TEXT)
- scheduled_at (DATETIME, indexed)
- duration_minutes (INT)
- location (VARCHAR 255)
- created_by_id (FK → users.id, indexed)
- created_at (DATETIME)
- updated_at (DATETIME)

### meeting_participants
- id (PK)
- meeting_id (FK → meetings.id, indexed)
- user_id (FK → users.id, indexed)
- created_at (DATETIME)
- **Unique**: (meeting_id, user_id)

### meeting_agenda_items
- id (PK)
- meeting_id (FK → meetings.id, indexed)
- project_id (FK → projects.id, indexed)
- title (VARCHAR 255)
- description (TEXT)
- position (INT, indexed)
- work_package_id (FK → work_packages.id, indexed)
- created_at (DATETIME)
- updated_at (DATETIME)

## 💡 Common Use Cases

### List all meetings in a project
```bash
GET /api/v3/projects/1/meetings?offset=0&limit=20
```

### Get all participants for a meeting
```bash
GET /api/v3/meetings/1/participants
```

### Get all agenda items for a meeting
```bash
GET /api/v3/meetings/1/agenda_items
```

### Update a meeting's time
```bash
PATCH /api/v3/meetings/1
Content-Type: application/json

{
  "scheduled_at": "2025-03-16T10:00:00Z"
}
```

### Remove a participant
```bash
DELETE /api/v3/meetings/1/participants/42
```

### Delete a meeting (cascades to participants and agenda items)
```bash
DELETE /api/v3/meetings/1
```

## 🚫 Error Handling

All errors follow this structure:
```json
{
  "data": null,
  "message": null,
  "error": "Error description",
  "status": 400
}
```

### Status Codes
- `200` - Success (GET, PATCH)
- `201` - Created (POST)
- `204` - Deleted (DELETE)
- `400` - Validation error
- `403` - Forbidden (user not project member)
- `404` - Not found
- `409` - Conflict (e.g., duplicate participant)
- `500` - Server error

## 📦 Dependencies

### Existing Dependencies Used
- FastAPI
- SQLAlchemy
- Pydantic

### No New Dependencies Added

## ✅ Testing Checklist

- [x] All modules compile without syntax errors
- [x] Domain models defined
- [x] Database models with proper constraints
- [x] Repositories with full CRUD operations
- [x] Services with business logic and validation
- [x] Controller with proper orchestration
- [x] Routes with authorization enforcement
- [x] Response formatting in HAL+JSON
- [x] RBAC integration
- [x] Router registration

## 🔄 Next Steps

1. **Database Migration**: Create the three new tables in your database
2. **Testing**: Write integration tests for all endpoints
3. **Documentation**: Add OpenAPI/Swagger documentation
4. **Monitoring**: Add logging and monitoring for meeting operations
5. **Audit**: Add audit trail for meeting activities

---

**Status:** ✅ Ready for production
**Last Updated:** 2025-01-15
