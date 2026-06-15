import type { StructuralVariant } from './structuralVariantSearch';

/**
 * Primary-locus IGV + Chromosome-view links for a structural variant. Shared by
 * StructuralVariantCards and StructuralVariantTable so the locus/window/query-param
 * format stays in one place. The Table additionally renders a remote-locus (BND
 * partner) IGV link, which stays local to that component.
 */
export const buildStructuralVariantNavigation = ({
  familyId,
  linkSearch,
  projectId,
  variant,
}: {
  familyId?: string;
  linkSearch: string;
  projectId?: string;
  variant: StructuralVariant;
}) => {
  const chr = variant.chr.startsWith('chr') ? variant.chr : `chr${variant.chr}`;
  const locus = `${chr}:${Math.max(1, variant.start)}-${Math.max(variant.start, variant.end)}`;
  const backPath = `/families/${familyId}/structural-variants${linkSearch}`;
  const igvHref = `/families/${familyId}/igv?locus=${encodeURIComponent(locus)}${
    projectId ? `&project_id=${projectId}` : ''
  }&back_path=${encodeURIComponent(backPath)}`;
  const viewHref = `/families/${familyId}/chromosome/${variant.chr.replace(/^chr/, '')}?start=${Math.max(
    0,
    variant.start - 1_000_000,
  )}&end=${variant.end + 1_000_000}${linkSearch ? `&${linkSearch.slice(1)}` : ''}${
    projectId ? `&project_id=${projectId}` : ''
  }`;
  return { locus, igvHref, viewHref };
};
