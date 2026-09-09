"""
Main FastAPI application.
"""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.config import settings
from src.database import init_db
from src.limiter import limiter
from src.routes import auth_router, users_router, generate_router, tracks_router, analytics_router, payments_router, demo_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting up SargamAI backend...")
    try:
        init_db()
        logger.info("Database tables initialised")
    except Exception as e:
        logger.warning("Database init failed (will retry on first request): %s", e)
    try:
        from src.cache import cache
        cache.client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.error("Redis connection failed - OTP/sessions will not work: %s", e)
    try:
        os.makedirs(settings.MEDIA_DIR, exist_ok=True)
        logger.info("Media directory ready: %s", settings.MEDIA_DIR)
    except Exception as e:
        logger.warning("Media dir creation failed: %s", e)
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="SargamAI Backend API",
    description="Backend API for SargamAI — AI-powered music lyrics and audio generation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Attach limiter to app state so route decorators can find it
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # Only send HSTS in production (HTTPS)
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["X-Total-Count"],
)

# ── Static media (audio files) ────────────────────────────────────────────────
_media_dir = os.path.join(os.getcwd(), "media")
os.makedirs(settings.MEDIA_DIR, exist_ok=True)
if os.path.isdir(_media_dir):
    app.mount("/media", StaticFiles(directory=_media_dir), name="media")
else:
    logger.warning("Media dir %s missing; /media will not serve files", _media_dir)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(generate_router)
app.include_router(tracks_router)
app.include_router(analytics_router)
app.include_router(payments_router)
app.include_router(demo_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "SargamAI Backend API is running"}


@app.get("/")
async def root():
    return {
        "message": "Welcome to SargamAI Backend API",
        "docs": "/docs",
        "health": "/health",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
