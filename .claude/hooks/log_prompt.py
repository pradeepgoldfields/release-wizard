"""
log_prompt.py — UserPromptSubmit hook for Conduit / Claude Code

Appends every user prompt to docs/prompt_log.md with a timestamp.
Invoked automatically by Claude Code before each prompt is processed.

Input (stdin): JSON with shape { "prompt": "...", ... }
"""

import json
import sys
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parents[2] / "docs" / "prompt_log.md"


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    prompt = data.get("prompt", "").strip()
    if not prompt:
        sys.exit(0)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write header on first use
    if not LOG_FILE.exists():
        LOG_FILE.write_text(
            "# Prompt Log\n\nAll prompts sent to Claude Code in this project.\n\n",
            encoding="utf-8",
        )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"## {timestamp}\n\n{prompt}\n\n---\n\n"

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry)


if __name__ == "__main__":
    main()
