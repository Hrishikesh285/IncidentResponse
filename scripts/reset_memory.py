"""Reset script — clears all incidents from MongoDB and all memories from Hindsight.

Run: python scripts/reset_memory.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import db, memory


def main() -> None:
    """Wipe MongoDB incidents collection and Hindsight bank."""
    deleted = db.clear_incidents()
    print(f"MongoDB: deleted {deleted} incidents")

    try:
        memory.reset_bank()
        print("Hindsight: memory bank cleared successfully")
    except Exception as exc:
        print(f"Hindsight reset failed: {exc}")
        sys.exit(1)

    print("Reset complete.")


if __name__ == "__main__":
    main()
