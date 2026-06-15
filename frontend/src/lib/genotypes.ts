function isNoCall(gt?: string): boolean {
  // Missing/empty, or every allele is the VCF missing marker '.': './.', '.|.', '.'.
  if (!gt) return true;
  return gt.split(/[/|]/).every((allele) => allele === '.');
}

export function formatGt(gt?: string): string {
  if (gt === '1/1' || gt === '1|1') return 'Hom';
  if (
    gt === '1/0' ||
    gt === '0/1' ||
    gt === '1|0' ||
    gt === '0|1'
  )
    return 'Het';
  if (isNoCall(gt)) return 'No call';
  return 'WT';
}

// True only when the genotype carries at least one alt allele (Het or Hom).
// No-call and reference both return false, so carrier/presence filters must use
// this rather than `formatGt(gt) !== 'WT'` — that check now counts no-calls,
// which the backend buckets with reference.
export function hasAltAllele(gt?: string): boolean {
  const label = formatGt(gt);
  return label === 'Het' || label === 'Hom';
}
