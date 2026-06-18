from __future__ import annotations


# Primary-assembly chromosomes (after normalising away any "chr" prefix). Used to
# keep gene/locus lookups on the effective chromosome instead of resolving to an
# ALT/scaffold contig (e.g. "1_KI270766v1_alt", "Un_GL000195v1").
PRIMARY_CHROMOSOMES = frozenset(
    [str(number) for number in range(1, 23)] + ["X", "Y", "M", "MT"]
)


def normalize_chromosome(chromosome: str) -> str:
    chromosome = str(chromosome or "").strip()
    return chromosome[3:] if chromosome.lower().startswith("chr") else chromosome


def is_primary_chromosome(chromosome: str) -> bool:
    """True for a primary-assembly chromosome, False for ALT/scaffold contigs."""

    return normalize_chromosome(chromosome).upper() in PRIMARY_CHROMOSOMES


def chromosome_aliases(chromosome: str) -> list[str]:
    normalized = normalize_chromosome(chromosome)
    if normalized.upper() in {"M", "MT"}:
        candidates = [normalized, f"chr{normalized}", "MT", "chrMT", "M", "chrM"]
    else:
        candidates = [normalized, f"chr{normalized}"]
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))
