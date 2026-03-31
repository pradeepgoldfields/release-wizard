"""Authentication endpoints — login, logout, current user.

Issues and verifies JWT tokens stored client-side in localStorage.
All tokens are signed with CONFIG.JWT_SECRET_KEY (HS256).

Token payload:
  sub   — user ID
  usr   — username
  per   — persona
  exp   — expiry (UTC epoch seconds)
  iat   — issued-at
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models.auth import User
from app.services.id_service import resource_id

log = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

# ── Public endpoints ──────────────────────────────────────────────────────────


@auth_bp.post("/api/v1/auth/login")
def login():
    """Exchange username+password for a JWT.

    Body: ``{"username": "...", "password": "..."}``
    Returns: ``{"token": "...", "user": {...}}``

    Authentication order:
      1. Local bcrypt password (if set on the user record)
      2. LDAP bind (if LDAP_URL is configured and local auth fails or has no password)
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = User.query.filter_by(username=username).first()

    # ── Local password auth ───────────────────────────────────────────────────
    if user and user.is_active and user.password_hash:
        if bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            user.last_login = datetime.now(UTC)
            db.session.commit()
            return jsonify({"token": _issue_token(user), "user": user.to_dict()})
        # Wrong local password — do NOT fall through to LDAP
        return jsonify({"error": "Invalid credentials"}), 401

    # ── LDAP auth ─────────────────────────────────────────────────────────────
    ldap_url = current_app.config.get("LDAP_URL", "")
    if ldap_url and ldap_url != "ldaps://ldap.example.com":
        ldap_user = _try_ldap_login(username, password)
        if ldap_user:
            ldap_user.last_login = datetime.now(UTC)
            db.session.commit()
            return jsonify({"token": _issue_token(ldap_user), "user": ldap_user.to_dict()})
        return jsonify({"error": "Invalid credentials"}), 401

    # No local user and LDAP not configured
    if not user or not user.is_active:
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify({"error": "Account has no local password — contact your administrator"}), 401


@auth_bp.post("/api/v1/auth/logout")
def logout():
    """Client-side logout — just acknowledge; client must discard the token."""
    return jsonify({"message": "Logged out"})


@auth_bp.get("/api/v1/auth/ldap/config")
def get_ldap_config():
    """Return current LDAP configuration (no secrets)."""
    cfg = current_app.config
    return jsonify(
        {
            "LDAP_URL": cfg.get("LDAP_URL", ""),
            "LDAP_BIND_DN": cfg.get("LDAP_BIND_DN", ""),
            "LDAP_BASE_DN": cfg.get("LDAP_BASE_DN", ""),
            "LDAP_USER_SEARCH_BASE": cfg.get("LDAP_USER_SEARCH_BASE", ""),
            "configured": bool(
                cfg.get("LDAP_URL") and cfg.get("LDAP_URL") != "ldaps://ldap.example.com"
            ),
        }
    )


@auth_bp.post("/api/v1/auth/ldap/test")
def test_ldap():
    """Test the LDAP connection using the current server config.

    Optional body: ``{"username": "...", "password": "..."}``
    If credentials are provided, also attempts a full user bind.
    Returns ``{"ok": true, "message": "..."}`` or ``{"ok": false, "error": "..."}``.
    """
    try:
        import ldap3  # noqa: PLC0415
    except ImportError:
        return jsonify({"ok": False, "error": "ldap3 not installed"}), 500

    cfg = current_app.config
    ldap_url = cfg.get("LDAP_URL", "")
    bind_dn = cfg.get("LDAP_BIND_DN", "")
    bind_pw = cfg.get("LDAP_BIND_PASSWORD", "")

    if not ldap_url or ldap_url == "ldaps://ldap.example.com":
        return jsonify({"ok": False, "error": "LDAP_URL is not configured"})

    try:
        server = ldap3.Server(ldap_url, get_info=ldap3.ALL, connect_timeout=5)
        with ldap3.Connection(
            server,
            user=bind_dn or None,
            password=bind_pw or None,
            auto_bind=ldap3.AUTO_BIND_NO_TLS,
        ) as conn:
            if not conn.bound:
                return jsonify({"ok": False, "error": "Service-account bind failed"})

        data = request.get_json(silent=True) or {}
        test_user = (data.get("username") or "").strip()
        test_pass = data.get("password") or ""

        if test_user and test_pass:
            result = _try_ldap_login(test_user, test_pass)
            if result:
                return jsonify(
                    {
                        "ok": True,
                        "message": f"Connected and authenticated '{test_user}' successfully",
                    }
                )
            return jsonify(
                {"ok": False, "error": f"Service bind OK but user '{test_user}' auth failed"}
            )

        return jsonify(
            {"ok": True, "message": f"Connected to {ldap_url} — service bind successful"}
        )

    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


@auth_bp.get("/api/v1/auth/me")
def me():
    """Return the currently authenticated user (requires valid JWT)."""
    user = _current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(user.to_dict())


# ── Middleware helper — called from before_request ────────────────────────────


def verify_token(token: str) -> User | None:
    """Decode a JWT and return the User, or None if invalid/expired."""
    try:
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        user = db.session.get(User, payload["sub"])
        if user and user.is_active:
            return user
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError):
        pass
    return None


def _current_user() -> User | None:
    """Extract and verify the Bearer token from the current request."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return verify_token(auth_header[7:])
    # Also check cookie for browser-side convenience
    token = request.cookies.get("cdt_token")
    if token:
        return verify_token(token)
    return None


def _issue_token(user: User) -> str:
    """Sign and return a JWT for the given user."""
    expiry_hours = current_app.config.get("JWT_EXPIRY_HOURS", 8)
    now = datetime.now(UTC)
    payload = {
        "sub": user.id,
        "usr": user.username,
        "per": user.persona,
        "iat": now,
        "exp": now + timedelta(hours=expiry_hours),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


# ── LDAP authentication ───────────────────────────────────────────────────────


def _try_ldap_login(username: str, password: str) -> User | None:
    """Attempt to authenticate via LDAP and return (or auto-create) the User.

    Performs a two-step bind:
      1. Bind with the service account (LDAP_BIND_DN / LDAP_BIND_PASSWORD)
         to search for the user's DN.
      2. Re-bind with the user's DN and the supplied password to verify.

    On success, creates or updates the local User record with attributes
    from the LDAP entry (email, display_name, ldap_dn).

    Returns None on any failure so the caller can return 401.
    """
    try:
        import ldap3  # noqa: PLC0415
    except ImportError:
        log.warning("ldap3 not installed — LDAP auth unavailable")
        return None

    cfg = current_app.config
    ldap_url = cfg.get("LDAP_URL", "")
    bind_dn = cfg.get("LDAP_BIND_DN", "")
    bind_pw = cfg.get("LDAP_BIND_PASSWORD", "")
    search_base = cfg.get("LDAP_USER_SEARCH_BASE", "")
    base_dn = cfg.get("LDAP_BASE_DN", "")

    if not search_base:
        search_base = base_dn

    try:
        server = ldap3.Server(ldap_url, get_info=ldap3.ALL, connect_timeout=5)

        # Step 1 — service-account bind to find the user
        with ldap3.Connection(
            server,
            user=bind_dn or None,
            password=bind_pw or None,
            auto_bind=ldap3.AUTO_BIND_NO_TLS,
        ) as conn:
            conn.search(
                search_base=search_base,
                search_filter=f"(|(uid={ldap3.utils.conv.escape_filter_chars(username)})"
                f"(sAMAccountName={ldap3.utils.conv.escape_filter_chars(username)}))",
                attributes=["dn", "mail", "cn", "displayName", "sAMAccountName", "uid"],
            )
            if not conn.entries:
                log.debug("LDAP: user '%s' not found in %s", username, search_base)
                return None
            entry = conn.entries[0]
            user_dn = entry.entry_dn
            email = str(entry["mail"].value or "") if "mail" in entry else ""
            display_name = (
                str(entry["displayName"].value or entry["cn"].value or username)
                if "displayName" in entry or "cn" in entry
                else username
            )

        # Step 2 — bind as the user to verify password
        with ldap3.Connection(
            server,
            user=user_dn,
            password=password,
            auto_bind=ldap3.AUTO_BIND_NO_TLS,
        ) as user_conn:
            if not user_conn.bound:
                log.debug("LDAP: password verification failed for '%s'", username)
                return None

        # Upsert local User record
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User.query.filter_by(ldap_dn=user_dn).first()
        if not user:
            user = User(
                id=resource_id("usr"),
                username=username,
                persona="ReadOnly",
                is_active=True,
            )
            db.session.add(user)
            log.info("LDAP: auto-created user '%s' (dn=%s)", username, user_dn)

        user.ldap_dn = user_dn
        if email:
            user.email = email
        if display_name:
            user.display_name = display_name
        db.session.flush()
        return user

    except Exception as exc:
        log.warning("LDAP auth error for '%s': %s", username, exc)
        return None


# ── Admin seed ────────────────────────────────────────────────────────────────


def ensure_admin_user(app) -> None:
    """Create the default admin user on first boot if no users exist."""
    with app.app_context():
        if User.query.count() > 0:
            return
        password = "admin"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(
            id=resource_id("usr"),
            username="admin",
            email="admin@conduit.local",
            display_name="Administrator",
            password_hash=hashed,
            persona="PlatformAdmin",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        app.logger.info("Created default admin user (password: admin)")
