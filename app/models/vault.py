"""Secrets vault model — stores encrypted key/value secrets."""

from __future__ import annotations

from datetime import UTC, datetime

from app.extensions import db


class VaultSecret(db.Model):
    __tablename__ = "vault_secrets"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=True)
    # encrypted ciphertext (base64-encoded Fernet token)
    ciphertext = db.Column(db.Text, nullable=False)
    # who can read: comma-separated usernames, or "*" for all admins
    allowed_users = db.Column(db.String(1024), nullable=False, default="*")
    created_by = db.Column(db.String(128), nullable=False, default="system")
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def to_dict(self, include_value: bool = False) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "allowed_users": self.allowed_users,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        return d
