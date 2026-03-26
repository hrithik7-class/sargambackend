"""
Redis cache service for caching and session management.
"""
import json
from typing import Optional, Any
from redis import Redis
from redis.connection import ConnectionPool
from src.config import settings


def _safe_redis_host() -> str:
    """Return Redis host for logging (masked for security)."""
    try:
        url = getattr(settings, "REDIS_URL", "") or ""
        if "localhost" in url:
            return "localhost"
        if "redis:" in url or "redis://" in url:
            return "redis (Docker)"
        return "configured"
    except Exception:
        return "unknown"


class RedisCache:
    """Redis cache service for the application."""
    
    _instance: Optional["RedisCache"] = None
    _pool: Optional[ConnectionPool] = None
    _client: Optional[Redis] = None
    
    def __new__(cls) -> "RedisCache":
        """Singleton pattern for Redis client."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self) -> None:
        """Initialize Redis connection pool."""
        self._pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
        )
        self._client = Redis(connection_pool=self._pool)
    
    @property
    def client(self) -> Redis:
        """Get Redis client."""
        return self._client
    
    def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None,
    ) -> bool:
        """
        Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds
            
        Returns:
            True if successful
        """
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            return self._client.set(key, value, ex=expire)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Redis set error: %s (REDIS_URL host: %s)", e, _safe_redis_host())
            return False
    
    def get(self, key: str, parse_json: bool = False) -> Optional[Any]:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
            parse_json: Whether to parse the value as JSON
            
        Returns:
            Cached value or None
        """
        try:
            value = self._client.get(key)
            if value is None:
                return None
            if parse_json:
                return json.loads(value)
            return value
        except Exception as e:
            print(f"Redis get error: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        try:
            return bool(self._client.delete(key))
        except Exception as e:
            print(f"Redis delete error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        try:
            return bool(self._client.exists(key))
        except Exception as e:
            print(f"Redis exists error: {e}")
            return False
    
    def set_session(
        self,
        session_id: str,
        user_data: dict,
        expire: int = 86400,
    ) -> bool:
        """
        Store session data in Redis.
        
        Args:
            session_id: Session ID
            user_data: User data to store
            expire: Expiration time in seconds (default 24 hours)
            
        Returns:
            True if successful
        """
        return self.set(f"session:{session_id}", user_data, expire)
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """
        Get session data from Redis.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session data or None
        """
        return self.get(f"session:{session_id}", parse_json=True)
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete session from Redis.

        Args:
            session_id: Session ID

        Returns:
            True if successful
        """
        return self.delete(f"session:{session_id}")

    # ── OTP for email verification ──────────────────────────────────────────────

    OTP_TTL_SECONDS: int = 900  # 15 minutes

    @staticmethod
    def _normalize_email(email: str) -> str:
        """Normalize email for consistent Redis keys (lowercase, stripped)."""
        return email.strip().lower()

    @staticmethod
    def _normalize_otp(otp: str) -> str:
        """Keep only digits from OTP (handles paste with spaces/dashes)."""
        return "".join(c for c in otp if c.isdigit())

    def set_otp(self, email: str, otp: str) -> bool:
        """Store OTP for email verification. TTL = 15 minutes.
        Stores under both normalized and raw email so verification finds it either way."""
        value = self._normalize_otp(otp)
        normalized = self._normalize_email(email)
        raw = email.strip()
        ok1 = self.set(f"verify_otp:{normalized}", value, expire=RedisCache.OTP_TTL_SECONDS)
        if raw != normalized:
            self.set(f"verify_otp:{raw}", value, expire=RedisCache.OTP_TTL_SECONDS)
        return ok1

    def get_otp(self, email: str) -> Optional[str]:
        """Get stored OTP for email. Returns None if missing or expired."""
        return self.get(f"verify_otp:{self._normalize_email(email)}")

    def verify_otp(self, email: str, otp: str) -> bool:
        """Verify OTP and delete it on success (one-time use)."""
        normalized_otp = self._normalize_otp(otp)
        if len(normalized_otp) != 6:
            return False

        normalized_email = self._normalize_email(email)
        raw_email = email.strip()
        keys_to_try = list(dict.fromkeys([normalized_email, raw_email]))  # unique, preserve order

        for key_email in keys_to_try:
            stored = self.get(f"verify_otp:{key_email}")
            if stored is not None and stored == normalized_otp:
                self.delete(f"verify_otp:{normalized_email}")
                self.delete(f"verify_otp:{raw_email}")
                return True
        return False

    def delete_otp(self, email: str) -> bool:
        """Remove OTP from cache."""
        return self.delete(f"verify_otp:{self._normalize_email(email)}")

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter in cache."""
        try:
            return self._client.incrby(key, amount)
        except Exception as e:
            print(f"Redis increment error: {e}")
            return None
    
    def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key."""
        try:
            return self._client.expire(key, seconds)
        except Exception as e:
            print(f"Redis expire error: {e}")
            return False
    
    def blacklist_token(self, jti: str, ttl_seconds: int) -> bool:
        """
        Add a JWT jti to the blacklist with a TTL matching the token expiry.

        Args:
            jti: JWT ID claim from the token
            ttl_seconds: How many seconds until the token would naturally expire

        Returns:
            True if successful
        """
        return self.set(f"blacklist:{jti}", "1", expire=ttl_seconds)

    def is_token_blacklisted(self, jti: str) -> bool:
        """
        Check whether a JWT jti has been blacklisted (i.e. the token was revoked).

        Args:
            jti: JWT ID claim from the token

        Returns:
            True if the token is blacklisted
        """
        return self.exists(f"blacklist:{jti}")

    # ── Login event log ───────────────────────────────────────────────────────

    def log_login_event(self, user_id: int, ip: str, user_agent: str) -> bool:
        """
        Prepend a login event to the user's history list.
        Keeps only the latest 10 events; TTL = 30 days.
        """
        try:
            key = f"login_events:{user_id}"
            event = json.dumps({
                "ip": ip,
                "user_agent": user_agent,
                "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            })
            self._client.lpush(key, event)
            self._client.ltrim(key, 0, 9)        # keep latest 10
            self._client.expire(key, 30 * 86400)  # 30 days TTL
            return True
        except Exception as e:
            print(f"Redis log_login_event error: {e}")
            return False

    def get_login_history(self, user_id: int) -> list:
        """Return the last 10 login events for a user (newest first)."""
        try:
            key = f"login_events:{user_id}"
            raw = self._client.lrange(key, 0, 9)
            return [json.loads(r) for r in raw]
        except Exception as e:
            print(f"Redis get_login_history error: {e}")
            return []

    # ── Single-device session (premium users) ─────────────────────────────────

    def set_active_session(self, user_id: int, jti: str, ttl: int) -> bool:
        """
        Store the active JTI for a premium user.
        key: active_session:{user_id}  value: jti  TTL: access token lifetime
        """
        return self.set(f"active_session:{user_id}", jti, expire=ttl)

    def get_active_session(self, user_id: int) -> Optional[str]:
        """Return the stored active JTI for a premium user, or None."""
        return self.get(f"active_session:{user_id}")

    def clear_active_session(self, user_id: int) -> bool:
        """Remove the active session record for a user."""
        return self.delete(f"active_session:{user_id}")

    def flush_all(self) -> bool:
        """Flush all keys from the database."""
        try:
            return self._client.flushdb()
        except Exception as e:
            print(f"Redis flush error: {e}")
            return False


# Create singleton instance
cache = RedisCache()
