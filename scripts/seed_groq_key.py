"""Set the GROQ_API_KEY platform setting.

Run after any data seed or server restart:
    python scripts/seed_groq_key.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.setting import PlatformSetting  # noqa: E402

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
