import { describe, expect, it } from 'vitest';
import {
  diseaseHaplotypeKindForLane,
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
