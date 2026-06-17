"""Tests for Monarch gene -> disease association parsing and aggregation."""

from backend.app.services.monarch_ingest import (
    _Association,
    _DiseasePhenotype,
    parse_disease_phenotype_tsv,
    parse_gene_disease_tsv,
)

_HEADER = (
    "subject\tsubject_label\tsubject_category\tsubject_taxon\tsubject_taxon_label\t"
    "negated\tpredicate\tobject\tobject_label\tobject_category\tqualifiers\t"
    "publications\thas_evidence\tprimary_knowledge_source\taggregator_knowledge_source"
)


def _row(subject, label, predicate, obj, obj_label, source, negated=""):
    return (
        f"{subject}\t{label}\tbiolink:Gene\tNCBITaxon:9606\tHomo sapiens\t"
        f"{negated}\t{predicate}\t{obj}\t{obj_label}\tbiolink:Disease\t\t\t\t"
        f"{source}\t['infores:monarchinitiative']"
    )


def _tsv(*rows: str) -> str:
    return "\n".join((_HEADER, *rows)) + "\n"


def test_parse_aggregates_sources_and_picks_strongest_predicate() -> None:
    text = _tsv(
        _row("HGNC:1", "GENEA", "biolink:gene_associated_with_condition",
             "MONDO:1", "disease one", "infores:orphanet"),
        _row("HGNC:1", "GENEA", "biolink:causes",
             "MONDO:1", "disease one", "infores:omim"),
    )
    associations: dict[tuple[str, str], _Association] = {}
    parse_gene_disease_tsv(text, associations=associations)

    assert len(associations) == 1
    record = associations[("HGNC:1", "MONDO:1")]
    # Strongest predicate wins; sources and predicates accumulate.
    assert record.predicate == "causes"
    assert record.predicates == {"causes", "gene_associated_with_condition"}
    assert record.sources == {"omim", "orphanet"}
    assert record.causal is True


def test_parse_filters_non_hgnc_subjects_and_negated_rows() -> None:
    text = _tsv(
        _row("MONDO:9", "diseaseX", "biolink:causes", "MONDO:1", "d1", "infores:omim"),
        _row("HGNC:2", "GENEB", "biolink:causes", "MONDO:2", "d2", "infores:omim",
             negated="True"),
        _row("HGNC:3", "GENEC", "biolink:causes", "MONDO:3", "d3", "infores:omim"),
    )
    associations: dict[tuple[str, str], _Association] = {}
    parse_gene_disease_tsv(text, associations=associations)

    assert set(associations) == {("HGNC:3", "MONDO:3")}


def test_noncausal_only_predicate_is_not_marked_causal() -> None:
    text = _tsv(
        _row("HGNC:4", "GENED", "biolink:associated_with_increased_likelihood_of",
             "MONDO:4", "d4", "infores:omim"),
    )
    associations: dict[tuple[str, str], _Association] = {}
    parse_gene_disease_tsv(text, associations=associations)

    record = associations[("HGNC:4", "MONDO:4")]
    assert record.causal is False
    assert record.predicate == "associated_with_increased_likelihood_of"


def _pheno_row(disease, disease_label, hpo, hpo_label, source, negated=""):
    return (
        f"{disease}\t{disease_label}\tbiolink:Disease\t\t\t"
        f"{negated}\tbiolink:has_phenotype\t{hpo}\t{hpo_label}\tbiolink:PhenotypicFeature\t\t\t\t"
        f"{source}\t['infores:monarchinitiative']"
    )


def test_disease_phenotype_aggregates_sources() -> None:
    text = _tsv(
        _pheno_row("MONDO:1", "d1", "HP:1", "seizure", "infores:omim"),
        _pheno_row("MONDO:1", "d1", "HP:1", "seizure", "infores:orphanet"),
    )
    phenotypes: dict[tuple[str, str], _DiseasePhenotype] = {}
    parse_disease_phenotype_tsv(text, phenotypes=phenotypes)

    assert len(phenotypes) == 1
    record = phenotypes[("MONDO:1", "HP:1")]
    assert record.sources == {"omim", "orphanet"}
    assert record.negated is False


def test_disease_phenotype_present_assertion_wins_over_negated() -> None:
    text = _tsv(
        _pheno_row("MONDO:2", "d2", "HP:2", "ataxia", "infores:omim", negated="True"),
        _pheno_row("MONDO:2", "d2", "HP:2", "ataxia", "infores:orphanet"),
    )
    phenotypes: dict[tuple[str, str], _DiseasePhenotype] = {}
    parse_disease_phenotype_tsv(text, phenotypes=phenotypes)

    assert phenotypes[("MONDO:2", "HP:2")].negated is False


def test_disease_phenotype_keeps_pure_exclusions_and_filters_non_hp() -> None:
    text = _tsv(
        _pheno_row("MONDO:3", "d3", "HP:3", "excluded", "infores:omim", negated="True"),
        _pheno_row("MONDO:4", "d4", "MONDO:9", "not-a-phenotype", "infores:omim"),
    )
    phenotypes: dict[tuple[str, str], _DiseasePhenotype] = {}
    parse_disease_phenotype_tsv(text, phenotypes=phenotypes)

    assert set(phenotypes) == {("MONDO:3", "HP:3")}
    assert phenotypes[("MONDO:3", "HP:3")].negated is True
