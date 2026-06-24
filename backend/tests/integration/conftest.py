"""Gate for integration tests that need real Postgres + ClickHouse.

These are skipped unless ``RUN_INTEGRATION=1`` so the normal backend job (and
local runs) stay self-contained. The CI ``smoke`` job sets the flag and provides
the service containers.
"""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("RUN_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(
        reason="integration test; set RUN_INTEGRATION=1 with Postgres + ClickHouse available"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
