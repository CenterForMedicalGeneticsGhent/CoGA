import { describe, expect, it } from 'vitest';
import {
  classifyEmbryosAtRoi,
  hasRecombinationNearRoi,
  type EmbryoClassification,
} from '../embryoSegregation';
import type { HaplotypeMemberLike, HaplotypeSampleLike } from '../haplotypeRisk';

const region = { chr: '1', start: 1_000_000, end: 1_001_000 };

const seg = (
  hap1: string,
  hap2: string,
  hap1_lineage = 'paternal',
  hap2_lineage = 'maternal',
  start = 0,
  end = 2_000_000,
) => ({ chr: '1', start, end, hap1, hap2, hap1_lineage, hap2_lineage });

const byId = (rows: EmbryoClassification[]) => Object.fromEntries(rows.map((r) => [r.sampleId, r]));

describe('classifyEmbryosAtRoi (dominant)', () => {
  const members: HaplotypeMemberLike[] = [
    { sample_id: 'FATHER', role: 'father', affected: true, sex: 'male' },
    { sample_id: 'PROBAND', role: 'proband', affected: true, sex: 'female' },
    { sample_id: 'E_RISK', role: 'embryo', affected: false, sex: 'female' },
    { sample_id: 'E_CLEAR', role: 'embryo', affected: false, sex: 'female' },
  ];
  const samples: HaplotypeSampleLike[] = [
    { sample: 'FATHER', segments: [seg('0', '1', 'paternal', 'paternal')] },
    { sample: 'PROBAND', segments: [seg('1', '0')] }, // shares paternal:1 with father -> disease hap
    { sample: 'E_RISK', segments: [seg('1', '1')] }, // inherited paternal:1 -> at risk
    { sample: 'E_CLEAR', segments: [seg('0', '1')] }, // inherited paternal:0 -> unaffected
  ];

  it('classifies each embryo by the shared dominant haplotype', () => {
    const out = byId(classifyEmbryosAtRoi({ members, samples, inheritanceModel: 'AD', region }));
    expect(Object.keys(out).sort()).toEqual(['E_CLEAR', 'E_RISK']);
    expect(out.E_RISK.state).toBe('affected_or_at_risk');
    expect(out.E_CLEAR.state).toBe('unaffected_non_carrier');
    expect(out.E_RISK.recombinationNearRoi).toBe(false);
    expect(out.E_RISK.uninformative).toBe(false);
  });

  it('flags uninformative when the disease haplotype cannot be resolved', () => {
    // A single affected member with a homozygous block is ambiguous -> uninformative.
    const lone: HaplotypeMemberLike[] = [
      { sample_id: 'PROBAND', role: 'proband', affected: true, sex: 'female' },
      { sample_id: 'E1', role: 'embryo', affected: false, sex: 'female' },
    ];
    const loneSamples: HaplotypeSampleLike[] = [
      { sample: 'PROBAND', segments: [seg('1', '1')] },
      { sample: 'E1', segments: [seg('1', '0')] },
    ];
    const out = byId(classifyEmbryosAtRoi({ members: lone, samples: loneSamples, inheritanceModel: 'AD', region }));
    expect(out.E1.state).toBe('uninformative');
    expect(out.E1.uninformative).toBe(true);
  });
});

describe('hasRecombinationNearRoi', () => {
  it('flags a block boundary inside the ROI', () => {
    const segs = [
      seg('1', '1', 'paternal', 'maternal', 0, 1_000_500),
      seg('0', '1', 'paternal', 'maternal', 1_000_500, 2_000_000), // crossover at 1,000,500 (inside ROI)
    ];
    expect(hasRecombinationNearRoi(segs, region)).toBe(true);
  });

  it('does not flag a boundary far from the ROI', () => {
    const segs = [
      seg('1', '1', 'paternal', 'maternal', 0, 500_000),
      seg('0', '1', 'paternal', 'maternal', 500_000, 2_000_000), // crossover at 500k, >250k from ROI
    ];
    expect(hasRecombinationNearRoi(segs, region)).toBe(false);
  });
});
