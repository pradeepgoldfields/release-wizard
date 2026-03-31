"""Set the GROQ_API_KEY platform setting.

Run after any data seed or server restart:
    python scripts/seed_groq_key.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.config import Config
from app.extensions import db
from app.models.setting import PlatformSetting

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")


def main() -> None:
    app = create_app(Config)
    with app.app_context():
        row = db.session.get(PlatformSetting, "GROQ_API_KEY")
        if row:
            row.value = GROQ_API_KEY
        else:
            db.session.add(PlatformSetting(key="GROQ_API_KEY", value=GROQ_API_KEY, is_secret=True))
        db.session.commit()
        # Also inject into running app config so it takes effect immediately
        app.config["GROQ_API_KEY"] = GROQ_API_KEY
        print("GROQ_API_KEY set successfully.")


if __name__ == "__main__":
    main()
