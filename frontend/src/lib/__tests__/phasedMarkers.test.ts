import { describe, expect, it } from 'vitest';

import {
  computeFamilyPhasedMarkers,
  phasedAlleles,
  transmittedParentHomolog,
  type MarkerMemberLike,
  type MarkerVariantLike,
} from '../phasedMarkers';

describe('phasedAlleles', () => {
  it('splits a phased GT', () => {
    expect(phasedAlleles('0|1')).toEqual(['0', '1']);
    expect(phasedAlleles('1|0')).toEqual(['1', '0']);
  });
  it('rejects unphased or missing GTs', () => {
    expect(phasedAlleles('0/1')).toBeNull();
    expect(phasedAlleles('.|1')).toBeNull();
    expect(phasedAlleles('')).toBeNull();
    expect(phasedAlleles(null)).toBeNull();
  });
});

describe('transmittedParentHomolog', () => {
  it('resolves the paternal homolog when the mother is homozygous', () => {
    // father 0|1, mother 0|0; child 0|0 -> paternal allele 0 -> father homolog 0
    expect(transmittedParentHomolog(['0', '1'], ['0', '0'], ['0', '0'])).toBe(0);
    // child 0|1 -> paternal allele 1 -> father homolog 1
    expect(transmittedParentHomolog(['0', '1'], ['0', '0'], ['0', '1'])).toBe(1);
  });

  it('returns null when the parent is homozygous (uninformative)', () => {
    expect(transmittedParentHomolog(['0', '0'], ['0', '1'], ['0', '0'])).toBeNull();
  });

  it('returns null when both parents are het and the child is het (ambiguous)', () => {
    expect(transmittedParentHomolog(['0', '1'], ['0', '1'], ['0', '1'])).toBeNull();
  });

  it('resolves even when both parents are het if the child is homozygous', () => {
    expect(transmittedParentHomolog(['0', '1'], ['0', '1'], ['1', '1'])).toBe(1);
    expect(transmittedParentHomolog(['0', '1'], ['0', '1'], ['0', '0'])).toBe(0);
  });
});

const members: MarkerMemberLike[] = [
  { sample_id: 'FATHER', role: 'father' },
  { sample_id: 'MOTHER', role: 'mother' },
  { sample_id: 'CHILD', role: 'proband', affected: true },
];

const variant = (
  pos: number,
  father: string,
  mother: string,
  child: string,
): MarkerVariantLike => ({
  start: pos,
  source: 'glimpse2',
  genotypes: [
    { sample: 'FATHER', gt: father },
    { sample: 'MOTHER', gt: mother },
    { sample: 'CHILD', gt: child },
  ],
});

describe('computeFamilyPhasedMarkers', () => {
  it('tracks a paternal recombination across markers (mother homozygous)', () => {
    const variants = [
      variant(100, '0|1', '0|0', '0|0'), // paternal 0
      variant(200, '0|1', '0|0', '0|0'), // paternal 0
      variant(300, '0|1', '0|0', '0|1'), // paternal 1  <- switch
      variant(400, '0|1', '0|0', '0|1'), // paternal 1
    ];
    const markers = computeFamilyPhasedMarkers(variants, members).get('CHILD');
    expect(markers).toBeDefined();
    expect(markers!.map((m) => m.paternal)).toEqual([0, 0, 1, 1]);
    // mother is homozygous everywhere -> maternal side uninformative
    expect(markers!.every((m) => m.maternal === null)).toBe(true);
  });

  it('orients homologs by the affected child (flips when homolog 0 dominates)', () => {
    // affected child inherits paternal homolog 0 three times, 1 once -> father_flip = true
    const variants = [
      variant(100, '0|1', '0|0', '0|0'), // raw paternal 0
      variant(200, '0|1', '0|0', '0|0'), // raw 0
      variant(300, '0|1', '0|0', '0|0'), // raw 0
      variant(400, '0|1', '0|0', '0|1'), // raw 1
    ];
    const markers = computeFamilyPhasedMarkers(variants, members).get('CHILD');
    // raw [0,0,0,1] flipped -> [1,1,1,0]
    expect(markers!.map((m) => m.paternal)).toEqual([1, 1, 1, 0]);
  });

  it('returns nothing without both parents', () => {
    const incomplete: MarkerMemberLike[] = [
      { sample_id: 'MOTHER', role: 'mother' },
      { sample_id: 'CHILD', role: 'proband' },
    ];
    expect(computeFamilyPhasedMarkers([variant(100, '0|1', '0|0', '0|0')], incomplete).size).toBe(
      0,
    );
  });

  it('ignores non-imputed variants', () => {
    const called: MarkerVariantLike = {
      start: 100,
      source: 'clair3',
      genotypes: [
        { sample: 'FATHER', gt: '0|1' },
        { sample: 'MOTHER', gt: '0|0' },
        { sample: 'CHILD', gt: '0|1' },
      ],
    };
    const markers = computeFamilyPhasedMarkers([called], members).get('CHILD');
    expect(markers).toEqual([]);
  });
});
