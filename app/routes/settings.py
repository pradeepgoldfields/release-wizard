"""Platform settings API — runtime-configurable key/value settings."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models.setting import PlatformSetting

settings_bp = Blueprint("settings", __name__, url_prefix="/api/v1/settings")

# Known settings with metadata
_KNOWN: dict[str, dict] = {
    "GROQ_API_KEY": {
        "description": "Groq API key for the AI chat assistant — free tier, runs Llama 3.3 70B (gsk_...)",
        "is_secret": True,
    },
    "TASK_RUNNER": {
        "description": "Task execution backend: 'subprocess' (default), 'docker', or 'podman'",
        "is_secret": False,
    },
    "TASK_RUNNER_IMAGE": {
        "description": "Container image used for docker/podman runner (default: python:3.12-slim)",
        "is_secret": False,
    },
}


@settings_bp.get("")
def list_settings():
    """Return all platform settings (secret values masked)."""
    rows = {s.key: s for s in PlatformSetting.query.all()}
    result = []
    for key, meta in _KNOWN.items():
        row = rows.get(key)
        result.append(
            {
                "key": key,
                "description": meta["description"],
                "is_secret": meta["is_secret"],
                "is_set": bool(row and row.value),
                "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
            }
        )
    return jsonify(result)


@settings_bp.put("/<key>")
def set_setting(key: str):
    """Set a platform setting value.

    Body: ``{ "value": "..." }``
    """
    if key not in _KNOWN:
        return jsonify({"error": f"Unknown setting key: {key}"}), 400

    data = request.get_json(silent=True) or {}
    value = data.get("value", "")

    row = PlatformSetting.query.get(key)
    if row:
        row.value = value
    else:
        row = PlatformSetting(
            key=key,
            value=value,
            is_secret=_KNOWN[key]["is_secret"],
        )
        db.session.add(row)
    db.session.commit()

    # Apply to running app config immediately
    current_app.config[key] = value

    return jsonify({"key": key, "is_set": bool(value)})


@settings_bp.post("/runner/test")
def test_runner():
    """Smoke-test the configured container runner.

    Runs ``echo conduit-ok`` in the configured image and returns success/failure.
    """
    import shutil
    import subprocess

    data = request.get_json(silent=True) or {}
    runtime = data.get("runtime") or "subprocess"
    image   = data.get("image") or "python:3.12-slim"

    if runtime == "subprocess":
        return jsonify({"ok": True, "runtime": "subprocess", "message": "subprocess runner is always available"})

    if not shutil.which(runtime):
        return jsonify({"ok": False, "runtime": runtime, "message": f"'{runtime}' not found on PATH"}), 200

    try:
        result = subprocess.run(
            [runtime, "run", "--rm", image, "echo", "conduit-ok"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60,
        )
        if "conduit-ok" in result.stdout:
            return jsonify({"ok": True, "runtime": runtime, "image": image,
                            "message": f"{runtime} is working — image pulled successfully"})
        return jsonify({"ok": False, "runtime": runtime, "image": image,
                        "message": result.stderr or result.stdout or "unexpected output"}), 200
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "runtime": runtime, "message": "Timed out pulling/running image (60s)"}), 200
    except Exception as exc:
        return jsonify({"ok": False, "runtime": runtime, "message": str(exc)}), 200


@settings_bp.delete("/<key>")
def clear_setting(key: str):
    """Clear a platform setting."""
    if key not in _KNOWN:
        return jsonify({"error": f"Unknown setting key: {key}"}), 400
    row = PlatformSetting.query.get(key)
    if row:
        row.value = None
        db.session.commit()
        current_app.config[key] = ""
    return "", 204
