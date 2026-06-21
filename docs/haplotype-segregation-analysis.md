# Haplotype Segregation Analysis

CoGA's haplotype segregation analysis is a **preimplantation genetic testing (PGT)**
tool. It visualises how the four grandparental haplotypes are inherited through a
family so you can read off **which embryos inherited the disease haplotype(s)**, and
flags the artifacts (recombinations near the locus, uninformative markers) that
would make that call unsafe.

It is shown as the **Haplotype track** in the **Chromosome view** (the ROI opens
here with flanking context). This document is the canonical reference for what the
track means; it complements the in-app user guide (`/docs` → *Haplotype segregation
analysis*).

> **Derived, not entered.** Everything coloured — the founder haplotypes, the
> relatives, and each embryo's affected/carrier/unaffected call — is **computed
> from the phased genotypes and the pedigree**, not typed in by the analyst. The
> only inputs are the family's pedigree (roles, parentage, sex), the recorded
> affected/carrier status, the inheritance model, and the region of interest (ROI).

---

## The clinical question

In PGT the couple (or a single parent + donor) produces a set of embryos, and a
known disease segregates in one or both families. The question is, **per embryo**:

- **Dominant disorder** — did it inherit the single affected haplotype that the
  affected parent and affected relatives share at the locus?
- **Recessive disorder** — did it inherit a carrier haplotype from *each* side
  (→ at risk / affected), from *one* side (→ carrier), or from *neither*?
- **X-linked** — sex-aware: a male inheriting the affected maternal haplotype is at
  risk; a female inheriting it on one side is a carrier.

The analysis answers this by colouring every individual's two haplotypes by which
grandparental founder homolog they descend from (identity-by-descent), then
identifying which founder haplotype carries the disease allele.

---

## The two layers

The track draws **two complementary layers** for every family member:

1. **Cleaned haplotype blocks** — the colour-coded inheritance blocks. Each member
   has two lanes (their two homologs); a block is a stretch of chromosome that
   descends from one founder haplotype, recolouring at each recombination
   breakpoint. This is the *interpretation* layer — the smoothed, easy-to-read
   answer to "which haplotype is this".

2. **Raw phased-marker overlay** — one dot per informative imputed marker, drawn on
   top of the blocks, **with no binning, smoothing, or voting**. This is the
   *diagnostic* layer. Because it is raw, it exposes exactly what the blocks hide:
   isolated phasing switches, jitter at recombination boundaries, and the precise
   marker where a crossover occurs. Use it to **confirm a breakpoint is real** and
   to **spot artifacts** before trusting the embryo call.

The blocks are the cleaned version of the markers; the markers are there to let you
audit the blocks.

---

## The colour code

Colour encodes **which founder haplotype** a block descends from. There are four
founders — the index couple's four homologs (one per grandparent line):

| Lane / colour | Meaning |
| --- | --- |
| **Dark blue** | Paternal founder homolog 0 |
| **Light blue** | Paternal founder homolog 1 |
| **Dark green** | Maternal founder homolog 0 |
| **Light green** | Maternal founder homolog 1 |
| **Grey** | *Untransmitted* or *unknown* — a homolog not inherited from a placed founder, or one CoGA could not place. Carries no founder identity. |

The dark/light split within a side is the two grandparental haplotypes on that
side. The **absolute** dark-vs-light assignment is arbitrary (it comes from the raw
phasing orientation); what matters is **consistency** — the same physical
grandparental haplotype keeps the same shade across everyone in the family, so you
can trace one haplotype from an affected grandparent down to an embryo.

### Risk overlay

On top of the founder colour, the locus-carrying haplotype(s) are highlighted so
the disease haplotype stands out:

| Overlay | Meaning |
| --- | --- |
| **Red** | The **dominant** affected haplotype (the single haplotype shared by the affected/obligate members at the ROI). |
| **Orange** | A **recessive carrier** haplotype. An affected individual has two orange haplotypes; a carrier has one. |

The risk overlay is derived (see *Disease-haplotype inference* below), not entered.

---

## How each member is coloured (pedigree IBD)

The stored haplotype blocks built at upload time are only meaningful for the index
**nuclear family** — the father, the mother, and their direct children/embryos —
because that is what the trio phasing grounds. The four founder homologs there get
their stable colour, and each child's paternal (hap1) / maternal (hap2) homolog is
coloured to match the founder it came from.

**Relatives** (a grandparent, an aunt/uncle, a cousin) are *not* part of that trio
phasing, so their stored blocks are biologically meaningless and must never be
trusted as-is. Worse, CoGA's role model is flat: a paternal grandmother is stored
with `role = mother`, which a naïve colourer would paint entirely green.

CoGA therefore **recomputes every relative's colour from the raw phased genotypes**,
propagating founder identity outward through the pedigree:

1. Start from the nuclear core (the founders + their children), already coloured.
2. Walk the pedigree graph along parent–child edges. For each relative reached from
   an already-coloured member, **identity-by-descent (IBD) match** the relative's
   two homologs against that member's two homologs. The homolog they share inherits
   the member's colour for that homolog; the relative's other homolog is
   *untransmitted* and is **greyed out**.

So a paternal grandmother gets **exactly one homolog coloured** (dark or light blue
— whichever the affected father shares with her) and the other grey. That is what
makes it possible to read off *which* paternal haplotype carries the dominant
disease allele: the affected grandparent's coloured homolog is the disease
haplotype, and you can follow that colour down to the embryos.

The matching is **recombination-aware**. A relative's shared haplotype switches
physical homolog lanes at each meiotic crossover; CoGA recovers those switch points
from the genotypes and only commits a switch once a run of contradicting markers is
both long enough and wide enough (matching the block builder's thresholds), so real
crossovers split the track but isolated phasing noise does not. At a crossover the
disease-carrying colour keeps its identity but jumps lanes (grey follows it).

A member CoGA cannot confidently place is rendered **entirely grey** — never
mis-coloured.

### Single-parent (donor) families

CoGA supports embryos with only **one known parent** (e.g. a single woman, or a
couple using a donor gamete) while the disorder segregates in the known parent's
family. The core is **anchored on the embryos**: the index parents are the embryos'
parents, and the donor side is simply absent.

- The **known parent's two homologs are the founders** (one per grandparent), and
  are coloured by tracing them up to the affected grandparent.
- The embryos are the known parent's children, so the same relative-IBD machinery
  colours **the known-parent-derived lane** and **greys the donor lane** (the donor
  is unknown/unavailable).

The grandparents are essential here — they are what phase the known parent so the
disease haplotype can be identified.

---

## Disease-haplotype inference

The disease haplotype(s) are **inferred from the analysis**, using the recorded
affected/carrier status and the inheritance model:

- **Dominant** — the single haplotype **shared at the ROI by the informative
  members** (affected individuals, plus obligate carriers). Taking the intersection
  of the haplotypes those members carry, the disease haplotype is the one signature
  they all share. Known non-carrier, unaffected members are used to subtract false
  candidates. Highlighted **red**.
- **Recessive** — a carrier haplotype on **each side**: the paternal-side haplotype
  shared by the affecteds, and the maternal-side one. Both are highlighted
  **orange**. An affected embryo carries both; a carrier carries one.
- **X-linked recessive** — from affected males (hemizygous) where available, else
  from affected females per side. Sex-aware.
- **X-linked dominant** — the single shared affected haplotype, as for dominant.

If the members do not resolve to a unique haplotype, the model is **uninformative**
and no risk overlay is drawn (and embryo calls fall back to *uninformative* —
see below).

---

## The derived embryo classification (at the ROI)

For each embryo, CoGA compares the haplotypes it carries at the ROI against the
inferred disease haplotype(s) and assigns one of four states. **This call is
derived from the analysis; it is not an entered status.**

| State | Meaning |
| --- | --- |
| **Affected / at-risk** | Carries the disease haplotype as required for the model — the dominant affected haplotype, **both** recessive carrier haplotypes, or (X-linked) the at-risk combination for its sex. |
| **Carrier** | Recessive: carries **one** of the two carrier haplotypes. X-linked female: carries it on one side. |
| **Unaffected (non-carrier)** | Carries none of the disease haplotype(s). |
| **Uninformative** | The disease model could not be resolved (no unique disease haplotype; or, recessive, only one side resolved), so no call can be made. |

### Warnings to read before trusting the call

Two situations make an at-ROI call unsafe, and the raw-marker overlay is how you
catch them:

- **Recombination close to the ROI.** A crossover near the locus means the
  haplotype the embryo carries *at the variant* may differ from what it carries a
  short distance away. Use the marker overlay to see exactly where the breakpoint
  falls relative to the ROI; a breakpoint inside or adjacent to the locus warrants
  caution and confirmation.
- **Uninformative markers at the ROI.** If the locus sits in a stretch with few or
  no informative markers, the haplotype identity there is interpolated from the
  flanks rather than directly observed. Check the marker overview (below): sparse
  informative markers at the ROI weakens the call.

---

## The ROI marker overview (re-checking errors and artifacts)

Alongside the track, CoGA shows a **per-site marker overview**: a members × markers
grid of the raw phased genotypes across the ROI, colour-coded by haplotype, with the
**informative-marker count** for each member. This is the table you use to
*re-check* a surprising embryo call against the underlying data:

- Confirm the genotypes that drive the haplotype assignment at and around the ROI.
- See **how many informative markers** actually distinguish the haplotypes near the
  locus — a handful of markers over a wide span is weak evidence.
- Spot per-site inconsistencies (a single marker disagreeing with its neighbours)
  that are phasing/imputation artifacts rather than real recombination.

The overlay and overview are deliberately **raw** — one call per site, no binning —
because hiding the noise would hide exactly the signal you need to validate the
clean blocks.

> The raw-marker overlay and overview are computed only for the **index parents'
> own children** (single-parent families: the one known parent's children). Running
> the parent-of-origin transmission logic on a relative would be biologically
> backwards and produce coincidental, wildly-switching noise — so relatives appear
> on the track (their lineage block is the meaningful view) but carry no marker
> dots.

---

## Quality-control signals

Per child, CoGA reports two QC numbers from the sites where both parents and the
child have a valid phased genotype (jointly informative sites):

- **Informative-site count** — how many sites actually distinguish the haplotypes.
  More is better; a low count over the region means weak phasing evidence.
- **Mendel-error rate** — the fraction of jointly-informative sites where the
  child's genotype is **impossible** given the parents' alleles (an allele the child
  could not have inherited). A non-trivial rate is a red flag for a **sample swap or
  wrong pedigree** and should be resolved before trusting any haplotype call.
  (For a single-parent family a Mendel error is the child sharing *no* allele with
  the known parent.)

A genuine Mendelian inconsistency is distinct from benign parent-of-origin
ambiguity (e.g. both parents and the child heterozygous): the latter is perfectly
consistent, just uninformative, and is **not** counted as an error.

---

## Known limitations

- **Recessive single-parent (donor) families are uninformative at the ROI.**
  Classifying a recessive embryo needs *both* parental risk haplotypes, but the
  donor side is unknown, so the embryo call returns **uninformative** (a deliberately
  safe result — the donor's carrier status cannot be assumed). The known-parent risk
  haplotype is still coloured; surfacing a "carries the known-parent risk allele,
  donor status unknown" call is a planned enhancement.
- **Relatives are greyed on sex chromosomes and mtDNA.** The IBD logic assumes two
  homologs at every site. Hemizygous X (in males), the non-recombining Y, and the
  mitochondrion break that assumption, so on non-autosomes CoGA leaves relatives
  grey rather than risk mis-colouring them. The nuclear core still keeps its
  role-based colouring there. Proper hemizygous-X handling is a follow-up.
- **Truncation on very large regions.** Whole-chromosome marker fetches are capped.
  When the cap is hit, the raw-marker overlay is suppressed (with a "too many sites
  — zoom in" state) rather than drawn partway across a block, and coloured relative
  blocks are clamped to the last site with evidence (the rest greyed). The cleaned
  blocks still render; zoom into the ROI to restore the full marker overlay.

---

## Where this lives (developer notes)

- **Pedigree IBD colouring** — `backend/app/services/haplotype_lineage_service.py`
  (`annotate_lineage`: builds the pedigree, identifies the embryo-anchored nuclear
  core, BFS-propagates founder colour by IBD matching, recombination-segments each
  relative, greys non-autosomes / unplaceable members / truncation tails). Pure, no
  I/O; the callers in `bed_service` do the fetching, including the genome-wide
  `/haplotypes/batch` path.
- **Raw phased-marker overlay + QC** —
  `backend/app/services/phased_marker_service.py`
  (`compute_phased_markers`: raw per-site lane values for the index couple's
  children, oriented through the parents' stored-block shade maps; trio and
  single-parent modes; per-child informative-site / Mendel-error QC; fetch
  truncation guard).
- **Disease-haplotype inference + embryo classification** —
  `frontend/src/lib/haplotypeRisk.ts` (`inferDiseaseHaplotypes` for the disease
  signature(s) by inheritance mode; `interpretSampleHaplotypeRisk` returns
  `affected_or_at_risk` / `carrier` / `unaffected_non_carrier` / `uninformative`;
  `getHaplotypeLaneSignature` treats the backend's pedigree-aware lineage tags as
  authoritative over the flat `role`).
