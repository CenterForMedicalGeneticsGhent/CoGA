"""scrub_log control-character neutralization (CWE-117 log forging)."""
from __future__ import annotations

from backend.app.core.coga_logging import scrub_log


def test_scrub_log_neutralizes_crlf_forging() -> None:
    forged = "family-123\r\nERROR forged admin login by attacker"
    out = scrub_log(forged)
    assert "\n" not in out and "\r" not in out
    # content is preserved; only the line breaks that would forge a new record are gone
    assert out == "family-123  ERROR forged admin login by attacker"


def test_scrub_log_passes_clean_value_through() -> None:
    assert scrub_log("FAM0001") == "FAM0001"


def test_scrub_log_coerces_non_str() -> None:
    assert scrub_log(42) == "42"


def test_scrub_log_strips_tab_and_del() -> None:
    assert scrub_log("a\tb\x7fc") == "a b c"


def test_scrub_log_truncates_oversized_value() -> None:
    out = scrub_log("x" * 1000, max_len=100)
    assert len(out) == 100
    assert out.endswith("...")
