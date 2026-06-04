# Family Member Management Impact Chain

CoGA stores family membership in PostgreSQL with the family graph split across
`family_members`, `samples`, and `family_relationships`. HPO annotations are
stored in `individual_hpo` and linked by `family_id` plus `sample_id` UUID.

## Tables That Reference Family Members

- `family_members`: active membership, role, clinical status, carrier status.
- `family_relationships`: parent-child and couple edges; `sample_id_a` is the parent or first partner, `sample_id_b` is the child or second partner.
- `individual_hpo`: per-individual HPO annotations.
- `sample_projects`: project visibility for a sample.
- `sample_interval_track_sources`: coverage, APCAD, segment, and haplotype track metadata.
- `repeat_expansions`: TRGT/repeat calls per sample.
- `sample_paraphase_results`: Paraphase copy-number and haplotype results per sample.
- ClickHouse SNV/indel entries: per-family variant calls with `calls.sampleId`.
- ClickHouse structural variant entries: per-family calls with `calls.sampleId`.

Family-level tables that can depend on member state include
`small_variant_reviews`, `structural_variant_reviews`, `family_structure_versions`,
the family pedigree text in `families.pedigree`, and derived browser tracks.

## Validation Assumptions

- Father relationships must point to male individuals.
- Mother relationships must point to female individuals.
- Unknown-sex individuals may remain generic parents, but cannot be saved as an explicit father or mother when their stored sex conflicts.
- Parent-child relationships are directed from parent to child and must be acyclic.
- A child can have at most one father and one mother.
- Removing a member is a soft removal from the active family graph; linked sample rows are retained for auditability.

## Derived Data Impact

Changing sex, role, identifier, or parent links can invalidate pedigree rendering,
segregation models, inheritance filtering, haplotype phasing, shared haplotype
calculations, embryo classification, and family-level variant review context.

Changing phenotype or carrier status can invalidate segregation analysis,
inheritance filtering, and saved variant interpretation context.

Phenotype, carrier, affected/unaffected, sex, and role edits are treated as
metadata-only changes. They update `samples`, `family_members`,
`family_relationships`, `families.pedigree`, `family_structure_versions`, and
`families.metadata.derived_data_status`. They do not delete, reload, reimport, or
recompute raw/imported datasets.

Changing HPO annotations marks phenotype-dependent derived data as stale in
`families.metadata.derived_data_status.hpo_annotations`.

The metadata-derived resources that are marked stale after phenotype/carrier
updates are:

- Pedigree display snapshots.
- Segregation and inheritance-filter views.
- Haplotype interpretation/classification overlays.
- Embryo risk/classification summaries.
- Saved variant interpretation context.

The imported datasets preserved by metadata updates are:

- APCAD and APCAD PCF interval tracks.
- Coverage and segment tracks.
- Haplotype interval tracks.
- GLIMPSE2, Clair3, and other SNV/indel ClickHouse variant entries.
- Structural variant ClickHouse entries.
- TRGT repeat expansion calls.
- QDNAseq or other coverage-derived uploads.

Renaming a member with imported genomic data is blocked because raw variant and
track datasets still carry the source sample identifier. Removing a member is a
soft removal from the active family graph and preserves imported datasets.

Batch phenotype/member updates use a single transaction. The UI queues edits for
multiple individuals and calls `PUT /families/{family_id}/members/batch` once,
then downstream family-level interpretation scopes are marked stale once for the
batch.

## Current Limitations

- Expensive derived analyses are marked stale; automatic recomputation is only
performed where the existing service already supports it.
- Some ClickHouse impact checks can be unavailable when ClickHouse is offline;
the API reports this as an unknown genotype-linkage risk.
- The deletion workflow soft-removes members instead of hard-deleting sample rows.
