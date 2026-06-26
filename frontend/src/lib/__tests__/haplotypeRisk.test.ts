import { describe, expect, it } from 'vitest';
import {
  diseaseHaplotypeKindForLane,
  getHaplotypeLaneSignature,
  getRenderableHaplotypeLanes,
  inferDiseaseHaplotypes,
  interpretSampleHaplotypeRisk,
  type HaplotypeMemberLike,
  type HaplotypeSampleLike,
} from '../haplotypeRisk';

const region = { chr: '1', start: 40, end: 60 };

describe('haplotype risk inference', () => {
  it('identifies the dominant haplotype shared by an affected parent and child', () => {
    const members: HaplotypeMemberLike[] = [
      { sample_id: 'FATHER', role: 'father', affected: true, sex: 'male' },
      { sample_id: 'PROBAND', role: 'proband', affected: true, sex: 'female' },
      { sample_id: 'EMBRYO1', role: 'embryo', affected: false, sex: 'female' },
    ];
    const samples: HaplotypeSampleLike[] = [
      {
        sample: 'FATHER',
        segments: [{ chr: '1', start: 0, end: 100, hap1: '0', hap2: '1' }],
      },
      {
        sample: 'PROBAND',
        segments: [{ chr: '1', start: 0, end: 100, hap1: '1', hap2: '0' }],
      },
      {
        sample: 'EMBRYO1',
        segments: [{ chr: '1', start: 0, end: 100, hap1: '1', hap2: '1' }],
      },
    ];

    const model = inferDiseaseHaplotypes({
      samples,
      members,
      inheritanceModel: 'AD',
      region,
    });

    expect(model.signatures).toEqual([{ origin: 'paternal', value: '1', kind: 'dominant' }]);
    expect(diseaseHaplotypeKindForLane(model, members[2], samples[2].segments[0], 'hap1', '1')).toBe('dominant');
    expect(diseaseHaplotypeKindForLane(model, members[2], samples[2].segments[0], 'hap2', '1')).toBeNull();
    expect(
      interpretSampleHaplotypeRisk({
        model,
        samples,
        member: members[2],
        region,
      }),
    ).toBe('affected_or_at_risk');
  });

  it('leaves dominant coloring neutral when a single affected sample is ambiguous', () => {
    const members: HaplotypeMemberLike[] = [{ sample_id: 'PROBAND', role: 'proband', affected: true, sex: 'female' }];
    const samples: HaplotypeSampleLike[] = [
      {
        sample: 'PROBAND',
        segments: [{ chr: '1', start: 0, end: 100, hap1: '1', hap2: '1' }],
      },
    ];

    const model = inferDiseaseHaplotypes({
      samples,
      members,
      inheritanceModel: 'AD',
      region,
    });

    expect(model.informative).toBe(false);
    expect(model.signatures).toEqual([]);
  });

  it('infers paternal and maternal recessive risk haplotypes from an affected child', () => {
    const members: HaplotypeMemberLike[] = [
      { sample_id: 'PROBAND', role: 'proband', affected: true, sex: 'female' },
      {
        sample_id: 'EMBRYO_RISK',
        role: 'embryo',
        affected: false,
        sex: 'female',
      },
      {
        sample_id: 'EMBRYO_CARRIER',
        role: 'embryo',
        affected: false,
        sex: 'female',
      },
      {
        sample_id: 'EMBRYO_CLEAR',
        role: 'embryo',
        affected: false,
        sex: 'female',
      },
    ];
    const samples: HaplotypeSampleLike[] = [
      {
        sample: 'PROBAND',
        segments: [{ chr: '1', start: 0, end: 100, hap1: '1', hap2: '0' }],
      },
      {
        sample: 'EMBRYO_RISK',
        segments: [{ chr: '1', start: 0, end: 100, hap1: '1', hap2: '0' }],
      },
      {
        sample: 'EMBRYO_CARRIER',
        segments: [{ chr: '1', start: 0, end: 100, hap1: '1', hap2: '1' }],
      },
      {
        sample: 'EMBRYO_CLEAR',
        segments: [{ chr: '1', start: 0, end: 100, hap1: '0', hap2: '1' }],
      },
    ];

    const model = inferDiseaseHaplotypes({
      samples,
      members,
      inheritanceModel: 'AR',
      region,
    });

    expect(model.signatures).toEqual([
      { origin: 'paternal', value: '1', kind: 'recessive-paternal' },
      { origin: 'maternal', value: '0', kind: 'recessive-maternal' },
    ]);
    expect(
      interpretSampleHaplotypeRisk({
        model,
        samples,
        member: members[1],
        region,
      }),
    ).toBe('affected_or_at_risk');
    expect(
      interpretSampleHaplotypeRisk({
        model,
        samples,
        member: members[2],
        region,
      }),
    ).toBe('carrier');
    expect(
      interpretSampleHaplotypeRisk({
        model,
        samples,
        member: members[3],
        region,
      }),
    ).toBe('unaffected_non_carrier');
  });

  it('returns uninformative for a recessive embryo when only one side resolves (donor/unknown side)', () => {
    // Single-parent / donor PGT: only the known parent's (paternal) risk haplotype
    // can be resolved; the donor (maternal) side is unknown. A recessive call needs
    // BOTH sides, so the embryo must fall back to uninformative — never a confident
    // "at risk"/"clear" — even though the model carries a paternal signature.
    const members: HaplotypeMemberLike[] = [
      { sample_id: 'PROBAND', role: 'proband', affected: true, sex: 'female' },
      { sample_id: 'EMBRYO', role: 'embryo', affected: false, sex: 'female' },
    ];
    const samples: HaplotypeSampleLike[] = [
      // maternal lane non-informative ('.') -> only the paternal side resolves
      { sample: 'PROBAND', segments: [{ chr: '1', start: 0, end: 100, hap1: '1', hap2: '.' }] },
      { sample: 'EMBRYO', segments: [{ chr: '1', start: 0, end: 100, hap1: '1', hap2: '0' }] },
    ];

    const model = inferDiseaseHaplotypes({ samples, members, inheritanceModel: 'AR', region });

    expect(model.signatures.map((s) => s.kind)).toEqual(['recessive-paternal']);
    expect(
      interpretSampleHaplotypeRisk({ model, samples, member: members[1], region }),
    ).toBe('uninformative');
  });

  it('handles X-linked recessive male hemizygosity and carrier females', () => {
    const xRegion = { chr: 'X', start: 40, end: 60 };
    const members: HaplotypeMemberLike[] = [
      {
        sample_id: 'AFFECTED_SON',
        role: 'proband',
        affected: true,
        sex: 'male',
      },
      {
        sample_id: 'CARRIER_DAUGHTER',
        role: 'sibling',
        affected: false,
        sex: 'female',
        carrier_status: 'carrier',
      },
      { sample_id: 'CLEAR_SON', role: 'sibling', affected: false, sex: 'male' },
    ];
    const samples: HaplotypeSampleLike[] = [
      {
        sample: 'AFFECTED_SON',
        segments: [{ chr: 'X', start: 0, end: 100, hap1: '0', hap2: '1' }],
      },
      {
        sample: 'CARRIER_DAUGHTER',
        segments: [{ chr: 'X', start: 0, end: 100, hap1: '0', hap2: '1' }],
      },
      {
        sample: 'CLEAR_SON',
        segments: [{ chr: 'X', start: 0, end: 100, hap1: '0', hap2: '0' }],
      },
    ];

    const model = inferDiseaseHaplotypes({
      samples,
      members,
      inheritanceModel: 'XLR',
      region: xRegion,
    });

    expect(model.signatures).toEqual([{ origin: 'maternal', value: '1', kind: 'x-linked' }]);
    expect(getRenderableHaplotypeLanes(members[0], samples[0].segments[0], 'X')).toEqual(['hap2']);
    expect(
      interpretSampleHaplotypeRisk({
        model,
        samples,
        member: members[0],
        region: xRegion,
      }),
    ).toBe('affected_or_at_risk');
    expect(
      interpretSampleHaplotypeRisk({
        model,
        samples,
        member: members[1],
        region: xRegion,
      }),
    ).toBe('carrier');
    expect(
      interpretSampleHaplotypeRisk({
        model,
        samples,
        member: members[2],
        region: xRegion,
      }),
    ).toBe('unaffected_non_carrier');
  });
});

describe('pedigree-aware lineage tags override role-based origin', () => {
  // co620: the paternal grandmother is stored with role "mother" but the backend
  // tags her shared homolog paternal and her other homolog untransmitted.
  const grandmother: HaplotypeMemberLike = { sample_id: 'GM', role: 'mother', affected: true, sex: 'female' };

  it('uses the lineage tag, not the role, to pick the origin', () => {
    const seg = {
      chr: '1',
      start: 0,
      end: 100,
      hap1: '0',
      hap2: '1',
      hap1_lineage: 'untransmitted',
      hap2_lineage: 'paternal',
    };
    // hap2 is the shared paternal homolog (light blue, shade 1) despite role "mother".
    expect(getHaplotypeLaneSignature(grandmother, seg, 'hap2', '1')).toEqual({ origin: 'paternal', value: '1' });
    // hap1 is untransmitted -> no signature -> rendered grey.
    expect(getHaplotypeLaneSignature(grandmother, seg, 'hap1', '1')).toBeNull();
  });

  it('falls back to role-based origin when no lineage tag is present', () => {
    const seg = { chr: '1', start: 0, end: 100, hap1: '0', hap2: '1' };
    // role "mother" -> both lanes maternal (the legacy behaviour, still used for
    // the nuclear core and for un-tagged data).
    expect(getHaplotypeLaneSignature(grandmother, seg, 'hap1', '1')).toEqual({ origin: 'maternal', value: '0' });
    expect(getHaplotypeLaneSignature(grandmother, seg, 'hap2', '1')).toEqual({ origin: 'maternal', value: '1' });
  });

  it('infers the dominant disease haplotype from an affected father + lineage-tagged grandmother', () => {
    const members: HaplotypeMemberLike[] = [
      { sample_id: 'FATHER', role: 'father', affected: true, sex: 'male' },
      grandmother,
    ];
    const samples: HaplotypeSampleLike[] = [
      { sample: 'FATHER', segments: [{ chr: '1', start: 0, end: 100, hap1: '0', hap2: '1' }] },
      {
        sample: 'GM',
        segments: [
          {
            chr: '1',
            start: 0,
            end: 100,
            hap1: '0',
            hap2: '1',
            hap1_lineage: 'untransmitted',
            hap2_lineage: 'paternal',
          },
        ],
      },
    ];
    const model = inferDiseaseHaplotypes({ samples, members, inheritanceModel: 'AD', region });
    // The shared paternal homolog (shade 1, light blue) carries the dominant allele.
    expect(model.signatures).toEqual([{ origin: 'paternal', value: '1', kind: 'dominant' }]);
  });

  it('does not let a fully-greyed affected relative collapse a resolvable dominant call', () => {
    // Regression for the intersection-collapse bug: the affected father + affected
    // proband co-segregate paternal:0, so the dominant call must resolve. An affected
    // relative the lineage service greyed on BOTH lanes (e.g. the co620 grandmother on
    // an autosome where IBD matching failed the gates, or any non-autosome) yields ZERO
    // in-region signatures. She must be treated as NON-informative for the intersection,
    // not as a hard zero that wipes the whole disease-haplotype call.
    const father: HaplotypeMemberLike = { sample_id: 'FATHER', role: 'father', affected: true, sex: 'male' };
    const proband: HaplotypeMemberLike = { sample_id: 'PROBAND', role: 'proband', affected: true, sex: 'female' };
    const greyedRelative: HaplotypeMemberLike = { sample_id: 'GM', role: 'mother', affected: true, sex: 'female' };
    const members = [father, proband, greyedRelative];
    const baseSamples: HaplotypeSampleLike[] = [
      { sample: 'FATHER', segments: [{ chr: '1', start: 0, end: 100, hap1: '0', hap2: '1' }] },
      { sample: 'PROBAND', segments: [{ chr: '1', start: 0, end: 100, hap1: '0', hap2: '1' }] },
    ];

    // Father + proband alone resolve paternal:0.
    const baseModel = inferDiseaseHaplotypes({
      samples: baseSamples,
      members: [father, proband],
      inheritanceModel: 'AD',
      region,
    });
    expect(baseModel.signatures).toEqual([{ origin: 'paternal', value: '0', kind: 'dominant' }]);
    expect(baseModel.informative).toBe(true);

    // Adding the greyed affected relative (both lanes untransmitted/unknown) must NOT
    // wipe the call.
    const withGreyed = inferDiseaseHaplotypes({
      samples: [
        ...baseSamples,
        {
          sample: 'GM',
          segments: [
            {
              chr: '1',
              start: 0,
              end: 100,
              hap1: '0',
              hap2: '1',
              hap1_lineage: 'unknown',
              hap2_lineage: 'untransmitted',
            },
          ],
        },
      ],
      members,
      inheritanceModel: 'AD',
      region,
    });
    expect(withGreyed.informative).toBe(true);
    expect(withGreyed.signatures).toEqual([{ origin: 'paternal', value: '0', kind: 'dominant' }]);
  });

  it('still resolves a recessive side when one affected member is greyed on that side', () => {
    // The per-origin intersection has the same collapse hazard. An affected proband
    // resolves recessive paternal:1 / maternal:0; an affected relative greyed on both
    // lanes must not zero the per-origin intersection.
    const proband: HaplotypeMemberLike = { sample_id: 'PROBAND', role: 'proband', affected: true, sex: 'female' };
    const greyedRelative: HaplotypeMemberLike = { sample_id: 'AUNT', role: 'mother', affected: true, sex: 'female' };
    const model = inferDiseaseHaplotypes({
      samples: [
        { sample: 'PROBAND', segments: [{ chr: '1', start: 0, end: 100, hap1: '1', hap2: '0' }] },
        {
          sample: 'AUNT',
          segments: [
            {
              chr: '1',
              start: 0,
              end: 100,
              hap1: '0',
              hap2: '1',
              hap1_lineage: 'untransmitted',
              hap2_lineage: 'unknown',
            },
          ],
        },
      ],
      members: [proband, greyedRelative],
      inheritanceModel: 'AR',
      region,
    });
    expect(model.signatures).toEqual([
      { origin: 'paternal', value: '1', kind: 'recessive-paternal' },
      { origin: 'maternal', value: '0', kind: 'recessive-maternal' },
    ]);
  });
});
