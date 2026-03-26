# SargamAI Backend

Production-ready FastAPI backend with PostgreSQL, SQLAlchemy ORM, and OAuth authentication.

## Features

- **User Authentication**
  - Email/Password signup and signin
  - OAuth 2.0 authentication with Google
  - OAuth 2.0 authentication with Facebook
  - JWT token-based authentication
  - Refresh token support

- **Database**
  - PostgreSQL with SQLAlchemy ORM
  - Alembic for database migrations
  - User and OAuth account models

- **API**
  - RESTful API with FastAPI
  - OpenAPI documentation (Swagger UI)
  - CORS enabled for frontend integration

## Prerequisites

- Python 3.10+
- PostgreSQL database

## Installation

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```

4. **Edit `.env` file** with your configuration:
   ```env
   # Database
   DATABASE_URL=postgresql://postgres:password@localhost:5432/sargamdb

   # JWT Settings
   SECRET_KEY=your-super-secret-key-change-in-production
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   REFRESH_TOKEN_EXPIRE_DAYS=7

   # OAuth - Google (optional)
   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret

   # OAuth - Facebook (optional)
   FACEBOOK_CLIENT_ID=your-facebook-app-id
   FACEBOOK_CLIENT_SECRET=your-facebook-app-secret

   # Frontend URL
   FRONTEND_URL=http://localhost:3000

   # Server
   DEBUG=True
   ```

5. **Set up PostgreSQL**
   - Create a PostgreSQL database named `sargamdb`
   - Update the `DATABASE_URL` in `.env` with your credentials

## Running the Application

### Development
```bash
uvicorn app.main:app --reload
```

The API will be available at:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Production
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/signup` | Register with email/password |
| POST | `/api/auth/signin` | Login with email/password |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/oauth/google` | Get Google OAuth URL |
| GET | `/api/auth/oauth/facebook` | Get Facebook OAuth URL |
| GET | `/api/auth/callback/google` | Google OAuth callback |
| GET | `/api/auth/callback/facebook` | Facebook OAuth callback |
| POST | `/api/auth/logout` | Logout |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/me/full` | Get current user profile with OAuth providers |
| GET | `/api/users/profile/{user_id}` | Get user public profile |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/` | Root endpoint |

## Database Migrations

### Create initial migration
```bash
alembic revision --autogenerate -m "Initial migration"
```

### Run migrations
```bash
alembic upgrade head
```

### Rollback migration
```bash
alembic downgrade -1
```

## OAuth Setup

### Google OAuth
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Go to APIs & Services > Credentials
4. Create OAuth 2.0 Client ID
5. Set redirect URI: `http://localhost:3000/api/auth/callback/google`
6. Copy Client ID and Client Secret to `.env`

### Facebook OAuth
1. Go to [Facebook Developers](https://developers.facebook.com/)
2. Create a new app
3. Add Facebook Login product
4. Set redirect URI: `http://localhost:3000/api/auth/callback/facebook`
5. Copy App ID and App Secret to `.env`

## Project Structure

```
sargambackend/
├── app/
│   ├── __init__.py
│   ├── config.py          # Configuration settings
│   ├── database.py        # Database connection
│   ├── models.py          # SQLAlchemy models
│   ├── main.py            # FastAPI application
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py        # Authentication routes
│   │   └── users.py       # User routes
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── auth.py        # Pydantic schemas
│   ├── services/
│   │   ├── __init__.py
│   │   └── oauth_service.py  # OAuth service
│   └── utils/
│       ├── __init__.py
│       ├── password.py    # Password hashing
│       └── token.py       # JWT utilities
├── alembic/
│   ├── env.py            # Alembic environment
│   └── script.py.mako    # Migration template
├── alembic.ini           # Alembic configuration
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variables example
└── README.md             # This file
```

## License

MIT License
