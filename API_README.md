# OpenProject User Service - FastAPI Backend

A FastAPI implementation of the OpenProject User Service that is **compatible with the OpenProject Angular frontend**.

## 🎯 Frontend Compatibility

### Can the OpenProject Frontend Use This Backend?

**Yes, with configuration!** This FastAPI backend implements the OpenProject API v3 specifications and can work with the Angular frontend, but requires some considerations:

### ✅ What's Compatible

1. **API Structure**: Implements OpenProject API v3 endpoints (`/api/v3/users/*`)
2. **Response Format**: Uses HAL+JSON format matching OpenProject
3. **Authentication**: Supports multiple auth methods (API keys, Bearer tokens, session-based)
4. **User Operations**: Full CRUD operations matching OpenProject API
5. **Status Codes**: HTTP status codes match OpenProject conventions

### ⚠️ What Needs Configuration

1. **Backend URL**: Frontend needs to be configured to point to FastAPI server (default: `http://localhost:8000`)
2. **Feature Parity**: Some OpenProject features beyond user management are not implemented
3. **Database Schema**: While compatible, you'd need to migrate existing OpenProject data
4. **Session Management**: May need additional middleware for full session compatibility

### 🔄 Converting OpenProject Frontend to Use FastAPI Backend

**Partially Feasible** - Here's what you need to know:

#### What You CAN Do:
- Use the OpenProject Angular frontend for user management features
- Replace user-related API calls with this FastAPI backend
- Maintain the same UI/UX for user operations
- Keep the Angular application structure

#### What You CANNOT Do (easily):
- The OpenProject frontend is tightly integrated with Rails backend for:
  - Work packages
  - Projects
  - Time tracking
  - Budgets
  - Other OpenProject features beyond user management

#### Recommended Approach:

**Option 1: Gradual Migration** (Recommended)
- Use this FastAPI backend for new features
- Proxy some calls to original Rails backend
- Gradually migrate other modules

**Option 2: Microservices Architecture**
- Run FastAPI for user service
- Keep Rails backend for other features
- Use API gateway to route requests

**Option 3: Full Rewrite** (Not Recommended)
- Would require implementing all OpenProject features in FastAPI
- Significant development effort
- Better to contribute to OpenProject directly

## 🚀 Installation

### 1. Install Dependencies

```bash
pip install -r requirements_api.txt
```

### 2. Set Up Database

The API uses SQLAlchemy and supports multiple databases:

```python
# For SQLite (development)
DATABASE_URL = "sqlite:///./openproject.db"

# For PostgreSQL (production)
DATABASE_URL = "postgresql://user:password@localhost/openproject"

# For MySQL
DATABASE_URL = "mysql://user:password@localhost/openproject"
```

Configure in [database.py](database.py:11).

### 3. Initialize Database

```bash
python -c "from user_service.database import init_db; init_db()"
```

### 4. Run the Server

```bash
# Development
uvicorn user_service.main:app --reload

# Production
uvicorn user_service.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

## 📡 API Endpoints

### User Management

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/v3/users` | List all users | Admin |
| POST | `/api/v3/users` | Create new user | Admin |
| GET | `/api/v3/users/{id}` | Get user by ID | Optional |
| GET | `/api/v3/users/me` | Get current user | Yes |
| PATCH | `/api/v3/users/{id}` | Update user | Admin |
| DELETE | `/api/v3/users/{id}` | Delete user | Admin |
| GET | `/api/v3/users/schema` | Get user schema | Optional |
| POST | `/api/v3/users/{id}/lock` | Lock user account | Admin |
| POST | `/api/v3/users/{id}/unlock` | Unlock user account | Admin |

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v3/auth/login` | User login |
| POST | `/api/v3/auth/logout` | User logout |
| POST | `/api/v3/auth/register` | User registration |
| POST | `/api/v3/auth/change-password` | Change password |

## 🔐 Authentication

The API supports three authentication methods:

### 1. API Key (Basic Auth)

```bash
curl -u apikey:YOUR_API_KEY http://localhost:8000/api/v3/users/me
```

### 2. Bearer Token

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v3/users/me
```

### 3. Session-based (Angular Client)

```bash
curl -H "X-Requested-With: XMLHttpRequest" \
     -H "Cookie: session_id=SESSION_ID" \
     http://localhost:8000/api/v3/users/me
```

## 📝 Usage Examples

### Create a User

```bash
curl -X POST http://localhost:8000/api/v3/users \
  -H "Content-Type: application/json" \
  -u apikey:YOUR_API_KEY \
  -d '{
    "login": "johndoe",
    "firstName": "John",
    "lastName": "Doe",
    "email": "john@example.com",
    "password": "SecurePass123!",
    "admin": false,
    "status": "active",
    "language": "en"
  }'
```

### Login

```bash
curl -X POST http://localhost:8000/api/v3/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "password": "SecurePass123!"
  }'
```

### List Users

```bash
curl http://localhost:8000/api/v3/users?offset=0&pageSize=20 \
  -u apikey:YOUR_API_KEY
```

### Get Current User

```bash
curl http://localhost:8000/api/v3/users/me \
  -u apikey:YOUR_API_KEY
```

### Update User

```bash
curl -X PATCH http://localhost:8000/api/v3/users/1 \
  -H "Content-Type: application/json" \
  -u apikey:YOUR_API_KEY \
  -d '{
    "firstName": "Jane",
    "preferences": {
      "theme": "dark",
      "timezone": "America/New_York"
    }
  }'
```

### Lock User

```bash
curl -X POST http://localhost:8000/api/v3/users/1/lock \
  -u apikey:YOUR_API_KEY
```

## 🔧 Configuration

### Frontend Configuration

To connect the OpenProject Angular frontend to this backend:

1. **Update API Base URL**

In the Angular app, configure the API base URL:

```typescript
// environment.ts
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api/v3'
};
```

2. **Configure CORS**

The FastAPI backend already includes CORS middleware. Adjust origins in [main.py](main.py:69):

```python
allow_origins=[
    "http://localhost:4200",  # Angular dev server
    "https://your-frontend-domain.com"
]
```

3. **Authentication Setup**

The backend supports the same authentication methods as OpenProject:
- API keys
- OAuth2
- Session-based (for Angular)

## 🧪 Testing

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=user_service --cov-report=html

# Run specific test file
pytest test_api.py -v
```

### Test with cURL

See examples above or use the interactive API docs at `/api/docs`.

### Test with Python

```python
import requests

# Login
response = requests.post(
    "http://localhost:8000/api/v3/auth/login",
    json={"username": "admin", "password": "admin"}
)
print(response.json())

# Get users
response = requests.get(
    "http://localhost:8000/api/v3/users",
    auth=("apikey", "YOUR_API_KEY")
)
print(response.json())
```

## 🏗️ Architecture

```
user_service/
├── api/                      # API layer
│   ├── dependencies.py      # Dependency injection
│   ├── schemas.py           # Pydantic models
│   ├── users.py             # User endpoints
│   └── auth.py              # Auth endpoints
├── models/                   # Domain models
│   ├── user.py
│   ├── user_preference.py
│   └── user_password.py
├── services/                 # Business logic
│   ├── base_service.py
│   └── user_service.py
├── database.py              # Database config
├── db_models.py             # SQLAlchemy models
├── repositories.py          # Data access layer
└── main.py                  # FastAPI app
```

## 📚 API Documentation

### Interactive Documentation

Visit http://localhost:8000/api/docs for:
- Interactive API explorer
- Request/response examples
- Schema definitions
- Try out API calls directly

### HAL+JSON Format

All responses follow the HAL+JSON format used by OpenProject:

```json
{
  "_type": "User",
  "id": 1,
  "login": "johndoe",
  "name": "John Doe",
  "_links": {
    "self": {
      "href": "/api/v3/users/1"
    }
  }
}
```

## 🔒 Security

### Best Practices

1. **Use HTTPS** in production
2. **Set secure cookies**: `secure=True, httponly=True, samesite='strict'`
3. **Implement rate limiting** (use SlowAPI or similar)
4. **Use environment variables** for secrets
5. **Enable CSRF protection** for session-based auth
6. **Regularly update dependencies**

### Environment Variables

```bash
# .env file
DATABASE_URL=postgresql://user:password@localhost/openproject
SECRET_KEY=your-secret-key-here
API_KEY_SALT=your-salt-here
```

## 📈 Performance

### Production Optimization

```bash
# Run with multiple workers
uvicorn user_service.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --loop uvloop \
  --http httptools
```

### Database Connection Pooling

Configure in SQLAlchemy:

```python
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)
```

## 🐳 Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements_api.txt .
RUN pip install --no-cache-dir -r requirements_api.txt

COPY . .
CMD ["uvicorn", "user_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build
docker build -t openproject-user-api .

# Run
docker run -p 8000:8000 openproject-user-api
```

## 🤝 Contributing to OpenProject Compatibility

To improve compatibility with OpenProject frontend:

1. **Study OpenProject API specs**: https://www.openproject.org/docs/api/
2. **Implement missing endpoints** as needed
3. **Match response formats** exactly
4. **Test with actual frontend** to ensure compatibility

## 📄 License

Based on OpenProject which is licensed under GPL-3.0.

## 🔗 Resources

- [OpenProject API Documentation](https://www.openproject.org/docs/api/)
- [OpenProject API v3 Endpoints](https://www.openproject.org/docs/api/endpoints/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

---

## Summary: Frontend Conversion Feasibility

**Short Answer**: You can use this FastAPI backend for user management endpoints, but a complete frontend conversion would require implementing all OpenProject features.

**Recommended Path**:
1. Use this backend as a **microservice** for user management
2. Keep the Rails backend for other OpenProject features
3. Use an API gateway or proxy to route requests appropriately
4. Gradually expand FastAPI implementation as needed

This approach gives you:
- ✅ Modern, fast API for user management
- ✅ Maintains existing OpenProject functionality
- ✅ Allows incremental migration
- ✅ Preserves the Angular frontend
