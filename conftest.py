import os
from pathlib import Path
import sys

import pytest

os.environ.setdefault("APP_ENV", "test")

ROOT_DIR = Path(__file__).resolve().parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture(autouse=True)
def _reset_process_memoization_caches():
    """Reset per-process schema/probe memoization caches between tests so their
    module-level state does not leak. These caches make DDL/probes run once per
    process in production, but several tests assert the first-call behaviour."""
    from backend.app.services import clickhouse_interval_tracks, hpo_service

    hpo_service._pg_tables_confirmed_available.clear()
    clickhouse_interval_tracks._ensured_interval_table_assemblies.clear()
    yield
