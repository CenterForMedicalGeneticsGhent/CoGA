from __future__ import annotations

from backend.app.services.clickhouse_family_variants import _annotation_matches_normal
from backend.app.services.family_variant_filters import SmallVariantQueryFilters


def _filters(**overrides) -> SmallVariantQueryFilters:
    base = dict(page=1, page_size=100, max_gnomad_af=0.01, max_gnomad_hom_count=10)
    base.update(overrides)
    return SmallVariantQueryFilters(**base)


def test_common_pathogenic_kept_when_rescue_enabled() -> None:
    annotation = {"gnomad_af": 0.2, "gnomad_hom_count": 5000, "clinvar": "Pathogenic"}
    assert _annotation_matches_normal(annotation, _filters(clinvar_overrides_frequency=True))


def test_common_likely_pathogenic_kept_when_rescue_enabled() -> None:
    annotation = {"gnomad_af": 0.2, "clinvar": "Likely_pathogenic"}
    assert _annotation_matches_normal(annotation, _filters(clinvar_overrides_frequency=True))


def test_common_pathogenic_filtered_without_rescue() -> None:
    annotation = {"gnomad_af": 0.2, "clinvar": "Pathogenic"}
    assert not _annotation_matches_normal(annotation, _filters(clinvar_overrides_frequency=False))


def test_rescue_does_not_keep_common_benign() -> None:
    annotation = {"gnomad_af": 0.2, "clinvar": "Benign"}
    assert not _annotation_matches_normal(annotation, _filters(clinvar_overrides_frequency=True))


def test_rescue_does_not_keep_common_variant_without_clinvar() -> None:
    annotation = {"gnomad_af": 0.2}
    assert not _annotation_matches_normal(annotation, _filters(clinvar_overrides_frequency=True))


def test_rare_pathogenic_passes_regardless() -> None:
    annotation = {"gnomad_af": 0.0001, "clinvar": "Pathogenic"}
    assert _annotation_matches_normal(annotation, _filters(clinvar_overrides_frequency=False))


def test_rescue_only_bypasses_frequency_not_hom_count_independently() -> None:
    # A P/LP variant that is common by hom_count is also rescued (rescue covers
    # the whole frequency/hom/hemi/AC block).
    annotation = {"gnomad_af": 0.0001, "gnomad_hom_count": 9000, "clinvar": "Pathogenic"}
    assert not _annotation_matches_normal(annotation, _filters(clinvar_overrides_frequency=False))
    assert _annotation_matches_normal(annotation, _filters(clinvar_overrides_frequency=True))
