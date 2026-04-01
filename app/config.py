"""Application configuration — reads from environment variables.

Set DATABASE_URL, JWT_SECRET_KEY, LDAP_URL etc. in the container's ConfigMap/Secret.
"""

import os


class Config:
    """Base configuration — safe defaults for local development."""

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8080))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Database — defaults to local SQLite; override with DATABASE_URL=postgresql://... in K8s
    SQLALCHEMY_DATABASE_URI: str = os.getenv("DATABASE_URL", "sqlite:///conduit.db")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # Connection pool — only applied for server-based databases (PostgreSQL, Oracle).
    # SQLite uses StaticPool and rejects pool_size/max_overflow/pool_timeout.
    SQLALCHEMY_ENGINE_OPTIONS: dict = (
        {}
        if os.getenv("DATABASE_URL", "sqlite:///conduit.db").startswith("sqlite")
        else {
            "pool_size": int(os.getenv("DB_POOL_SIZE", 5)),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", 10)),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", 30)),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", 1800)),
            "pool_pre_ping": True,
        }
    )

    # JWT authentication
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_EXPIRY_HOURS: int = int(os.getenv("JWT_EXPIRY_HOURS", 8))

    # LDAP directory integration
    LDAP_URL: str = os.getenv("LDAP_URL", "ldaps://ldap.example.com")
    LDAP_BIND_DN: str = os.getenv("LDAP_BIND_DN", "")
    LDAP_BIND_PASSWORD: str = os.getenv("LDAP_BIND_PASSWORD", "")
    LDAP_BASE_DN: str = os.getenv("LDAP_BASE_DN", "dc=example,dc=com")
    LDAP_USER_SEARCH_BASE: str = os.getenv("LDAP_USER_SEARCH_BASE", "ou=People,dc=example,dc=com")
    LDAP_GROUP_SEARCH_BASE: str = os.getenv("LDAP_GROUP_SEARCH_BASE", "ou=Groups,dc=example,dc=com")

    # Redis — used for caching and rate limiting
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Audit PDF storage path inside the container
    AUDIT_STORAGE_PATH: str = os.getenv("AUDIT_STORAGE_PATH", "/tmp/audit-reports")

    # Groq API — required for the AI chat agent (free tier, Llama 3.3 70B)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")


class TestConfig(Config):
    """Test configuration — in-memory SQLite, deterministic secrets."""

    TESTING: bool = True
    DEBUG: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    JWT_SECRET_KEY: str = "test-secret"
