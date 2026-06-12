/**
 * Per-marker parent-of-origin for GLIMPSE2-imputed small variants.
 *
 * For each informative marker in a trio, we determine which parental homolog
 * (0/1) the child inherited on the paternal and maternal side. Plotting those
 * along the chromosome reveals recombination/haplotype switches at single-marker
 * resolution — finer than the smoothed haplotype blocks (which require
 * 50 markers / 500 kb to switch).
 *
 * This is a faithful port of the backend block builder's logic
 * (`_transmitted_parent_haplotype` + `_orient_haplotype_rows_by_affected_child`
 * in variant_upload_service.py), so the homolog indices match the stored
 * haplotype blocks and therefore the Haplotype track's colours + disease overlay.
 */

export type Homolog = 0 | 1;

export interface MarkerMemberLike {
  sample_id: string;
  role?: string | null;
  affected?: boolean | null;
}

export interface MarkerGenotypeLike {
  sample: string;
  gt: string;
}

export interface MarkerVariantLike {
  start: number;
  source?: string | null;
  genotypes?: MarkerGenotypeLike[];
}

export interface PhasedMarker {
  pos: number;
  /** Oriented paternal homolog (0/1) the child inherited, or null if uninformative. */
  paternal: Homolog | null;
  /** Oriented maternal homolog (0/1), or null if uninformative. */
  maternal: Homolog | null;
}

const IMPUTED_SOURCES = new Set(['glimpse2', 'shapeit']);

export const isImputedSource = (source?: string | null): boolean =>
  Boolean(source) && IMPUTED_SOURCES.has(String(source).toLowerCase());

/** Split a phased GT ("0|1") into its two alleles, or null if unphased/missing. */
export const phasedAlleles = (gt: string | null | undefined): [string, string] | null => {
  if (!gt || !gt.includes('|')) return null;
  const parts = gt.split('|');
  const a = parts[0];
  const b = parts[1];
  if (!a || !b || a === '.' || b === '.') return null;
  return [a, b];
};

const sortedPair = (a: string, b: string): string => (a <= b ? `${a}${b}` : `${b}${a}`);

/**
 * Which of `parent`'s two phased homologs (0/1) was transmitted to `child`,
 * given the `otherParent`'s alleles — or null when ambiguous/uninformative.
 * Port of backend `_transmitted_parent_haplotype`.
 */
export const transmittedParentHomolog = (
  parent: [string, string] | null,
  otherParent: [string, string] | null,
  child: [string, string] | null,
): Homolog | null => {
  if (!parent || !otherParent || !child) return null;
  const childState = sortedPair(child[0], child[1]);
  const possible = new Set<number>();
  parent.forEach((parentAllele, index) => {
    otherParent.forEach((otherAllele) => {
      if (sortedPair(parentAllele, otherAllele) === childState) {
        possible.add(index);
      }
    });
  });
  if (possible.size !== 1) return null;
  return possible.has(0) ? 0 : 1;
};

const flipHomolog = (value: Homolog | null, flip: boolean): Homolog | null =>
  value === null ? null : flip ? ((1 - value) as Homolog) : value;

const role = (member: MarkerMemberLike): string => (member.role || '').toLowerCase();

interface ResolvedRoles {
  father?: MarkerMemberLike;
  mother?: MarkerMemberLike;
  children: MarkerMemberLike[];
}

export const resolveTrioRoles = (members: MarkerMemberLike[]): ResolvedRoles => {
  const father = members.find((member) => role(member) === 'father');
  const mother = members.find((member) => role(member) === 'mother');
  const children = members.filter((member) => member !== father && member !== mother);
  return { father, mother, children };
};

/**
 * Oriented per-marker parent-of-origin homologs for every child, from imputed
 * variants that carry all family samples' phased genotypes. Orientation
 * (father/mother flip from the affected children's transmitted counts) mirrors
 * the backend block builder so indices align with the stored haplotype blocks.
 *
 * Returns a map of child sample_id -> markers sorted by position.
 */
export const computeFamilyPhasedMarkers = (
  variants: MarkerVariantLike[],
  members: MarkerMemberLike[],
): Map<string, PhasedMarker[]> => {
  const { father, mother, children } = resolveTrioRoles(members);
  const result = new Map<string, PhasedMarker[]>();
  if (!father || !mother || children.length === 0) return result;

  const affected = new Set(
    children.filter((child) => child.affected).map((child) => child.sample_id),
  );
  const raw = new Map<string, PhasedMarker[]>();
  children.forEach((child) => raw.set(child.sample_id, []));
  const fatherCounts: Record<Homolog, number> = { 0: 0, 1: 0 };
  const motherCounts: Record<Homolog, number> = { 0: 0, 1: 0 };

  for (const variant of variants) {
    if (!isImputedSource(variant.source) || !variant.genotypes) continue;
    const gtBySample = new Map(variant.genotypes.map((g) => [g.sample, g.gt]));
    const fatherAlleles = phasedAlleles(gtBySample.get(father.sample_id));
    const motherAlleles = phasedAlleles(gtBySample.get(mother.sample_id));
    if (!fatherAlleles || !motherAlleles) continue;
    for (const child of children) {
      const childAlleles = phasedAlleles(gtBySample.get(child.sample_id));
      const paternal = transmittedParentHomolog(fatherAlleles, motherAlleles, childAlleles);
      const maternal = transmittedParentHomolog(motherAlleles, fatherAlleles, childAlleles);
      if (paternal === null && maternal === null) continue;
      raw.get(child.sample_id)?.push({ pos: variant.start, paternal, maternal });
      if (affected.has(child.sample_id)) {
        if (paternal !== null) fatherCounts[paternal] += 1;
        if (maternal !== null) motherCounts[maternal] += 1;
      }
    }
  }

  const fatherFlip = fatherCounts[0] > fatherCounts[1];
  const motherFlip = motherCounts[0] > motherCounts[1];

  for (const child of children) {
    const markers = (raw.get(child.sample_id) || [])
      .map((marker) => ({
        pos: marker.pos,
        paternal: flipHomolog(marker.paternal, fatherFlip),
        maternal: flipHomolog(marker.maternal, motherFlip),
      }))
      .sort((a, b) => a.pos - b.pos);
    result.set(child.sample_id, markers);
  }
  return result;
};
