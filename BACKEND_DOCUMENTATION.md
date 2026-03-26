# SargamAI Backend Documentation

Backend API for SargamAI — AI-powered music lyrics and audio generation. Built with **FastAPI**.

---

## Table of Contents

1. [FastAPI Framework Overview](#fastapi-framework-overview)
2. [Project Structure](#project-structure)
3. [Running the Backend](#running-the-backend)
4. [Running in Docker](#running-in-docker)
5. [Environment Variables](#environment-variables)
6. [API Endpoints](#api-endpoints)

---

## FastAPI Framework Overview

**FastAPI** is a modern, high-performance web framework for building APIs with Python 3.8+.

### Why FastAPI?

- **Automatic API docs**: Interactive Swagger UI at `/docs` and ReDoc at `/redoc`
- **Type hints**: Request/response validation via Pydantic
- **Async support**: Native `async`/`await` for non-blocking I/O
- **Standards**: OpenAPI (Swagger) and JSON Schema

### Key Concepts Used in This Project

| Concept | Usage |
|--------|-------|
| **Routers** | API routes grouped by domain (auth, tracks, generate, etc.) |
| **Dependencies** | `get_db()`, `get_current_user()` injected into route handlers |
| **Pydantic** | Request/response schemas in `src/schemas/` |
| **Lifespan** | Startup/shutdown logic (DB init, media dir) in `main.py` |
| **Middleware** | CORS, security headers, rate limiting (SlowAPI) |

---

## Project Structure

```
sargambackend/
├── src/
│   ├── main.py              # FastAPI app entry, routers, middleware
│   ├── config.py            # Pydantic Settings (env vars)
│   ├── database.py          # SQLAlchemy engine, session, get_db
│   ├── cache.py             # Redis cache utilities
│   ├── limiter.py           # Rate limiting (SlowAPI)
│   │
│   ├── models/              # SQLAlchemy ORM models
│   │   └── __init__.py      # User, OAuthAccount, Track, Subscription
│   │
│   ├── schemas/             # Pydantic request/response models
│   │   └── __init__.py      # SignupRequest, TokenResponse, TrackResponse, etc.
│   │
│   ├── routes/              # API route modules (FastAPI routers, all under /api)
│   │   ├── __init__.py      # Exports all routers
│   │   ├── auth.py          # /api/auth signup, signin, OAuth, logout
│   │   ├── users.py         # /api/users/me/full, profile
│   │   ├── generate.py      # /api/generate lyrics, audio, copyright-check
│   │   ├── tracks.py        # /api/tracks CRUD, publish, unpublish
│   │   ├── analytics.py     # /api/analytics
│   │   └── payments.py      # /api/payments checkout, webhooks, subscription
│   │
│   ├── controllers/         # Business logic called by routes
│   │   ├── auth_controller.py
│   │   ├── user_controller.py
│   │   ├── track_controller.py
│   │   └── generate_controller.py
│   │
│   ├── services/            # External APIs, AI, payments
│   │   ├── auth_service.py      # JWT, password hashing
│   │   ├── oauth_service.py    # Google, Facebook OAuth
│   │   ├── lyrics_service.py    # Groq API (AI lyrics)
│   │   ├── music_service.py     # Replicate (AI music synthesis)
│   │   ├── copyright_service.py # Genius API (similarity check)
│   │   ├── track_service.py     # Track CRUD, file handling
│   │   └── payment_service.py   # Lemon Squeezy, Razorpay
│   │
│   └── utils/               # Helpers
│       ├── token.py         # JWT encode/decode
│       └── password.py      # Hash/verify passwords
│
├── alembic/                 # Database migrations
│   ├── versions/            # 001_initial_schema, 002_tracks, 003_published_at,
│   │                        # 004_user_premium, 005_subscriptions
│   └── env.py               # Alembic environment config
│
├── media/                   # Generated audio files (created at runtime)
│   └── tracks/
│ 
├── requirements.txt        # Python dependencies
├── .env.example             # Template for environment variables
├── Dockerfile              # Backend container image
├── docker-compose.yml      # Full stack (Postgres, Redis, 3× API, Nginx)
├── nginx.conf              # Nginx reverse proxy + load balancer config
└── alembic.ini             # Alembic configuration
```

### Folder Responsibilities

| Folder | Purpose |
|--------|---------|
| `src/` | Application source code |
| `src/routes/` | HTTP endpoints; thin layer that delegates to controllers |
| `src/controllers/` | Orchestrates services, handles request/response flow |
| `src/services/` | External APIs (Groq, Replicate, Genius), payments, auth logic |
| `src/models/` | SQLAlchemy ORM models (database tables) |
| `src/schemas/` | Pydantic models for validation and serialization |
| `src/utils/` | Shared utilities (JWT, password hashing) |
| `alembic/` | Database schema migrations (version control for DB) |
| `media/` | Static files (generated audio) served at `/media` |

---

## Running the Backend

### Prerequisites

- Python 3.11+
- PostgreSQL 16
- Redis 7

### 1. Create virtual environment

```bash
cd sargambackend
python -m venv venv
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment variables

Copy the example file and fill in required values:

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

- `SECRET_KEY` — generate with: `python -c "import secrets; print(secrets.token_hex(32))"`
- `DATABASE_URL` — e.g. `postgresql://postgres:postgres@localhost:5432/sargamdb`
- `REDIS_URL` — e.g. `redis://localhost:6379/0`

### 4. Database setup

Ensure PostgreSQL is running, then run migrations:

```bash
alembic upgrade head
```

### 5. Start the server

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Or using the built-in runner:

```bash
python src/main.py
```

- **API base URL:** http://localhost:8000  
- **Swagger docs:** http://localhost:8000/docs  
- **ReDoc:** http://localhost:8000/redoc  
- **Health check:** http://localhost:8000/health  

---

## Running in Docker

Docker Compose runs the full stack: PostgreSQL, Redis, **three API instances**, and **Nginx** as reverse proxy with load balancing.

### Architecture: Nginx + Load Balancing

```
                    ┌─────────────┐
   Client ─────────►│   Nginx     │  (port 80)
                    │  (reverse   │
                    │   proxy)    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │  api1   │  │  api2   │  │  api3   │  (port 8000 each)
        │ :8000   │  │ :8000   │  │ :8000   │
        └────┬────┘  └────┬────┘  └────┬────┘
             │            │            │
             └────────────┼────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        ┌──────────┐            ┌──────────┐
        │ Postgres │            │  Redis   │
        └──────────┘            └──────────┘
```

- **All requests** go to Nginx first (port 80).
- Nginx distributes traffic across `api1`, `api2`, `api3` using **least_conn** (prefer server with fewest active connections).
- API instances share a `media_tracks` volume for generated audio files.

### Prerequisites

- Docker and Docker Compose installed

### 1. Build and start services

From the `sargambackend` directory:

```bash
docker-compose up -d --build
```

This starts:

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| PostgreSQL | sargam-postgres | 5432 | Database |
| Redis | sargam-redis | 6379 | Cache and sessions |
| API (x3) | sargam-api-1, 2, 3 | 8000 (api1 exposed for dev) | FastAPI backend instances |
| Nginx | sargam-nginx | **80**, 443 | Reverse proxy + load balancer |

**API base URL (via Nginx):** http://localhost  
**Swagger docs:** http://localhost/docs  
**Health check:** http://localhost/health  

### 2. Run database migrations

Run migrations on any API instance (e.g. api1):

```bash
docker-compose exec api1 alembic upgrade head
```

### 3. Environment variables for Docker

Create a `.env` file in `sargambackend/` (or pass env vars). The API services use:

- `DATABASE_URL=postgresql://postgres:postgres@postgres:5432/sargamdb` (host `postgres` = service name)
- `REDIS_URL=redis://redis:6379/0` (host `redis` = service name)
- `SECRET_KEY` — set via `.env` or `SECRET_KEY` in `docker-compose.yml`
- `FRONTEND_URL` — use `http://localhost:3000` for local frontend (or your deployed URL)
- Optional: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, etc.

### 4. View logs

```bash
docker-compose logs -f nginx    # Nginx access/error logs
docker-compose logs -f api1     # API instance 1
docker-compose logs -f api2 api3  # Multiple services
```

### 5. Stop services

```bash
docker-compose down
```

### 6. Run without Nginx (single API, direct port 8000)

To run a single API instance without Nginx (e.g. for local development):

```bash
docker-compose up -d postgres redis api1
```

Then access the API at http://localhost:8000 (api1 exposes port 8000 by default).

### 7. Run only database services (API locally)

To run Postgres and Redis in Docker but the API locally:

```bash
docker-compose up -d postgres redis
```

Then run `uvicorn src.main:app --reload` locally. Use `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sargamdb` and `REDIS_URL=redis://localhost:6379/0`.

### Nginx configuration (`nginx.conf`)

- **Upstream:** `api1:8000`, `api2:8000`, `api3:8000` with `least_conn` load balancing
- **Health:** `max_fails=3`, `fail_timeout=30s` for backend failure handling
- **Nginx health:** `GET /nginx-health` returns 200 OK (for load balancer probes)
- **Headers:** `X-Forwarded-For`, `X-Real-IP`, `X-Forwarded-Proto` passed to the API
- **WebSocket:** `/ws` location for future WebSocket support

### Dockerfile notes

- Base image: `python:3.11-slim`
- System deps: `gcc`, `curl` (for health check), `postgresql-client`
- Non-root user `appuser` for security
- Health check: `GET /health` every 30s via curl
- Default command: `uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4`

### Troubleshooting Docker

- **Nginx fails to start:** Ensure `nginx.conf` exists in `sargambackend/`.
- **API can't connect to Postgres/Redis:** Use service names (`postgres`, `redis`) as hosts, not `localhost`, when running inside Docker.
- **502 Bad Gateway:** Ensure all three API containers (api1, api2, api3) are running: `docker-compose ps`.

---

## Environment Variables

| Variable | Required | Default | Description |
|---------|----------|---------|-------------|
| `SECRET_KEY` | Yes | — | JWT signing key (use `secrets.token_hex(32)`) |
| `DATABASE_URL` | No | `postgresql://postgres:postgres@localhost:5432/sargamdb` | PostgreSQL connection string |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection string |
| `FRONTEND_URL` | No | `http://localhost:3000` | Frontend origin (CORS, OAuth redirects) |
| `DEBUG` | No | `false` | Enable debug logging and reload |
| `GROQ_API_KEY` | For lyrics | — | Groq API key (lyrics generation) |
| `REPLICATE_API_TOKEN` | For audio | — | Replicate token (music synthesis) |
| `GENIUS_ACCESS_TOKEN` | For copyright | — | Genius API (similarity check) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | For OAuth | — | Google OAuth |
| `LEMON_SQUEEZY_*` | For payments | — | Lemon Squeezy config |
| `RAZORPAY_*` | For payments | — | Razorpay config |

See `.env.example` for the full list.

---

## API Endpoints

All API routes use the `/api` prefix unless noted.

| Path | Method | Description |
|------|--------|-------------|
| `/` | GET | Welcome message and links |
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI |
| `/redoc` | GET | ReDoc |
| `/api/auth/signup` | POST | Register user |
| `/api/auth/signin` | POST | Login, get tokens |
| `/api/auth/refresh` | POST | Refresh access token |
| `/api/auth/me` | GET | Current user (from token) |
| `/api/auth/oauth/google` | GET | Google OAuth URL |
| `/api/auth/oauth/facebook` | GET | Facebook OAuth URL |
| `/api/auth/callback/google` | GET | Google OAuth callback |
| `/api/auth/callback/facebook` | GET | Facebook OAuth callback |
| `/api/auth/logout` | POST | Logout |
| `/api/auth/login-history` | GET | Login history |
| `/api/users/me/full` | GET | Current user with OAuth providers |
| `/api/users/profile/{user_id}` | GET | User profile by ID |
| `/api/generate/lyrics` | POST | Generate lyrics (AI) |
| `/api/generate/audio` | POST | Generate audio track (async) |
| `/api/generate/copyright-check` | POST | Check lyrics similarity |
| `/api/tracks` | GET | List user tracks |
| `/api/tracks/{id}` | GET | Get track |
| `/api/tracks/{id}` | DELETE | Delete track |
| `/api/tracks/{id}/publish` | POST | Publish track |
| `/api/tracks/{id}/unpublish` | POST | Unpublish track |
| `/api/analytics` | GET | Analytics data |
| `/api/payments/checkout/lemonsqueezy` | POST | Create Lemon Squeezy checkout |
| `/api/payments/checkout/razorpay` | POST | Create Razorpay order |
| `/api/payments/webhook/lemonsqueezy` | POST | Lemon Squeezy webhook |
| `/api/payments/webhook/razorpay` | POST | Razorpay webhook |
| `/api/payments/subscription` | GET | Current subscription |
| `/media/*` | GET | Static audio files |

All authenticated routes require `Authorization: Bearer <access_token>`.
