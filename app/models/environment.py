"""Environment domain model — a top-level deployment target tier."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.enums import EnvironmentType
from app.extensions import db

# Association: a product can have many environments, an environment can belong to many products
product_environments = db.Table(
    "product_environments",
    db.Column("product_id", db.String(64), db.ForeignKey("products.id"), primary_key=True),
    db.Column("environment_id", db.String(64), db.ForeignKey("environments.id"), primary_key=True),
    db.Column("added_at", db.DateTime, default=lambda: datetime.now(UTC)),
)


class Environment(db.Model):
    """A deployment environment (dev, qa, staging, prod, or custom)."""

    __tablename__ = "environments"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    env_type = db.Column(db.String(32), default=EnvironmentType.CUSTOM)
    order = db.Column(db.Integer, default=0)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    products = db.relationship(
        "Product", secondary=product_environments, back_populates="environments"
    )

    def __repr__(self) -> str:
        return f"<Environment id={self.id!r} name={self.name!r} type={self.env_type!r}>"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "env_type": self.env_type,
            "order": self.order,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
