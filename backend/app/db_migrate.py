"""Out-of-band Postgres schema migration + admin bootstrap.

This is the **owner-privileged** half of the DB privilege separation (P1-3 / P1-4). Schema
DDL — ``CREATE``/``ALTER TABLE``, trigger management, ``GRANT`` — must run as the table
**owner**; the restricted runtime role ``coga_app`` deliberately cannot. Keeping the
migration out of the API's request-serving process lets the app boot as ``coga_app``
(``POSTGRES_RUN_SCHEMA_MIGRATIONS_ON_STARTUP=false``) without crash-looping on DDL it is not
allowed to run — the coordinated flip described in ``docs/db-runtime-role-runbook.md``.

Run it as a deploy step, before starting the app, using the **owner** DSN::

    python -m backend.app.db_migrate

When ``POSTGRES_RUN_SCHEMA_MIGRATIONS_ON_STARTUP`` is left at its default (``true``) the app
still self-migrates on startup as the owner — the current single-DSN deployment — and this
module is simply unused. Both paths call the same ``init_postgres_schema`` /
``init_postgres_admin_user`` helpers, so there is one source of truth for the schema apply.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import text

from .core.config import settings
from .core.postgres import (
    close_postgres_engine,
    get_postgres_engine,
    init_postgres_schema,
    wait_for_postgres,
)
from .dependencies import get_password_hash


async def init_postgres_admin_user() -> None:
    """Ensure a metadata admin user exists in Postgres.

    Idempotent: returns early if the admin username is already present. Safe to run either
    as the owner (migration path) or as ``coga_app`` (which retains ``INSERT`` on ``users``).
    """

    engine = get_postgres_engine()
    async with engine.begin() as conn:
        existing = await conn.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": settings.admin_username},
        )
        if existing.scalar_one_or_none() is not None:
            return

        await conn.execute(
            text(
                """
                INSERT INTO users (
                    username,
                    hashed_password,
                    role,
                    email,
                    metadata,
                    created_at
                )
                VALUES (
                    :username,
                    :hashed_password,
                    'admin',
                    :email,
                    '{}'::jsonb,
                    :created_at
                )
                """
            ),
            {
                "username": settings.admin_username,
                "hashed_password": get_password_hash(settings.admin_password),
                "email": settings.admin_email,
                "created_at": datetime.now(timezone.utc),
            },
        )


async def run_schema_migrations() -> None:
    """Apply the Postgres schema and seed the admin user, then release the engine.

    This is the owner-privileged migration step invoked out-of-band by the deploy pipeline.
    ClickHouse schema init is intentionally left to app startup: ClickHouse connects with its
    own admin credentials (there is no ``coga_app`` equivalent there), so it is not part of
    the Postgres privilege-separation flip.
    """

    try:
        await wait_for_postgres()
        await init_postgres_schema()
        await init_postgres_admin_user()
    finally:
        await close_postgres_engine()


def main() -> None:
    asyncio.run(run_schema_migrations())


if __name__ == "__main__":
    main()
