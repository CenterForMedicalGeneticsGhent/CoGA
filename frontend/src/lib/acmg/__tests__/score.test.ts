import { describe, expect, it } from 'vitest';

import { computeClassification } from '../score';
import type { AcmgSelection, AcmgStrength, AcmgCriterionCode } from '../types';

function sel(
  code: AcmgCriterionCode,
  strength: AcmgStrength,
  accepted = true,
): AcmgSelection {
  return { code, strength, accepted, autoSuggested: false };
}

describe('computeClassification', () => {
  it('returns VUS at 0 points with no selections', () => {
    const result = computeClassification([]);
    expect(result.points).toBe(0);
    expect(result.classKey).toBe('acmg_class_3');
  });

  it('only counts accepted selections', () => {
    const result = computeClassification([sel('PVS1', 'very_strong', false)]);
    expect(result.points).toBe(0);
    expect(result.classKey).toBe('acmg_class_3');
  });

  it('PVS1 (8) + PM2 (1) = 9 → Likely Pathogenic', () => {
    const result = computeClassification([sel('PVS1', 'very_strong'), sel('PM2', 'supporting')]);
    expect(result.points).toBe(9);
    expect(result.classKey).toBe('acmg_class_4');
  });

  it('PVS1 (8) + PM2 moderate (2) = 10 → Pathogenic', () => {
    const result = computeClassification([sel('PVS1', 'very_strong'), sel('PM2', 'moderate')]);
    expect(result.points).toBe(10);
    expect(result.classKey).toBe('acmg_class_5');
  });

  it('two benign supporting (-2) → Likely benign', () => {
    const result = computeClassification([sel('BP4', 'supporting'), sel('BP7', 'supporting')]);
    expect(result.points).toBe(-2);
    expect(result.classKey).toBe('acmg_class_2');
  });

  it('benign strong + supporting (-5) stays Likely benign; -7 tips to Benign', () => {
    expect(
      computeClassification([sel('BS1', 'strong'), sel('BP4', 'supporting')]).classKey,
    ).toBe('acmg_class_2');
    expect(
      computeClassification([sel('BS1', 'strong'), sel('BS2', 'strong')]).classKey,
    ).toBe('acmg_class_1');
  });

  it('mixed pathogenic and benign evidence nets toward VUS', () => {
    const result = computeClassification([sel('PVS1', 'very_strong'), sel('BS1', 'strong')]);
    expect(result.points).toBe(4);
    expect(result.classKey).toBe('acmg_class_3');
  });

  it('BA1 forces Benign regardless of point total', () => {
    const result = computeClassification([
      sel('BA1', 'stand_alone'),
      sel('PVS1', 'very_strong'),
      sel('PM2', 'moderate'),
    ]);
    expect(result.standAloneBenign).toBe(true);
    expect(result.classKey).toBe('acmg_class_1');
  });
});
