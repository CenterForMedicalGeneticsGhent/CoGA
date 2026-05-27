from __future__ import annotations


def normalize_chromosome(chromosome: str) -> str:
    chromosome = str(chromosome or "").strip()
    return chromosome[3:] if chromosome.lower().startswith("chr") else chromosome


def chromosome_aliases(chromosome: str) -> list[str]:
    normalized = normalize_chromosome(chromosome)
    if normalized.upper() in {"M", "MT"}:
        candidates = [normalized, f"chr{normalized}", "MT", "chrMT", "M", "chrM"]
    else:
        candidates = [normalized, f"chr{normalized}"]
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))
