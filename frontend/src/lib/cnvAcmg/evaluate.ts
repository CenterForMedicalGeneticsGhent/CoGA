// Auto-suggest ClinGen CNV evidence from the structural variant's available data.
// Conservative by design: it fires only on signals the SV payload reliably carries
// (gene overlap, gene constraint, annotated inheritance). The analyst confirms and
// completes the rest in the modal.

import { cnvCriterionMap } from './criteria';
import type { CnvKind, CnvSuggestion } from './types';

export interface CnvVariantInput {
  type?: string | null;
  gene?: string | null;
  genePli?: number | null;
  inheritance?: string | null;
}

const GAIN_TYPES = new Set(['DUP', 'GAIN', 'CNV_GAIN', 'INS']);

export const cnvKindForType = (type?: string | null): CnvKind =>
  GAIN_TYPES.has((type || '').trim().toUpperCase()) ? 'gain' : 'loss';

// Section-3 gene counting differs by event class: a deletion changes the copy
// number of every gene it spans (count all wholly/partially included genes),
// whereas inversions, translocations/breakends and insertions only alter genes
// their breakpoints disrupt (count only disrupted genes).
const DISRUPTION_ONLY_TYPES = new Set(['INV', 'BND', 'TRA', 'INS']);

export type CnvGeneCountMode = 'all' | 'disrupted';

export const cnvGeneCountMode = (type?: string | null): CnvGeneCountMode =>
  DISRUPTION_ONLY_TYPES.has((type || '').trim().toUpperCase()) ? 'disrupted' : 'all';

export const cnvGeneCountHint = (type?: string | null): string =>
  cnvGeneCountMode(type) === 'all'
    ? 'Count every protein-coding gene wholly or partially within the event.'
    : 'Count only genes disrupted by a breakpoint — fully contained genes keep their copy number for inversions, translocations and insertions.';

export const evaluateCnv = (input: CnvVariantInput): CnvSuggestion[] => {
  const kind = cnvKindForType(input.type);
  const map = cnvCriterionMap(kind);
  const out: CnvSuggestion[] = [];
  const hasGene = Boolean(input.gene && input.gene.trim());

  if (hasGene) {
    out.push({ code: '1A', points: 0, evidence: `Overlaps ${input.gene}.` });
    out.push({
      code: '3A',
      points: 0,
      evidence: `Default gene-count tier — adjust if many genes qualify. ${cnvGeneCountHint(input.type)}`,
    });
  } else {
    out.push({ code: '1B', points: -0.6, evidence: 'No protein-coding gene overlap detected.' });
  }

  const pli = input.genePli;
  if (kind === 'loss' && typeof pli === 'number' && pli >= 0.9) {
    out.push({
      code: '2H',
      points: map['2H']?.maxPoints ?? 0.15,
      evidence: `Constrained gene (pLI ${pli.toFixed(3)}) supports haploinsufficiency.`,
    });
  }

  const inh = (input.inheritance || '').toLowerCase();
  if (inh.includes('de') && inh.includes('novo')) {
    out.push({
      code: '5B',
      points: map['5B']?.maxPoints ?? 0.3,
      evidence: 'Annotated de novo (assumed — confirm with parental testing for 5A).',
    });
  } else if (
    inh.includes('maternal') ||
    inh.includes('paternal') ||
    inh.includes('inherited')
  ) {
    out.push({ code: '5F', points: 0, evidence: `Annotated as ${inh}.` });
  }

  return out;
};
