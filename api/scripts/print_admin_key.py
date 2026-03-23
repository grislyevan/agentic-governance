#!/usr/bin/env python3
"""Show the seeded admin user's info.

API keys are hashed at rest and only displayed once at creation time
(in the seed log or registration response). This script cannot recover
the raw key; it shows the prefix so you can confirm which key is active.

To reset, delete the user row and restart the API to re-seed.

Usage (from the api/ directory):
    python scripts/print_admin_key.py

Requires DATABASE_URL to be set (or an .env file in the working directory).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import SessionLocal
from models.user import User


def main() -> None:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").order_by(User.created_at).first()
        if admin is None:
            print("No admin user found. Has the API been started at least once?")
            sys.exit(1)
        print(f"Email:        {admin.email}")
        print(f"Key prefix:   {admin.api_key_prefix or '(none)'}")
        print(f"Key hash:     {admin.api_key_hash[:16]}..." if admin.api_key_hash else "Key hash:     (none)")
        print()
        print("The raw API key was displayed once at seed time in the server log.")
        print("If you lost it, delete the admin row and restart the API to re-seed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
