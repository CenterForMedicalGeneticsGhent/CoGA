from __future__ import annotations

import pytest

from backend.app.services import family_package_import as fpi
from backend.app.services.family_package_import import (
    PackageManifest,
    _normalize_manifest_samples,
    scan_family_import_packages,
)


def test_scan_lists_packages_with_manifest_and_ped(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    nipt = tmp_path / "FAM_NIPT_DEMO"
    nipt.mkdir()
    (nipt / "manifest.yaml").write_text(
        "schema_version: 1\n"
        "family_id: FAM_NIPT_DEMO\n"
        "analysis_type: monogenic_nipt\n"
        "ped: nipt_trio.ped\n"
    )
    (nipt / "nipt_trio.ped").write_text("FAM_NIPT_DEMO\tF\t0\t0\t1\t1\n")

    ped_only = tmp_path / "PLAIN_FAM"
    ped_only.mkdir()
    (ped_only / "family.ped").write_text("PLAIN_FAM\tP\t0\t0\t1\t2\n")

    (tmp_path / "not-a-package").mkdir()  # no manifest, no ped -> skipped

    monkeypatch.setattr(fpi.settings, "family_import_roots", [str(tmp_path)])

    packages = {pkg["name"]: pkg for pkg in scan_family_import_packages()}

    assert set(packages) == {"FAM_NIPT_DEMO", "PLAIN_FAM"}

    nipt_pkg = packages["FAM_NIPT_DEMO"]
    assert nipt_pkg["family_id"] == "FAM_NIPT_DEMO"
    assert nipt_pkg["has_manifest"] is True
    assert nipt_pkg["has_ped"] is True
    assert nipt_pkg["analysis_type"] == "monogenic_nipt"
    assert nipt_pkg["folder_path"] == str(nipt.resolve())

    plain_pkg = packages["PLAIN_FAM"]
    assert plain_pkg["family_id"] == "PLAIN_FAM"  # falls back to the folder name
    assert plain_pkg["has_manifest"] is False
    assert plain_pkg["has_ped"] is True
    assert plain_pkg["analysis_type"] is None


def test_scan_returns_empty_without_roots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fpi.settings, "family_import_roots", [])
    assert scan_family_import_packages() == []


def test_manifest_accepts_analysis_type() -> None:
    manifest = PackageManifest(ped="trio.ped", analysis_type="monogenic_nipt")
    assert manifest.analysis_type == "monogenic_nipt"


def test_manifest_samples_carry_assay() -> None:
    # The per-sample assay is what _register_package_provenance promotes to the
    # top of sample.metadata so resolve_nipt_trio can find the cfDNA sample.
    samples = _normalize_manifest_samples({"CFDNA_NIPT": {"assay": "nipt_cfdna"}})
    assert samples["CFDNA_NIPT"]["assay"] == "nipt_cfdna"
