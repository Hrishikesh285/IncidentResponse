"""Seed MongoDB/local store and Hindsight/local memory with synthetic incidents.

Run after generating the seed data:
    python data/generate_incidents.py
    python scripts/seed_memory.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import seed


def main() -> None:
    """Load seed incidents into storage and retain each one in memory."""
    try:
        result = seed.seed_all(clear_first=True, retain_remote=True)
    except FileNotFoundError as exc:
        print(exc)
        print("Run: python data/generate_incidents.py first")
        sys.exit(1)

    print(
        f"\nDone. Seeded={result['seeded']} storage={result['storage']} "
        f"memory={result['memory_backend']} local={result['local_memories']} "
        f"remote_ok={result['remote_retained']} remote_fail={result['remote_failed']}"
    )


if __name__ == "__main__":
    main()
