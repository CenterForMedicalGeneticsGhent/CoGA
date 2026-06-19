// ClinGen 2019 copy-number variant (CNV) classification types.
// Kept in parity with the backend engine in
// backend/app/services/cnv_acmg_points.py.

export type CnvKind = 'loss' | 'gain';

export interface CnvCriterionDef {
  code: string;
  name: string;
  /** ClinGen evidence section: '1' | '2' | '3' | '4' | '5'. */
  section: string;
  defaultPoints: number;
  minPoints: number;
  maxPoints: number;
}

export interface CnvSuggestion {
  code: string;
  points: number;
  evidence?: string;
}

/** Analyst working state for a single criterion in the modal. */
export interface CnvSelection {
  code: string;
  points: number;
  accepted: boolean;
  evidence?: string;
  autoSuggested: boolean;
}

export interface CnvClassification {
  pointTotal: number;
  classKey: string;
  classLabel: string;
}
