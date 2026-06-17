// Shared types for the semi-automatic ACMG/AMP variant classifier.
//
// Scoring follows the Tavtigian/ClinGen Bayesian points system: each accepted
// criterion contributes points by its applied strength (pathogenic positive,
// benign negative), and the signed sum maps onto the five ACMG classes.

export type AcmgDirection = 'pathogenic' | 'benign';

// Applied evidence strength. `stand_alone` is reserved for BA1 (gnomAD AF ≥ 5%),
// which classifies a variant Benign on its own regardless of other evidence.
export type AcmgStrength =
  | 'very_strong'
  | 'strong'
  | 'moderate'
  | 'supporting'
  | 'stand_alone';

// All 28 ACMG/AMP 2015 criterion codes.
export type AcmgCriterionCode =
  | 'PVS1'
  | 'PS1'
  | 'PS2'
  | 'PS3'
  | 'PS4'
  | 'PM1'
  | 'PM2'
  | 'PM3'
  | 'PM4'
  | 'PM5'
  | 'PM6'
  | 'PP1'
  | 'PP2'
  | 'PP3'
  | 'PP4'
  | 'PP5'
  | 'BA1'
  | 'BS1'
  | 'BS2'
  | 'BS3'
  | 'BS4'
  | 'BP1'
  | 'BP2'
  | 'BP3'
  | 'BP4'
  | 'BP5'
  | 'BP6'
  | 'BP7';

export interface AcmgCriterionDef {
  code: AcmgCriterionCode;
  direction: AcmgDirection;
  // Short human label, e.g. "Null variant in LOF gene".
  name: string;
  // One-line description of the ACMG rule.
  description: string;
  defaultStrength: AcmgStrength;
  // Strength modifiers the analyst may pick from for this criterion.
  allowedStrengths: AcmgStrength[];
  // True when the auto-evaluator can produce a data-driven suggestion for it.
  autoEvaluable: boolean;
}

// How the available data positions a criterion:
//  - 'applies'         the data supports it → auto-checked (positive)
//  - 'consider'        a weaker/uncertain signal → suggested, left unchecked
//  - 'contraindicated' the data argues against it → flagged, left unchecked (negative)
//  - 'not_applicable'  cannot apply to this variant class → disabled (excluded)
export type AcmgDisposition = 'applies' | 'consider' | 'contraindicated' | 'not_applicable';

// A criterion the auto-evaluator surfaces from the variant/gene/phenotype data.
export interface AcmgSuggestion {
  code: AcmgCriterionCode;
  // Strength the evaluator recommends (may differ from the criterion default,
  // e.g. PP3 scaled to Strong by REVEL, PM2 downgraded to Supporting).
  strength: AcmgStrength;
  // Human-readable rationale shown next to the criterion in the UI.
  evidence: string;
  disposition: AcmgDisposition;
}

// A criterion selection in the working classification. `accepted` gates whether
// it contributes points. `autoSuggested` marks an evaluator-surfaced positive,
// `contraindicated` marks a negative (data argues against), `notApplicable`
// marks a criterion the variant class rules out.
export interface AcmgSelection {
  code: AcmgCriterionCode;
  accepted: boolean;
  strength: AcmgStrength;
  evidence?: string;
  autoSuggested: boolean;
  contraindicated?: boolean;
  notApplicable?: boolean;
}

export type AcmgClassKey =
  | 'acmg_class_1'
  | 'acmg_class_2'
  | 'acmg_class_3'
  | 'acmg_class_4'
  | 'acmg_class_5';

export interface AcmgClassification {
  // Signed point total over accepted selections.
  points: number;
  classKey: AcmgClassKey;
  // Display label, e.g. "Likely Pathogenic - class 4".
  label: string;
  // True when an accepted BA1 forced the Benign call (stand-alone override).
  standAloneBenign: boolean;
}

// Minimal slice of the gene profile the evaluator needs (mirrors fields from
// GET /genes/profile `extra`). Kept local so the engine has no UI coupling.
export interface AcmgGeneContext {
  clingenDosageHaploinsufficiency?: string | null;
  // GenCC modes of inheritance for the gene, e.g. ["Autosomal recessive"].
  modesOfInheritance?: string[];
  // HPO ids associated with the gene (gene → phenotype).
  geneHpoIds?: string[];
}

// Phenotype context for PP4 (proband HPO terms observed as present).
export interface AcmgPhenotypeContext {
  probandHpoIds?: string[];
}

// One family member's genotype call for this variant (for de-novo / segregation).
export interface AcmgFamilyMemberCall {
  sampleId: string;
  role: string; // 'proband' | 'father' | 'mother' | 'sibling' | …
  affected: boolean;
  gt?: string; // VCF genotype string, e.g. '0/1', '1/1', '0/0', './.'
}

export interface AcmgFamilyContext {
  members: AcmgFamilyMemberCall[];
}
