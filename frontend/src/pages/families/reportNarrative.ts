// Pure text-generation helpers that turn a reviewed small variant into the
// full-sentence prose used by the family report template. Kept free of React so
// the wording can be unit-tested in isolation.

import { ACMG_CRITERIA_BY_CODE, STRENGTH_LABELS, type AcmgStrength } from '../../lib/acmg';
import { formatLocus } from './smallVariantResultUtils';
import type { FamilyMember, SmallVariant } from './smallVariantSearch';

export type Zygosity =
  | 'homozygous'
  | 'heterozygous'
  | 'hemizygous'
  | 'reference'
  | 'unknown';

const parseGenotype = (gt?: string): string[] => {
  if (!gt) return [];
  return gt
    .split(/[/|]/)
    .map((allele) => allele.trim())
    .filter((allele) => allele.length > 0);
};

export const describeZygosity = (gt?: string): Zygosity => {
  const alleles = parseGenotype(gt);
  if (alleles.length === 0 || alleles.every((allele) => allele === '.')) {
    return 'unknown';
  }
  const altAlleles = alleles.filter((allele) => allele !== '0' && allele !== '.');
  if (altAlleles.length === 0) {
    return 'reference';
  }
  if (alleles.length === 1) {
    return 'hemizygous';
  }
  if (altAlleles.length === alleles.length) {
    return 'homozygous';
  }
  return 'heterozygous';
};

// Human-friendly consequence: "missense_variant&splice_region_variant" →
// "missense variant / splice region variant".
export const humanizeEffect = (effect?: string): string => {
  if (!effect) return 'sequence variant';
  return effect
    .split(/[&,]/)
    .map((part) => part.trim().replace(/_/g, ' '))
    .filter(Boolean)
    .join(' / ');
};

const formatAlleleFrequency = (value: number): string => {
  if (value === 0) return '0';
  if (value < 0.0001) return value.toExponential(2);
  const fixed = value.toFixed(5).replace(/0+$/, '').replace(/\.$/, '');
  return fixed || String(value);
};

export const describeGnomadFrequency = (variant: SmallVariant): string => {
  const af = variant.gnomad_af;
  if (af === undefined || af === null) {
    return 'has no reported gnomAD allele frequency';
  }
  if (af === 0) {
    return 'is absent from gnomAD';
  }
  const freq = formatAlleleFrequency(af);
  const hom =
    variant.gnomad_hom_count && variant.gnomad_hom_count > 0
      ? ` with ${variant.gnomad_hom_count} homozygote${variant.gnomad_hom_count === 1 ? '' : 's'}`
      : '';
  if (af < 0.0001) {
    return `is extremely rare in gnomAD (allele frequency ${freq}${hom})`;
  }
  if (af < 0.01) {
    return `is rare in gnomAD (allele frequency ${freq}${hom})`;
  }
  return `is present in gnomAD at an allele frequency of ${freq}${hom}`;
};

export type InSilicoPrediction = { label: string; value: string };

export const collectInSilicoPredictions = (variant: SmallVariant): InSilicoPrediction[] => {
  const predictions: InSilicoPrediction[] = [];
  if (variant.cadd_phred !== undefined && variant.cadd_phred !== null) {
    predictions.push({ label: 'CADD', value: variant.cadd_phred.toFixed(1) });
  }
  if (variant.revel !== undefined && variant.revel !== null) {
    predictions.push({ label: 'REVEL', value: variant.revel.toFixed(3) });
  }
  if (variant.sift) {
    predictions.push({ label: 'SIFT', value: variant.sift });
  }
  if (variant.polyphen) {
    predictions.push({ label: 'PolyPhen', value: variant.polyphen });
  }
  if (variant.spliceai_max !== undefined && variant.spliceai_max !== null) {
    predictions.push({ label: 'SpliceAI', value: variant.spliceai_max.toFixed(2) });
  }
  return predictions;
};

export const describeInSilico = (variant: SmallVariant): string => {
  const predictions = collectInSilicoPredictions(variant);
  if (predictions.length === 0) {
    return 'No in silico pathogenicity predictions were available for this variant.';
  }
  const parts = predictions.map((prediction) => `${prediction.label} ${prediction.value}`);
  return `In silico predictors report ${joinWithAnd(parts)}.`;
};

export const describeClinvar = (variant: SmallVariant): string | null => {
  const clinvar = variant.clinvar?.trim();
  if (!clinvar) return null;
  return `ClinVar reports this variant as ${clinvar.replace(/_/g, ' ')}.`;
};

const memberLabel = (member: FamilyMember): string => {
  const role = (member.role || '').trim();
  if (role) {
    return `${role} (${member.sample_id})`;
  }
  return member.sample_id;
};

const isAffected = (member: FamilyMember): boolean =>
  Boolean(member.affected) || member.clinical_status === 'affected';

const findProband = (members: FamilyMember[]): FamilyMember | undefined =>
  members.find((member) => (member.role || '').toLowerCase() === 'proband') ??
  members.find(isAffected) ??
  members[0];

const genotypeForSample = (variant: SmallVariant, sampleId: string): string | undefined =>
  variant.genotypes.find((genotype) => genotype.sample === sampleId)?.gt;

// "A heterozygous missense variant, BRCA1 c.123A>G (p.Lys41Arg), was identified
//  at chr17:43,000,000 (rs123) in the proband (S1)."
export const buildVariantSentence = (
  variant: SmallVariant,
  members: FamilyMember[],
): string => {
  const gene = variant.gene || variant.gene_id || 'an intergenic region';
  const effect = humanizeEffect(variant.effect);
  const proband = findProband(members);
  const probandGt = proband ? genotypeForSample(variant, proband.sample_id) : undefined;
  const zygosity = describeZygosity(probandGt);
  const zygosityWord = zygosity === 'unknown' || zygosity === 'reference' ? '' : `${zygosity} `;

  const hgvs = [variant.hgvsc, variant.hgvsp ? `(${variant.hgvsp})` : '']
    .filter(Boolean)
    .join(' ');
  const variantName = [gene, hgvs].filter(Boolean).join(' ');
  const rsid = variant.rsid ? ` (${variant.rsid})` : '';
  const probandClause = proband ? ` in the ${memberLabel(proband)}` : '';

  return `A ${zygosityWord}${effect}, ${variantName}, was identified at ${formatLocus(
    variant,
  )}${rsid}${probandClause}.`;
};

export const buildSegregationSentence = (
  variant: SmallVariant,
  members: FamilyMember[],
): string | null => {
  if (members.length === 0) return null;
  const clauses = members
    .map((member) => {
      const zygosity = describeZygosity(genotypeForSample(variant, member.sample_id));
      const affected = isAffected(member) ? 'affected' : 'unaffected';
      const call =
        zygosity === 'unknown'
          ? 'no confident call'
          : zygosity === 'reference'
            ? 'wild-type'
            : zygosity;
      return `${call} in the ${affected} ${memberLabel(member)}`;
    })
    .filter(Boolean);
  if (clauses.length === 0) return null;
  return `Within the family, the variant is ${joinWithAnd(clauses)}.`;
};

export type ReportCriterion = {
  code: string;
  name: string;
  description: string;
  direction: 'pathogenic' | 'benign';
  strengthLabel: string;
  evidence?: string | null;
};

export const collectReportCriteria = (variant: SmallVariant): ReportCriterion[] => {
  const criteria = variant.review?.acmg?.criteria ?? [];
  return criteria
    .filter((criterion) => criterion.accepted)
    .map((criterion) => {
      const def = ACMG_CRITERIA_BY_CODE[criterion.code as keyof typeof ACMG_CRITERIA_BY_CODE];
      const strengthLabel = STRENGTH_LABELS[criterion.strength as AcmgStrength] || criterion.strength;
      return {
        code: criterion.code,
        name: def?.name ?? criterion.code,
        description: def?.description ?? '',
        direction: def?.direction ?? 'pathogenic',
        strengthLabel,
        evidence: criterion.evidence,
      } satisfies ReportCriterion;
    });
};

export const acmgClassificationLabel = (variant: SmallVariant): string | null =>
  variant.review?.acmg?.classification ?? variant.review?.classification ?? null;

// Joins ["a", "b", "c"] → "a, b and c"; ["a", "b"] → "a and b".
export function joinWithAnd(items: string[]): string {
  const filtered = items.filter(Boolean);
  if (filtered.length === 0) return '';
  if (filtered.length === 1) return filtered[0];
  if (filtered.length === 2) return `${filtered[0]} and ${filtered[1]}`;
  return `${filtered.slice(0, -1).join(', ')} and ${filtered[filtered.length - 1]}`;
}
