# PMIS Python - User Management Module

Production-ready Python FastAPI backend for OpenProject User module.

## Features

✅ **Complete User Management**
- Create, Read, Update, Delete users
- User authentication with JWT
- Password management
- User listing with pagination
- Current user endpoint (/me)

✅ **Security**
- JWT Bearer token authentication
- Bcrypt password hashing
- Role-Based Access Control (RBAC)
- Middleware-driven security
- Permissions checked at route level

✅ **Architecture**
- Clean separation: Controllers, Services, Repositories, Domain
- HAL+JSON response format (OpenProject API v3 compatible)
- Centralized error handling
- ServiceResult pattern for business logic
- No business logic in controllers
- No auth logic in services
- Database access only through repositories

✅ **Production Ready**
- Comprehensive error handling
- Request/response logging
- Database session management
- Input validation
- Pagination support

## Architecture

```
app/
├── main.py                          # Application entry point
├── core/                            # Core functionality
│   ├── config.py                    # Configuration
│   ├── security.py                  # JWT & password hashing
│   ├── rbac.py                      # Roles & permissions
│   ├── response.py                  # HAL+JSON formatter
│   ├── errors.py                    # Error definitions
│   ├── dependencies.py              # DI helpers
│   └── middleware/
│       ├── auth.py                  # Authentication middleware
│       ├── rbac.py                  # Authorization dependencies
│       └── logging.py               # Logging middleware
├── api/
│   ├── router.py                    # Central API router
│   └── v3/users/
│       ├── routes.py                # URL definitions + permissions
│       ├── controller.py            # Request orchestration
│       ├── schemas.py               # Pydantic models
│       ├── permissions.py           # Permission definitions
│       └── services/                # Business logic
│           ├── create.py
│           ├── update.py
│           ├── delete.py
│           ├── get.py
│           ├── list.py
│           └── authenticate.py
├── domain/users/
│   └── user.py                      # User domain model
├── infrastructure/db/
│   ├── session.py                   # Database session
│   ├── models/user.py               # SQLAlchemy model
│   └── repositories/user_repository.py  # Data access
└── shared/
    ├── service_result.py            # Service result wrapper
    ├── pagination.py                # Pagination utilities
    ├── utils.py                     # Validation helpers
    └── datetime.py                  # DateTime utilities
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create admin user:
```bash
python create_admin.py
```

## Running

Start the server:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or with auto-reload:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Testing

Run comprehensive tests:
```bash
python test_complete.py
```

## API Endpoints

### Public Endpoints
- `POST /api/v3/users/login` - Authenticate and get JWT token

### Authenticated Endpoints
- `GET /api/v3/users/me` - Get current user

### Admin Only Endpoints
- `POST /api/v3/users` - Create user
- `GET /api/v3/users` - List users (paginated)
- `GET /api/v3/users/{id}` - Get user by ID
- `PATCH /api/v3/users/{id}` - Update user
- `PATCH /api/v3/users/{id}/password` - Update password
- `DELETE /api/v3/users/{id}` - Delete user

### Utility Endpoints
- `GET /health` - Health check
- `GET /` - API root

## Default Admin Credentials

```
Login: admin
Password: admin12345
```

**⚠️ Change these in production!**

## Roles & Permissions

### Roles
- `admin` - Full access to all operations
- `member` - Can view and update own profile
- `viewer` - Can view own profile
- `anonymous` - No access

### Permissions
- `users:create` - Create users
- `users:read` - Read user data
- `users:read_all` - List all users
- `users:update` - Update users
- `users:update_all` - Update any user
- `users:delete` - Delete users
- `users:delete_all` - Delete any user

## Response Format

All responses follow HAL+JSON format:

### Single Resource
```json
{
  "_type": "User",
  "_links": {
    "self": {
      "href": "/api/v3/users/1",
      "title": "admin"
    }
  },
  "id": 1,
  "login": "admin",
  "firstName": "Admin",
  "lastName": "User",
  "email": "admin@example.com",
  "admin": true,
  "status": "active",
  "createdAt": "2025-12-15T11:26:26.833674",
  "updatedAt": "2025-12-15T11:26:26.833674"
}
```

### Collection
```json
{
  "_type": "Collection",
  "_links": {
    "self": {"href": "/api/v3/users?offset=1&pageSize=10"}
  },
  "total": 2,
  "count": 2,
  "pageSize": 10,
  "offset": 1,
  "_embedded": {
    "elements": [...]
  }
}
```

### Error
```json
{
  "_type": "Error",
  "errorIdentifier": "not_found",
  "message": "User with ID 99 not found"
}
```

## Configuration

Edit `.env` or modify [app/core/config.py](app/core/config.py):

```python
SECRET_KEY=your-secret-key-change-in-production
DATABASE_URL=sqlite:///./pmis.db
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DEBUG=False
```

## Security Best Practices

✅ **Implemented**
- JWT token-based authentication
- Password hashing with bcrypt
- Role-based access control
- Input validation
- SQL injection protection (SQLAlchemy ORM)
- No sensitive data in logs

⚠️ **Production Recommendations**
- Use PostgreSQL instead of SQLite
- Set strong SECRET_KEY (32+ characters)
- Enable HTTPS
- Implement rate limiting
- Add request timeouts
- Use environment variables for secrets
- Implement token refresh
- Add audit logging
- Set up monitoring

## Database

Uses SQLite by default. Schema:

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    login VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    admin BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Example Usage

### 1. Login
```bash
curl -X POST http://localhost:8000/api/v3/users/login \
  -H "Content-Type: application/json" \
  -d '{"login":"admin","password":"admin12345"}'
```

### 2. Create User
```bash
curl -X POST http://localhost:8000/api/v3/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "login":"newuser",
    "email":"user@example.com",
    "password":"password123",
    "firstName":"John",
    "lastName":"Doe",
    "admin":false
  }'
```

### 3. List Users
```bash
curl -X GET "http://localhost:8000/api/v3/users?offset=1&pageSize=10" \
  -H "Authorization: Bearer <token>"
```

### 4. Get Current User
```bash
curl -X GET http://localhost:8000/api/v3/users/me \
  -H "Authorization: Bearer <token>"
```

## Development

### Adding New Endpoints
1. Add service in `app/api/v3/users/services/`
2. Add controller method in `controller.py`
3. Add route in `routes.py` with permission
4. Add tests

### Adding New Permissions
1. Add to `core/rbac.py` Permission enum
2. Add to `ROLE_PERMISSIONS` mapping
3. Use in route with `require_permission()`

## Testing Checklist

✅ All endpoints tested:
- Health check
- Root endpoint
- Login (authentication)
- Get current user (/me)
- Create user
- Get user by ID
- List users with pagination
- Update user
- Update password
- Delete user
- Permission checks
- Error handling

## License

MIT

## Support

For issues or questions, please check the code comments or review the architecture documentation above.
