#!/usr/bin/env python3
"""P2-7: enforce per-module coverage floors on clinical-critical backend modules.

Reads a coverage.json (``pytest --cov-report=json:coverage.json``) and fails if any listed
module — or overall — has dropped below its floor. Floors are set just below the measured
baseline (2026-06-28) so they RATCHET against regression without churning on minor edits.

Modules whose bulk coverage comes from integration tests (skipped in the unit ``backend``
job — e.g. integrity_anchor_service) are deliberately NOT floored here; their behaviour is
gated by the smoke job's real-datastore tests instead.

Usage: python scripts/check-coverage-floor.py [coverage.json]
"""

from __future__ import annotations

import json
import sys

# Global floor for the whole backend/app package (baseline ~61.4%).
GLOBAL_FLOOR = 58.0

# Per-module floors (percent of lines covered) for clinical-critical modules.
MODULE_FLOORS: dict[str, float] = {
    "backend/app/services/acmg_points.py": 95.0,
    "backend/app/services/cnv_acmg_points.py": 90.0,
    "backend/app/services/classification_drift_service.py": 90.0,
    "backend/app/services/clinical_audit_service.py": 85.0,
    "backend/app/services/hash_chain.py": 90.0,
    "backend/app/services/haplotype_lineage_service.py": 85.0,
    "backend/app/services/nipt_analysis.py": 88.0,
    "backend/app/services/sample_integrity_qc.py": 82.0,
    "backend/app/services/report_signout_service.py": 65.0,
}


def main(path: str) -> int:
    with open(path) as handle:
        data = json.load(handle)
    files = data.get("files", {})
    failures: list[str] = []

    overall = data.get("totals", {}).get("percent_covered", 0.0)
    status = "OK " if overall >= GLOBAL_FLOOR else "LOW"
    print(f"[{status}] overall {overall:5.1f}%  (floor {GLOBAL_FLOOR:.0f}%)")
    if overall < GLOBAL_FLOOR:
        failures.append(f"overall {overall:.1f}% < {GLOBAL_FLOOR:.0f}%")

    for module, floor in sorted(MODULE_FLOORS.items()):
        info = files.get(module)
        if info is None:
            failures.append(f"{module}: NOT FOUND in coverage report")
            print(f"[ERR] {module}: not found in coverage report")
            continue
        covered = info["summary"]["percent_covered"]
        status = "OK " if covered >= floor else "LOW"
        print(f"[{status}] {covered:5.1f}%  (floor {floor:4.0f}%)  {module}")
        if covered < floor:
            failures.append(f"{module}: {covered:.1f}% < {floor:.0f}%")

    if failures:
        print("\nCoverage floor FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        print("\nAdd tests, or (if intentional) adjust the floor in scripts/check-coverage-floor.py.")
        return 1
    print("\nAll coverage floors met.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "coverage.json"))
