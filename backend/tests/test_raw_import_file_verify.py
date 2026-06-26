"""File-integrity (checksum) verification — REQ-DATA-004.

Verifies that `verify_raw_import_file` recomputes the stored file's SHA-256 and
correctly reports verified / mismatch / missing / unverifiable. A wrong or
corrupted source file must be detected, not silently trusted (risk H4).
"""

import asyncio
import hashlib
from pathlib import Path

from app.services import raw_import_files_pg as rif


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_verify_reports_verified_when_checksum_matches(tmp_path):
    f = tmp_path / "sample.vcf.gz"
    f.write_bytes(b"clinical genomic payload")
    expected = _sha256_of(f)

    result = asyncio.run(
        rif.verify_raw_import_file(
            {"id": "rec-1", "storage_path": str(f), "sha256": expected}
        )
    )

    assert result["status"] == "verified"
    assert result["computed_sha256"] == expected
    assert result["expected_sha256"] == expected


def test_verify_detects_a_corrupted_or_altered_file(tmp_path):
    f = tmp_path / "sample.vcf.gz"
    f.write_bytes(b"original payload")

    result = asyncio.run(
        rif.verify_raw_import_file(
            {"id": "rec-2", "storage_path": str(f), "sha256": "0" * 64}
        )
    )

    assert result["status"] == "mismatch"
    assert result["computed_sha256"] == _sha256_of(f)
    assert result["computed_sha256"] != result["expected_sha256"]


def test_verify_reports_missing_when_file_is_absent(tmp_path):
    result = asyncio.run(
        rif.verify_raw_import_file(
            {"id": "rec-3", "storage_path": str(tmp_path / "gone.vcf.gz"), "sha256": "abc"}
        )
    )

    assert result["status"] == "missing"
    assert result["computed_sha256"] is None


def test_verify_reports_unverifiable_without_a_recorded_checksum(tmp_path):
    f = tmp_path / "sample.vcf.gz"
    f.write_bytes(b"payload")

    result = asyncio.run(
        rif.verify_raw_import_file(
            {"id": "rec-4", "storage_path": str(f), "sha256": None}
        )
    )

    assert result["status"] == "unverifiable"
    assert result["computed_sha256"] == _sha256_of(f)
