import { describe, expect, it } from 'vitest';

import { formatGt, hasAltAllele } from '../genotypes';

describe('formatGt', () => {
  it('labels homozygous-alt genotypes', () => {
    expect(formatGt('1/1')).toBe('Hom');
    expect(formatGt('1|1')).toBe('Hom');
  });

  it('labels heterozygous genotypes regardless of allele order or phasing', () => {
    expect(formatGt('0/1')).toBe('Het');
    expect(formatGt('1/0')).toBe('Het');
    expect(formatGt('0|1')).toBe('Het');
    expect(formatGt('1|0')).toBe('Het');
  });

  it('labels reference genotypes as WT', () => {
    expect(formatGt('0/0')).toBe('WT');
    expect(formatGt('0|0')).toBe('WT');
  });

  it('labels missing/no-call genotypes distinctly, not as WT', () => {
    expect(formatGt('./.')).toBe('No call');
    expect(formatGt('.|.')).toBe('No call');
    expect(formatGt('.')).toBe('No call');
    expect(formatGt('')).toBe('No call');
    expect(formatGt(undefined)).toBe('No call');
  });
});

describe('hasAltAllele', () => {
  it('is true only for Het and Hom', () => {
    expect(hasAltAllele('1/1')).toBe(true);
    expect(hasAltAllele('0/1')).toBe(true);
    expect(hasAltAllele('1|0')).toBe(true);
  });

  it('excludes reference and no-call (matching backend carrier semantics)', () => {
    expect(hasAltAllele('0/0')).toBe(false);
    expect(hasAltAllele('./.')).toBe(false);
    expect(hasAltAllele('.')).toBe(false);
    expect(hasAltAllele('')).toBe(false);
    expect(hasAltAllele(undefined)).toBe(false);
  });
});
