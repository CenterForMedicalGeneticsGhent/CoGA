from __future__ import annotations

import pytest

from backend.app.core.clickhouse import clickhouse_dataset_key
from backend.app.services import clickhouse_family_variants as family
from backend.app.services import clickhouse_interval_tracks as interval
from backend.app.services import clickhouse_small_variants as small
from backend.app.services import clickhouse_variant_storage as storage
from backend.app.services import variant_explorer_service as explorer


def test_dataset_key_is_identity_for_existing_names() -> None:
    # Existing tables are named by these — the key MUST be identity or current
    # data becomes unaddressable.
    assert clickhouse_dataset_key("GRCh38") == "GRCh38"
    assert clickhouse_dataset_key("GRCm39") == "GRCm39"
    assert clickhouse_dataset_key("T2T_CHM13v2.0") == "T2T_CHM13v2.0"


def test_dataset_key_normalizes_disallowed_characters() -> None:
    assert clickhouse_dataset_key("T2T CHM13v2.0") == "T2T_CHM13v2.0"
    assert clickhouse_dataset_key("  spaced  name  ") == "spaced__name"
    # Path separators, backticks and semicolons can't survive — injection-safe.
    assert clickhouse_dataset_key("a/b`c;d") == "a_b_c_d"


def test_dataset_key_rejects_empty() -> None:
    with pytest.raises(ValueError):
        clickhouse_dataset_key("   ")


def test_all_modules_agree_on_the_table_prefix() -> None:
    # Ingestion (storage) and every read path derive the dataset key from the
    # SAME function, so a messy assembly name maps to one prefix everywhere —
    # otherwise variants written for T2T would be invisible to queries.
    name = "T2T CHM13v2.0"
    key = "T2T_CHM13v2.0"

    snv_names = {
        storage._small_table_name(name, "entries"),
        explorer._small_table_name(name, "entries"),
        small._table_name(name, "entries"),
        family._small_table_name(name, "entries"),
    }
    assert snv_names == {f"coga.`{key}/SNV_INDEL/entries`"}
    assert interval._interval_table_name(name) == f"coga.`{key}/INTERVAL/entries`"
    assert storage._structural_table_name(name, "entries") == f"coga.`{key}/SV/entries`"
