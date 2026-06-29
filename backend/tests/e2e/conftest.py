"""Gate for end-to-end tests that need real Postgres + ClickHouse.

A sibling of ``backend/tests/integration``; pytest collection hooks only apply to
their own directory subtree, so this gate must be duplicated here (it is NOT
inherited from ``integration/conftest.py``). E2E tests are skipped unless
``RUN_INTEGRATION=1`` so the normal backend job (and local runs) stay
self-contained. The CI ``e2e`` job sets the flag and provides the service
containers.
"""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("RUN_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(
        reason="e2e test; set RUN_INTEGRATION=1 with Postgres + ClickHouse available"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
