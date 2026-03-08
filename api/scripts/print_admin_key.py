#!/usr/bin/env python3
"""Print the seeded admin user's email and API key.

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
        print(f"Email:   {admin.email}")
        print(f"API Key: {admin.api_key}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
