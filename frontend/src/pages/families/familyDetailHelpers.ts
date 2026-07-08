import type {
  ApiFamilyRecord,
  ApiFamilyRegionOfInterest,
  ApiHpoAnnotation,
  ApiHpoTerm,
} from '../../lib/apiTypes';
import { sortTagDefinitions, type SmallVariantTagDefinition } from './smallVariantSearch';
import type {
  CarrierStatus,
  ClinicalStatus,
  CoupleDraft,
  ParentChildDraft,
  PedRow,
  StructureMemberDraft,
} from './familyDetailTypes';
import { ROLE_OPTIONS } from './familyDetailConstants';

export const parsePedigree = (pedigree?: string | null): PedRow[] => {
  if (!pedigree) return [];
  return pedigree
    .split('\n')
    .filter((line) => line.trim())
    .map((line) => {
      const [fid, iid, pid, mid, sex, phen] = line.trim().split(/\s+/);
      return { fid, iid, pid, mid, sex, phen };
    });
};

export const sampleKey = (sampleId: string): string => sampleId.trim().toLowerCase();

export const formatHpoTermOption = (term: ApiHpoTerm): string => `${term.hpo_id} ${term.label}`;

export const clinicalStatusForMember = (member: {
  clinical_status?: string | null;
  affected?: boolean;
}): ClinicalStatus => {
  if (member.clinical_status === 'affected' || member.clinical_status === 'unaffected') {
    return member.clinical_status;
  }
  if (member.affected) return 'affected';
  return 'unknown';
};

export const carrierStatusForMember = (member: {
  carrier_status?: string | boolean | null;
}): CarrierStatus => {
  if (member.carrier_status === 'carrier') return 'carrier';
  if (member.carrier_status === 'not_carrier') return 'not_carrier';
  if (member.carrier_status === true) return 'carrier';
  return 'unknown';
};

export const hpoTooltip = (annotation: ApiHpoAnnotation): string => {
  return [
    `${annotation.hpo_id}: ${annotation.definition || annotation.label}`,
    annotation.note ? `Note: ${annotation.note}` : '',
    annotation.evidence ? `Evidence: ${annotation.evidence}` : '',
  ]
    .filter(Boolean)
    .join(' | ');
};

export const memberDraftFromFamilyMember = (member: ApiFamilyRecord['members'][number]): StructureMemberDraft => ({
  sample_id: member.sample_id,
  sex: member.sex === 'male' || member.sex === 'female' ? member.sex : 'und',
  role: ROLE_OPTIONS.includes(member.role as StructureMemberDraft['role'])
    ? (member.role as StructureMemberDraft['role'])
    : 'relative',
  clinical_status: clinicalStatusForMember(member),
  carrier_status: carrierStatusForMember(member),
  carrier_type: member.carrier_type ?? '',
  isNew: false,
  removed: member.active === false,
});

export const parentChildDraftsFromRelationships = (family: ApiFamilyRecord | undefined): ParentChildDraft[] => {
  const relationships = family?.relationships?.filter(
    (relationship) => relationship.relationship_type === 'parent_child',
  );
  return (relationships || []).map((relationship, index) => ({
    id: relationship.id || `parent-child-${index}`,
    parent: relationship.sample_id_a,
    child: relationship.sample_id_b,
    parent_role:
      relationship.role_a === 'father' || relationship.role_a === 'mother'
        ? relationship.role_a
        : 'parent',
  }));
};

export const parentsForSample = (
  family: ApiFamilyRecord | undefined,
  sampleId: string,
): { father_id: string; mother_id: string } => {
  const childKey = sampleKey(sampleId);
  return (family?.relationships || []).reduce(
    (parents, relationship) => {
      if (
        relationship.relationship_type !== 'parent_child' ||
        sampleKey(relationship.sample_id_b) !== childKey
      ) {
        return parents;
      }
      if (relationship.role_a === 'father') {
        parents.father_id = relationship.sample_id_a;
      } else if (relationship.role_a === 'mother') {
        parents.mother_id = relationship.sample_id_a;
      }
      return parents;
    },
    { father_id: '', mother_id: '' },
  );
};

export const coupleDraftsFromRelationships = (family: ApiFamilyRecord | undefined): CoupleDraft[] =>
  (family?.relationships || [])
    .filter((relationship) => relationship.relationship_type === 'couple')
    .map((relationship, index) => ({
      id: relationship.id || `couple-${index}`,
      partnerA: relationship.sample_id_a,
      partnerB: relationship.sample_id_b,
      context: typeof relationship.metadata?.context === 'string' ? relationship.metadata.context : '',
    }));

export const formatRegion = (roi: ApiFamilyRegionOfInterest): string => {
  const chrom = roi.chr.startsWith('chr') ? roi.chr : `chr${roi.chr}`;
  return `${chrom}:${roi.start.toLocaleString()}-${roi.end.toLocaleString()}`;
};

export const getReviewSummaryTags = (
  tagCounts: Record<string, number> | undefined,
  tagDefinitions: SmallVariantTagDefinition[],
) => {
  const counts = tagCounts || {};
  const activeKeys = new Set<string>();
  const knownTags = sortTagDefinitions(tagDefinitions)
    .map((tag) => {
      const count = counts[tag.key] ?? 0;
      if (count <= 0) return null;
      activeKeys.add(tag.key);
      return {
        key: tag.key,
        label: tag.label,
        count,
      };
    })
    .filter((entry): entry is { key: string; label: string; count: number } => entry !== null);
  const unknownTags = Object.entries(counts)
    .filter(([key, count]) => count > 0 && !activeKeys.has(key))
    .sort(([left], [right]) => left.localeCompare(right, undefined, { sensitivity: 'base' }))
    .map(([key, count]) => ({
      key,
      label: key,
      count,
    }));
  return [...knownTags, ...unknownTags];
};
