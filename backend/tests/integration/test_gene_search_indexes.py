"""P2-3: the gene-search expression indexes actually serve their queries (real Postgres).

Each query that previously sequential-scanned the 120k+-row genes/gene_info tables is
EXPLAINed with ``enable_seqscan = off``: the planner is then forced onto the matching
index *iff* the index expression matches the query predicate (and uses the right operator
class — text_pattern_ops for the prefix LIKE, the default opclass for =/IN). A mismatch
would fall back to a (cost-penalised) Seq Scan and fail the assertion. EXPLAIN does not
execute, so no gene data / FK rows are needed.

Skipped unless ``RUN_INTEGRATION=1`` (see conftest.py); the CI ``smoke`` job sets it.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

# (index that must appear in the plan, query exercising its predicate with literal values)
_CASES = [
    (
        "idx_genes_assembly_symbol_prefix",  # autocomplete: assembly_id IN + upper(...) LIKE 'P%'
        "SELECT g.hgnc_symbol FROM genes g "
        "WHERE g.assembly_id IN ('00000000-0000-0000-0000-000000000000'::uuid) "
        "AND upper(g.hgnc_symbol) LIKE 'BR%'",
    ),
    (
        "idx_genes_upper_symbol",  # panel resolve: upper(hgnc_symbol) IN (...)
        "SELECT upper(g.hgnc_symbol) FROM genes g "
        "WHERE upper(g.hgnc_symbol) IN ('BRCA1', 'BRCA2')",
    ),
    (
        "idx_gene_info_lower_symbol",  # gene_info case-insensitive lookup
        "SELECT hgnc_symbol FROM gene_info WHERE lower(hgnc_symbol) = lower('BRCA1')",
    ),
]

# Candidate resolve: the three-branch OR must use all three lower() indexes (BitmapOr).
_CANDIDATE_SQL = (
    "SELECT g.hgnc_symbol FROM genes g "
    "WHERE lower(g.hgnc_symbol) IN ('brca1') "
    "OR lower(g.gene_id) IN ('ensg00000012048') "
    "OR lower(COALESCE(g.extra->>'transcript_id', '')) IN ('nm_007294')"
)
_CANDIDATE_INDEXES = (
    "idx_genes_lower_symbol",
    "idx_genes_lower_gene_id",
    "idx_genes_lower_transcript_id",
)


def test_gene_search_indexes_are_used_by_their_queries() -> None:
    from backend.app.core.postgres import (
        close_postgres_engine,
        get_postgres_sessionmaker,
        init_postgres_schema,
    )

    async def _plan(sm, sql: str) -> str:
        async with sm() as s:
            await s.execute(text("SET LOCAL enable_seqscan = off"))
            rows = (await s.execute(text("EXPLAIN " + sql))).all()
            return "\n".join(r[0] for r in rows)

    async def _run() -> None:
        try:
            await init_postgres_schema()
            sm = get_postgres_sessionmaker()
            for index, sql in _CASES:
                plan = await _plan(sm, sql)
                assert index in plan, f"{index} not used:\n{plan}"
            plan = await _plan(sm, _CANDIDATE_SQL)
            for index in _CANDIDATE_INDEXES:
                assert index in plan, f"{index} not used in candidate OR:\n{plan}"
        finally:
            await close_postgres_engine()

    asyncio.run(_run())
