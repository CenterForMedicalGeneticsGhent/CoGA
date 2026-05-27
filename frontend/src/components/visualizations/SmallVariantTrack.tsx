import React from 'react';
import { useQuery } from '@tanstack/react-query';
import * as d3 from 'd3';
import api from '../../lib/api';
import type { ApiVariantPage } from '../../lib/apiTypes';
import { formatGt } from '../../lib/genotypes';
import { cssVar } from '../../lib/colors';
import {
  SMALL_VARIANT_TRACK_RESULT_LIMIT,
  shouldShowSmallVariantDetails,
} from '../../lib/trackSampling';
import VizLoadingOverlay from './VizLoadingOverlay';

interface Genotype {
  sample: string;
  gt: string;
}

interface SmallVariantReview {
  tags?: string[];
}

interface Variant {
  chr: string;
  start: number;
  end: number;
  type: string;
  ref?: string;
  alt?: string;
  clinvar?: string | null;
  genotypes?: Genotype[];
  review?: SmallVariantReview | null;
}

interface TagDefinition {
  key: string;
  color?: string | null;
}

interface Props {
  familyId: string;
  sampleId: string;
  chrom: string;
  regionStart: number;
  regionEnd: number;
  width: number;
  height: number;
  filters?: Record<string, string>;
}

const NON_REFERENCE_GENOTYPES = ['0/1', '1/0', '0|1', '1|0', '1/1', '1|1'];

const samplePresenceFilter = (sampleId: string) =>
  `${sampleId}:${NON_REFERENCE_GENOTYPES.join('|')}`;

const hasActiveFilterValue = (value: unknown): boolean => {
  if (Array.isArray(value)) return value.some(hasActiveFilterValue);
  return String(value ?? '').trim().length > 0;
};

const CLINVAR_COLORS = {
  pathogenic: '#b42318',
  likelyPathogenic: '#ea580c',
  benign: '#2f855a',
  uncertain: '#ca8a04',
} as const;

const normalizeClinvar = (clinvar?: string | null): string =>
  (clinvar || '')
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

const getClinvarColor = (clinvar?: string | null): string | undefined => {
  const value = normalizeClinvar(clinvar);
  if (!value) return undefined;
  if (value.includes('likely pathogenic')) return CLINVAR_COLORS.likelyPathogenic;
  if (
    value === 'pathogenic' ||
    value.includes('pathogenic/likely pathogenic') ||
    value.includes('pathogenic and')
  ) {
    return CLINVAR_COLORS.pathogenic;
  }
  if (
    value.includes('benign') ||
    value.includes('likely benign') ||
    value.includes('benign/likely benign')
  ) {
    return CLINVAR_COLORS.benign;
  }
  if (
    value.includes('vus') ||
    value.includes('uncertain significance') ||
    value.includes('conflicting')
  ) {
    return CLINVAR_COLORS.uncertain;
  }
  return undefined;
};

const SmallVariantTrack: React.FC<Props> = ({
  familyId,
  sampleId,
  chrom,
  regionStart,
  regionEnd,
  width,
  height,
  filters,
}) => {
  const pageSize = SMALL_VARIANT_TRACK_RESULT_LIMIT - 1;
  const hasUserFilters = React.useMemo(
    () => Object.values(filters || {}).some(hasActiveFilterValue),
    [filters],
  );
  const regionRestricted = React.useMemo(
    () => shouldShowSmallVariantDetails(regionEnd - regionStart),
    [regionEnd, regionStart],
  );
  const canRequestSmallVariants =
    regionEnd > regionStart && (hasUserFilters || regionRestricted);
  const requestFilters = React.useMemo(() => {
    const nextFilters = { ...(filters || {}) };
    if (!nextFilters.sample_filter) {
      nextFilters.sample_filter = samplePresenceFilter(sampleId);
    }
    return nextFilters;
  }, [filters, sampleId]);
  const { data, isLoading } = useQuery<ApiVariantPage<Variant>>({
    queryKey: [
      'small-variants-track',
      familyId,
      sampleId,
      chrom,
      regionStart,
      regionEnd,
      pageSize,
      requestFilters,
    ],
    queryFn: async () => {
      const params: Record<string, any> = {
        chr: chrom,
        start: regionStart,
        end: regionEnd,
        overlap: true,
        page_size: pageSize,
        track_mode: true,
        track_result_limit: SMALL_VARIANT_TRACK_RESULT_LIMIT,
        ...requestFilters,
      };
      const res = await api.get(`/families/${familyId}/small-variants`, {
        params,
      });
      return res.data as ApiVariantPage<Variant>;
    },
    enabled: canRequestSmallVariants,
  });
  const { data: tagDefinitions = [] } = useQuery<TagDefinition[]>({
    queryKey: ['small-variant-track-tags', familyId],
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/small-variant-tags`);
      return res.data as TagDefinition[];
    },
    enabled: canRequestSmallVariants,
  });

  const tooManyVariants =
    !canRequestSmallVariants ||
    Boolean(
      data &&
        (data.total_is_estimated ||
          data.total >= SMALL_VARIANT_TRACK_RESULT_LIMIT ||
          (data.count_limit != null && data.total >= data.count_limit)),
    );
  const tagColorMap = React.useMemo(() => {
    if (!Array.isArray(tagDefinitions)) return {};
    return Object.fromEntries(
      tagDefinitions
        .filter((tag) => tag.key && tag.color)
        .map((tag) => [tag.key, tag.color as string]),
    );
  }, [tagDefinitions]);

  const variants = React.useMemo(
    () =>
      (tooManyVariants ? [] : data?.variants || []).filter((v) =>
        v.genotypes?.some(
          (g) => g.sample === sampleId && formatGt(g.gt) !== 'WT'
        )
      ),
    [data?.variants, sampleId, tooManyVariants]
  );

  const span = regionEnd - regionStart || 1;
  const withPos = React.useMemo(
    () =>
      variants.map((v) => {
        const x = ((v.start - regionStart) / span) * width;
        return { ...v, x };
      }),
    [variants, regionStart, span, width]
  );

  const typeColors = React.useMemo<Record<string, string>>(
    () => ({
      SNV: cssVar('--color-variant-default'),
      INDEL: cssVar('--color-variant-ins'),
      DEL: cssVar('--color-variant-del'),
      INS: cssVar('--color-variant-ins'),
    }),
    []
  );
  const getVariantColor = React.useCallback(
    (variant: Variant) => {
      const tagColor = variant.review?.tags
        ?.map((tagKey) => tagColorMap[tagKey])
        .find(Boolean);
      if (tagColor) return tagColor;
      return (
        getClinvarColor(variant.clinvar) ||
        typeColors[variant.type?.toUpperCase()] ||
        cssVar('--color-variant-default')
      );
    },
    [tagColorMap, typeColors],
  );
  const emptyMessage = tooManyVariants
    ? 'Too many variants to display. Zoom in or apply filters.'
    : 'no small variants for this region / sample';

  const svgRef = React.useRef<SVGSVGElement | null>(null);

  React.useEffect(() => {
    if (isLoading) {
      return;
    }

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    if (withPos.length === 0) {
      svg
        .append('text')
        .attr('x', 4)
        .attr('y', height / 2 + 4)
        .attr('font-size', 12)
        .attr('fill', cssVar('--color-variant-default'))
        .text(emptyMessage);
      return;
    }

    const g = svg.append('g');
    withPos.forEach((v) => {
      g
        .append('line')
        .attr('x1', v.x)
        .attr('x2', v.x)
        .attr('y1', 0)
        .attr('y2', height)
        .attr('stroke', getVariantColor(v));
    });
  }, [withPos, height, getVariantColor, emptyMessage, isLoading]);

  return (
    <div className="relative" style={{ width, height }}>
      <svg ref={svgRef} width={width} height={height} />
      {isLoading && <VizLoadingOverlay message="Loading small variants" />}
    </div>
  );
};

export default SmallVariantTrack;
