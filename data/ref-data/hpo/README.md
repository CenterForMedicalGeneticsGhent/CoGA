# HPO ontology — vendored reference (version-pinned)

`hp.obo` is deliberately **vendored** (committed) rather than fetched at build
time, so the platform bootstraps deterministically — including in offline /
air-gapped deployments — as required for an IVDR in-house IVD. The runtime
auto-download (`HPO_DOWNLOAD_IF_MISSING=True`,
[`hpo_service.py`](../../../backend/app/services/hpo_service.py)) is a **fallback
only**; this committed copy is the authoritative, pinned reference.

## Pinned version

| Field | Value |
| --- | --- |
| Source | Human Phenotype Ontology (HPO) |
| File | `hp.obo` (OBO format-version 1.2) |
| **Release (`data-version`)** | **`hp/releases/2026-02-16`** |
| Terms | 19,944 |
| Vendored into the repo | 2026-06-05 |
| SHA-256 | `8d6c23798667d4506767ce643fc3c028f0d1c85e7e1d8810e491181a345d53cd` |
| Canonical (floating) URL | <http://purl.obolibrary.org/obo/hp.obo> |
| Pinned (reproducible) URL | <http://purl.obolibrary.org/obo/hp/releases/2026-02-16/hp.obo> |
| License | HPO license — free for use, see <https://hpo.jax.org/app/license> |

The **pinned URL** is the reproducible fetch: it always returns the exact
`2026-02-16` release, whereas the canonical URL floats to the latest release.

## How the version is used

At startup `hpo_service._parse_hpo_obo_release_metadata` parses the `data-version:`
header from this file and records the release version/date into the platform
**reference layer**, which is frozen into each signed report's sign-out snapshot
(see [clinical-traceability.md](../../../docs/clinical-traceability.md) and the
[TF-08 SOUP register](../../../docs/regulatory/TF-08-soup-register.md), row *HPO*).
So the version below is not just documentation — it is what the running system
captures and reports.

## Updating (controlled change)

Replacing this ontology is a **TF-18 controlled change**:

1. Download the new pinned release from its versioned PURL.
2. Replace `hp.obo`, then update the **Release**, **Terms**, **Vendored**, and
   **SHA-256** rows above (recompute with `shasum -a 256 hp.obo`).
3. Re-run the performance-evaluation scope (TF-10 / TF-11) that pins which
   versions were validated; evidence-drift detection will flag any prior
   classification the new release would change.
