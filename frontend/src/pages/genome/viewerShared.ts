import type { ApiFamilyRegionOfInterest } from '../../lib/apiTypes';

export const CHROMS = [
  ...Array.from({ length: 22 }, (_, i) => String(i + 1)),
  'X',
  'Y',
  'MT',
];

export const DEFAULT_TRACK_WIDTH = 1200;
export const TRACK_WIDTH_PADDING = 32;

export const formatBp = (bp: number): string => {
  if (bp >= 1_000_000) return `${(bp / 1_000_000).toFixed(2)} Mb`;
  if (bp >= 1_000) return `${(bp / 1_000).toFixed(2)} kb`;
  return `${bp} bp`;
};

export const normalizeChrom = (value: string): string => {
  const stripped = value.trim().replace(/^chr/i, '');
  if (/^m(t)?$/i.test(stripped)) return 'MT';
  if (/^\d+$/.test(stripped)) return String(Number(stripped));
  return stripped.toUpperCase();
};

export const formatChromosomeLabel = (value: string): string => {
  const chrom = normalizeChrom(value);
  return chrom === 'MT' ? 'chrM' : `chr${chrom}`;
};

export const formatRoiCoordinates = (roi: ApiFamilyRegionOfInterest): string => {
  return `${formatChromosomeLabel(roi.chr)}:${roi.start.toLocaleString()}-${roi.end.toLocaleString()}`;
};

export const buildTrackFilterSummary = (
  variantFilters: Record<string, string>,
  sampleFilter?: string,
): string | null => {
  const parts = [
    ...Object.entries(variantFilters).map(([key, value]) => `${key}=${value}`),
    sampleFilter ? `sample_filter=${sampleFilter}` : null,
  ].filter(Boolean);

  return parts.length ? parts.join(', ') : null;
};
