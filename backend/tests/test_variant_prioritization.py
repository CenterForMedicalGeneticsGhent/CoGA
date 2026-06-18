"""Tests for the Exomiser-style variant prioritization scoring math."""

from backend.app.services.variant_prioritization import (
    MODE_COMPOUND_HET,
    MODE_DE_NOVO,
    MODE_DOMINANT,
    combine,
    frequency_score,
    pathogenicity_score,
    score_variant,
    segregation_weight,
)
from backend.app.services.monarch_phenotype_score import phenomizer_score


def test_pathogenicity_clinvar_pathogenic_overrides() -> None:
    assert pathogenicity_score(
        impact="low", clinvar="Pathogenic", cadd_phred=0, revel=0,
        spliceai_max=0, lof=None,
    ) == 1.0


def test_pathogenicity_high_impact_lof() -> None:
    # LoF/HIGH predicted-deleterious, but capped below the ClinVar-reserved 1.0.
    assert pathogenicity_score(
        impact="HIGH", clinvar=None, cadd_phred=None, revel=None,
        spliceai_max=None, lof="HC",
    ) == 0.85


def test_pathogenicity_missense_takes_max_predictor() -> None:
    # MODERATE base 0.5 vs REVEL 0.8 -> 0.8
    score = pathogenicity_score(
        impact="MODERATE", clinvar=None, cadd_phred=20, revel=0.8,
        spliceai_max=0.1, lof=None,
    )
    assert abs(score - 0.8) < 1e-9


def test_alpha_missense_pathogenic_class_raises_missense_score() -> None:
    common = dict(
        impact="MODERATE", clinvar=None, cadd_phred=None, revel=None,
        spliceai_max=None, lof=None,
    )
    plain = pathogenicity_score(**common)
    flagged = pathogenicity_score(**common, alpha_missense_class="likely_pathogenic")
    assert flagged > plain
    assert flagged == 0.85


def test_alpha_missense_benign_class_caps_missense_score() -> None:
    # A MODERATE missense with a high CADD but AlphaMissense-benign is de-prioritized.
    score = pathogenicity_score(
        impact="MODERATE", clinvar=None, cadd_phred=30, revel=None,
        spliceai_max=None, lof=None, alpha_missense_class="likely_benign",
    )
    assert score <= 0.25


def test_alpha_missense_does_not_override_clinvar_pathogenic() -> None:
    assert pathogenicity_score(
        impact="MODERATE", clinvar="Pathogenic", cadd_phred=None, revel=None,
        spliceai_max=None, lof=None, alpha_missense_class="likely_benign",
    ) == 1.0


def test_numeric_alpha_missense_feeds_predictor_max() -> None:
    score = pathogenicity_score(
        impact="MODERATE", clinvar=None, cadd_phred=None, revel=0.2,
        spliceai_max=None, lof=None, alpha_missense_pathogenicity=0.88,
    )
    assert abs(score - 0.88) < 1e-9  # numeric AlphaMissense drives the predictor max


def test_gene_pli_raises_lof_confidence() -> None:
    base = pathogenicity_score(
        impact="HIGH", clinvar=None, cadd_phred=None, revel=None,
        spliceai_max=None, lof="HC",
    )
    constrained = pathogenicity_score(
        impact="HIGH", clinvar=None, cadd_phred=None, revel=None,
        spliceai_max=None, lof="HC", gene_pli=0.99,
    )
    assert constrained >= base
    assert constrained == 0.9


def test_out_of_range_gene_pli_is_ignored() -> None:
    # Malformed pLI (> 1) from bad source data must not trigger the constraint floor.
    base = pathogenicity_score(
        impact="HIGH", clinvar=None, cadd_phred=None, revel=None,
        spliceai_max=None, lof="HC",
    )
    with_garbage = pathogenicity_score(
        impact="HIGH", clinvar=None, cadd_phred=None, revel=None,
        spliceai_max=None, lof="HC", gene_pli=9.21,
    )
    assert with_garbage == base == 0.85


def test_missense_z_adds_prior_for_missense_in_constrained_gene() -> None:
    plain = pathogenicity_score(
        impact="MODERATE", clinvar=None, cadd_phred=None, revel=None,
        spliceai_max=None, lof=None,
    )
    constrained = pathogenicity_score(
        impact="MODERATE", clinvar=None, cadd_phred=None, revel=None,
        spliceai_max=None, lof=None, gene_missense_z=4.0,
    )
    assert constrained > plain


def test_frequency_score_is_monotonic_decreasing() -> None:
    assert frequency_score(gnomad_popmax_af=None, gnomad_af=None) == 1.0
    f_rare = frequency_score(gnomad_popmax_af=1e-5, gnomad_af=None)
    f_mid = frequency_score(gnomad_popmax_af=5e-4, gnomad_af=None)
    f_common = frequency_score(gnomad_popmax_af=0.1, gnomad_af=None)
    assert f_rare > f_mid > f_common
    assert f_common == 0.0


def test_segregation_weight_prefers_strong_modes() -> None:
    assert segregation_weight([MODE_DE_NOVO]) == 1.0
    assert segregation_weight([MODE_COMPOUND_HET]) == 1.0
    assert segregation_weight([MODE_DOMINANT]) == 0.85
    assert segregation_weight([]) == 0.6


def test_segregation_neutral_when_not_evaluated() -> None:
    # No affected individuals -> segregation can't be evaluated -> neutral, not a penalty.
    assert segregation_weight([], evaluated=False) == 1.0
    assert segregation_weight([], evaluated=True) == 0.6
    # A variant with no compatible mode is not penalised when segregation is unevaluable.
    unevaluated = score_variant(
        impact="MODERATE", clinvar=None, cadd_phred=None, revel=0.8, spliceai_max=None,
        lof=None, gnomad_popmax_af=0.0, gnomad_af=0.0, segregation_modes=[],
        phenotype_score=None, segregation_evaluated=False,
    )
    evaluated = score_variant(
        impact="MODERATE", clinvar=None, cadd_phred=None, revel=0.8, spliceai_max=None,
        lof=None, gnomad_popmax_af=0.0, gnomad_af=0.0, segregation_modes=[],
        phenotype_score=None, segregation_evaluated=True,
    )
    assert unevaluated.variant_score > evaluated.variant_score


def test_combine_phenotype_reorders_candidates() -> None:
    # Bounded in [0, 1] and monotonic in both axes.
    assert 0.0 <= combine(0.0, None) <= 1.0
    assert combine(1.0, 1.0) == 1.0
    # A phenotype match lifts the combined score.
    assert combine(0.5, 1.0) > combine(0.5, None)
    # Phenotype reorders: a strong phenotype match on a slightly weaker variant can beat
    # a top-scoring variant in a phenotype-irrelevant gene.
    assert combine(0.8, 0.9) > combine(1.0, None)


def test_score_variant_end_to_end_ranks_phenotype_match_higher() -> None:
    common = dict(
        impact="HIGH", clinvar=None, cadd_phred=30, revel=None, spliceai_max=None,
        lof="HC", gnomad_popmax_af=1e-6, gnomad_af=1e-6, segregation_modes=[MODE_DE_NOVO],
    )
    with_pheno = score_variant(**common, phenotype_score=0.9)
    without_pheno = score_variant(**common, phenotype_score=None)
    assert with_pheno.combined_score > without_pheno.combined_score
    # Variant score (pre-phenotype) is identical.
    assert with_pheno.variant_score == without_pheno.variant_score


def test_phenomizer_score_perfect_self_match_is_high() -> None:
    ic = {"HP:root": 0.1, "HP:spec": 5.0}
    ancestors = {"HP:spec": {"HP:spec", "HP:root"}, "HP:root": {"HP:root"}}
    score = phenomizer_score(
        ["HP:spec"], ["HP:spec"], ancestors=ancestors, ic=ic, max_ic=5.0
    )
    assert abs(score.score - 1.0) < 1e-9
    assert score.matched and score.matched[0]["hpo_id"] == "HP:spec"


def test_phenomizer_score_unrelated_terms_is_low() -> None:
    ic = {"HP:root": 0.1, "HP:a": 5.0, "HP:b": 5.0}
    ancestors = {
        "HP:a": {"HP:a", "HP:root"},
        "HP:b": {"HP:b", "HP:root"},
        "HP:root": {"HP:root"},
    }
    score = phenomizer_score(
        ["HP:a"], ["HP:b"], ancestors=ancestors, ic=ic, max_ic=5.0
    )
    # Only the low-IC root is shared.
    assert score.score < 0.1
