"""Exomiser-style small-variant prioritization scoring.

Pure scoring math that combines a variant's predicted deleteriousness, rarity, and
segregation evidence with the gene's phenotype-match score into a single priority
score. The phenotype score comes from monarch_phenotype_score; segregation modes are
computed by the ClickHouse query layer using the existing pedigree helpers.

The score is for *ranking within a family*, not a calibrated probability. See
docs/monarch-integration.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Segregation modes (compatible inheritance patterns given the pedigree).
MODE_DE_NOVO = "de_novo"
MODE_HOM_RECESSIVE = "homozygous_recessive"
MODE_COMPOUND_HET = "compound_het"
MODE_X_LINKED = "x_linked_recessive"
MODE_DOMINANT = "dominant"

_STRONG_MODES = frozenset(
    {MODE_DE_NOVO, MODE_HOM_RECESSIVE, MODE_COMPOUND_HET, MODE_X_LINKED}
)

# Tunables.
_SEG_WEIGHT_STRONG = 1.0
_SEG_WEIGHT_DOMINANT = 0.85
_SEG_WEIGHT_NONE = 0.6
# Weight of the phenotype term in the combined score. Like Exomiser, phenotype
# relevance reorders candidates: a variant in a phenotype-matched gene can outrank an
# equally deleterious variant in a phenotype-irrelevant gene. Genes with no Monarch
# phenotype data score 0 on the phenotype axis (shown explicitly in the UI), so users
# can re-sort by the raw variant score when chasing novel-gene candidates.
_PHENOTYPE_WEIGHT = 0.5
# Predictor-only evidence is capped below 1.0; a perfect score is reserved for ClinVar
# pathogenic assertions, so variant scores spread out instead of saturating.
_MAX_PREDICTOR_PATHOGENICITY = 0.9

_HIGH_IMPACT = "high"
_PATHOGENIC_CLINVAR = ("pathogenic", "likely_pathogenic", "likely pathogenic")
_BENIGN_CLINVAR = ("benign", "likely_benign", "likely benign")


@dataclass(slots=True)
class VariantScore:
    pathogenicity: float
    frequency: float
    segregation_weight: float
    variant_score: float
    phenotype_score: float | None
    combined_score: float
    segregation_modes: list[str] = field(default_factory=list)


def pathogenicity_score(
    *,
    impact: str | None,
    clinvar: str | None,
    cadd_phred: float | None,
    revel: float | None,
    spliceai_max: float | None,
    lof: str | None,
) -> float:
    """Predicted deleteriousness in [0, 1]."""
    clin = (clinvar or "").strip().lower()
    if any(token in clin for token in _PATHOGENIC_CLINVAR):
        return 1.0
    if clin and "conflict" not in clin and any(token in clin for token in _BENIGN_CLINVAR):
        return 0.05

    impact_value = (impact or "").strip().lower()
    lof_value = (lof or "").strip().upper()
    if impact_value == _HIGH_IMPACT or lof_value == "HC":
        base = 0.85
    elif impact_value == "moderate":
        base = 0.4
    elif impact_value == "low":
        base = 0.15
    else:
        base = 0.05

    predictors = [base]
    if revel is not None:
        predictors.append(max(0.0, min(1.0, revel)))
    if cadd_phred is not None:
        predictors.append(max(0.0, min(1.0, cadd_phred / 40.0)))
    if spliceai_max is not None:
        predictors.append(max(0.0, min(1.0, spliceai_max)))
    return min(_MAX_PREDICTOR_PATHOGENICITY, max(predictors))


def frequency_score(
    *, gnomad_popmax_af: float | None, gnomad_af: float | None
) -> float:
    """Rarity score in [0, 1] — rarer is higher. Uses popmax, falling back to AF."""
    af = gnomad_popmax_af if gnomad_popmax_af is not None else gnomad_af
    if af is None or af <= 1e-6:
        return 1.0
    if af < 1e-4:
        return 0.9
    if af < 1e-3:
        return 0.7
    if af < 1e-2:
        return 0.4
    if af < 5e-2:
        return 0.1
    return 0.0


def segregation_weight(modes: list[str]) -> float:
    if any(mode in _STRONG_MODES for mode in modes):
        return _SEG_WEIGHT_STRONG
    if MODE_DOMINANT in modes:
        return _SEG_WEIGHT_DOMINANT
    return _SEG_WEIGHT_NONE


def combine(variant_score: float, phenotype_score: float | None) -> float:
    """Weighted combination of variant and phenotype evidence, in [0, 1].

    Phenotype relevance reorders candidates (Exomiser-style): a phenotype-matched gene
    can outrank an equally deleterious variant in an unrelated gene. A gene with no
    Monarch phenotype data scores 0 on the phenotype axis; the raw ``variant_score`` is
    surfaced separately so novel-gene candidates remain findable by re-sorting.
    """
    phenotype = phenotype_score or 0.0
    return (1.0 - _PHENOTYPE_WEIGHT) * variant_score + _PHENOTYPE_WEIGHT * phenotype


def score_variant(
    *,
    impact: str | None,
    clinvar: str | None,
    cadd_phred: float | None,
    revel: float | None,
    spliceai_max: float | None,
    lof: str | None,
    gnomad_popmax_af: float | None,
    gnomad_af: float | None,
    segregation_modes: list[str],
    phenotype_score: float | None,
) -> VariantScore:
    pathogenicity = pathogenicity_score(
        impact=impact,
        clinvar=clinvar,
        cadd_phred=cadd_phred,
        revel=revel,
        spliceai_max=spliceai_max,
        lof=lof,
    )
    frequency = frequency_score(gnomad_popmax_af=gnomad_popmax_af, gnomad_af=gnomad_af)
    seg_weight = segregation_weight(segregation_modes)
    variant_score = pathogenicity * frequency * seg_weight
    combined = combine(variant_score, phenotype_score)
    return VariantScore(
        pathogenicity=pathogenicity,
        frequency=frequency,
        segregation_weight=seg_weight,
        variant_score=variant_score,
        phenotype_score=phenotype_score,
        combined_score=combined,
        segregation_modes=list(segregation_modes),
    )
