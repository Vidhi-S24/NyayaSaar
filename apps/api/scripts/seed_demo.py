"""
NyayaSaar — development seed script.

Creates a demo user and clearly-labelled sample cases for local development.
Idempotent: re-running does not duplicate data.

Usage (from apps/api/):
    python -m scripts.seed_demo                       # uses DATABASE_URL / .env
    python -m scripts.seed_demo --email you@example.com --password secret123

Without DATABASE_URL the app falls back to a local SQLite file — convenient
for development, not for production.

The seeded cases are FICTIONAL SAMPLES for exercising the interface.
They are not real matters and contain no real personal or legal data.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid

# Parse CLI args BEFORE importing app modules so --database-url can be
# applied to the environment ahead of engine construction.
parser = argparse.ArgumentParser(description="Seed NyayaSaar demo data")
parser.add_argument("--email", default=os.environ.get("DEMO_USER_EMAIL", "demo@nyayasaar.example"))
parser.add_argument("--password", default=os.environ.get("DEMO_USER_PASSWORD", "demo-password-123"))
parser.add_argument("--full-name", default=os.environ.get("DEMO_USER_NAME", "Demo Advocate"))
parser.add_argument("--database-url", default=None, help="Override DATABASE_URL for this run")
args = parser.parse_args()

if args.database_url:
    os.environ["DATABASE_URL"] = args.database_url

from sqlalchemy import select, inspect  # noqa: E402

from app.db.base import Base, async_session_factory  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.models.case import Case  # noqa: E402
from app.services.auth import hash_password  # noqa: E402

DEMO_CASES = [
    {
        "title": "[DEMO] Sharma vs. Municipal Corporation — Land Acquisition Dispute",
        "case_number": "WP/4521/2024",
        "court": "High Court of Delhi",
        "jurisdiction": "India",
        "status": "active",
        "priority": "high",
        "summary": (
            "Sample case: challenge to land acquisition proceedings. Petitioner "
            "alleges procedural irregularities and inadequate compensation."
        ),
        "tags": ["Land Acquisition", "Constitutional", "Compensation"],
        "issues": [
            "Validity of the acquisition notification",
            "Adequacy of compensation offered",
            "Compliance with natural justice principles",
        ],
        "documents_count": 0,
    },
    {
        "title": "[DEMO] Patel Industries vs. State of Gujarat — Contract Breach",
        "case_number": "CS/892/2024",
        "court": "Commercial Court, Ahmedabad",
        "jurisdiction": "India",
        "status": "review",
        "priority": "medium",
        "summary": (
            "Sample case: alleged breach of a supply contract; respondent "
            "invokes force majeure clauses."
        ),
        "tags": ["Contract", "Commercial", "Force Majeure"],
        "issues": [
            "Interpretation of the force majeure clause",
            "Quantum of damages claimed",
        ],
        "documents_count": 0,
    },
    {
        "title": "[DEMO] Krishnamurthy Family Trust — Succession Dispute",
        "case_number": "TS/156/2024",
        "court": "City Civil Court, Bengaluru",
        "jurisdiction": "India",
        "status": "closed",
        "priority": "low",
        "summary": (
            "Sample case: succession dispute involving multiple claimants to a "
            "family trust and deed interpretation questions."
        ),
        "tags": ["Succession", "Trust"],
        "issues": ["Validity of trust deed amendments"],
        "documents_count": 0,
    },
]


async def ensure_schema() -> None:
    """Create tables if the target database is completely empty.

    Alembic migrations remain the canonical schema path for real deployments
    (PostgreSQL). This is a convenience so `python -m scripts.seed_demo` works
    on a fresh development database without a separate migration step.
    """
    engine = async_session_factory.kw["bind"]
    async with engine.connect() as conn:
        tables = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    if "users" not in tables:
        print("Empty database detected — creating schema via SQLAlchemy metadata.")
        print("(For production/PostgreSQL, prefer: alembic upgrade head)")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def seed() -> None:
    await ensure_schema()
    email = args.email.lower().strip()
    async with async_session_factory() as session:
        existing = await session.execute(select(User).where(User.email == email))
        user = existing.scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                hashed_password=hash_password(args.password),
                full_name=args.full_name,
            )
            session.add(user)
            await session.flush()
            print(f"Created demo user: {email}")
        else:
            print(f"Demo user already exists: {email}")

        created_count = 0
        for spec in DEMO_CASES:
            title = spec["title"]
            exists = await session.execute(
                select(Case).where(Case.owner_id == user.id, Case.title == title)
            )
            if exists.scalar_one_or_none():
                continue
            session.add(
                Case(
                    id=str(uuid.uuid4()),
                    owner_id=user.id,
                    title=title,
                    case_number=spec["case_number"],
                    court=spec["court"],
                    jurisdiction=spec["jurisdiction"],
                    status=spec["status"],
                    priority=spec["priority"],
                    summary=spec["summary"],
                    tags=spec["tags"],
                    issues=spec["issues"],
                    documents_count=spec["documents_count"],
                )
            )
            created_count += 1
        await session.commit()
        if created_count:
            print(f"Created {created_count} demo case(s).")
        else:
            print("Demo cases already present — nothing to do.")

    print("\nThese cases are fictional development samples, clearly prefixed [DEMO].")
    print("They are not real matters and contain no real legal data.")


if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception as exc:  # pragma: no cover — CLI helper
        print(f"Seed failed: {exc}", file=sys.stderr)
        print(
            "Hint: set DATABASE_URL (e.g. postgresql+asyncpg://nyayasaar:secret@localhost:5432/nyayasaar) "
            "or pass --database-url.",
            file=sys.stderr,
        )
        sys.exit(1)
