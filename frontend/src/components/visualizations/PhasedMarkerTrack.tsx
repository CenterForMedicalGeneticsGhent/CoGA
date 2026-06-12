import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../lib/api';
import { cssVar } from '../../lib/colors';
import { shouldShowSmallVariantDetails } from '../../lib/trackSampling';
import {
  defaultHaplotypeRiskRegion,
  diseaseHaplotypeKindForLane,
  inferDiseaseHaplotypes,
  resolveHaplotypeInheritanceModel,
  type DiseaseHaplotypeKind,
  type HaplotypeLane,
  type HaplotypeMemberLike,
  type HaplotypeRiskRegion,
  type HaplotypeSampleLike,
} from '../../lib/haplotypeRisk';
import VizTooltip from './VizTooltip';

interface Props {
  familyId: string;
  sampleId: string;
  chrom: string;
  regionStart: number;
  regionEnd: number;
  width: number;
  height: number;
  member: HaplotypeMemberLike;
  familyMembers: HaplotypeMemberLike[];
  inheritanceModel?: string | null;
  riskRegion?: HaplotypeRiskRegion | null;
}

interface HaplotypeResponse {
  samples: HaplotypeSampleLike[];
}

interface PhasedMarker {
  pos: number;
  paternal: number | null;
  maternal: number | null;
}

interface PhasedMarkerResponse {
  samples: { sample: string; markers: PhasedMarker[] }[];
}

const PhasedMarkerTrack: React.FC<Props> = ({
  familyId,
  sampleId,
  chrom,
  regionStart,
  regionEnd,
  width,
  height,
  member,
  familyMembers,
  inheritanceModel,
  riskRegion,
}) => {
  const [tooltip, setTooltip] = React.useState<{
    x: number;
    y: number;
    node: React.ReactNode;
  } | null>(null);

  const detailVisible =
    regionEnd > regionStart && shouldShowSmallVariantDetails(regionEnd - regionStart);

  // Per-marker parent-of-origin is computed server-side (it needs every sample's
  // phased GT across the dense imputed sites) and returned per child, density-
  // binned/denoised and bounded. Shared cache key across the family's children.
  const { data: phasedData } = useQuery<PhasedMarkerResponse>({
    queryKey: ['phased-markers', familyId, chrom, regionStart, regionEnd],
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/phased-markers`, {
        params: { chr: chrom, start: regionStart, end: regionEnd },
      });
      return res.data as PhasedMarkerResponse;
    },
    enabled: detailVisible,
  });

  // Haplotype blocks — reused (same query key as HaplotypeTrack) only to infer
  // the disease model so the marker colours match the block track's overlay.
  const { data: haplotypeData } = useQuery<HaplotypeResponse>({
    queryKey: ['haplotypes', familyId, chrom, regionStart, regionEnd],
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/haplotypes`, {
        params: { chr: chrom, start: regionStart, end: regionEnd },
      });
      return res.data as HaplotypeResponse;
    },
    enabled: detailVisible,
    staleTime: Infinity,
  });

  const markers: PhasedMarker[] = React.useMemo(
    () => phasedData?.samples.find((entry) => entry.sample === sampleId)?.markers ?? [],
    [phasedData?.samples, sampleId],
  );

  const diseaseModel = React.useMemo(
    () =>
      inferDiseaseHaplotypes({
        samples: haplotypeData?.samples ?? [],
        members: familyMembers,
        inheritanceModel: resolveHaplotypeInheritanceModel(inheritanceModel, familyMembers),
        region: riskRegion ?? defaultHaplotypeRiskRegion(chrom, regionStart, regionEnd),
      }),
    [haplotypeData?.samples, familyMembers, inheritanceModel, riskRegion, chrom, regionStart, regionEnd],
  );

  if (!detailVisible) {
    return (
      <div className="relative" style={{ width, height }}>
        <svg width={width} height={height} />
        <div className="viz-empty-overlay">Zoom to ≤5 Mb to view phased markers</div>
      </div>
    );
  }

  const regionLength = regionEnd - regionStart;
  const half = height / 2;
  const fatherColors = [
    cssVar('--color-haplotype-father-dark'),
    cssVar('--color-haplotype-father-light'),
  ];
  const motherColors = [
    cssVar('--color-haplotype-mother-dark'),
    cssVar('--color-haplotype-mother-light'),
  ];
  const riskColors: Record<DiseaseHaplotypeKind, string> = {
    dominant: cssVar('--color-haplotype-dominant'),
    'recessive-maternal': cssVar('--color-haplotype-recessive-maternal'),
    'recessive-paternal': cssVar('--color-haplotype-recessive-paternal'),
    'x-linked': cssVar('--color-haplotype-x-linked'),
  };

  const laneColor = (marker: PhasedMarker, lane: HaplotypeLane): string | null => {
    const value = lane === 'hap1' ? marker.paternal : marker.maternal;
    if (value === null) return null;
    const segment = {
      chr: chrom,
      start: marker.pos,
      end: marker.pos + 1,
      hap1: marker.paternal === null ? '.' : String(marker.paternal),
      hap2: marker.maternal === null ? '.' : String(marker.maternal),
      ps: null,
    };
    const riskKind = diseaseHaplotypeKindForLane(diseaseModel, member, segment, lane, chrom);
    if (riskKind) return riskColors[riskKind];
    return (lane === 'hap1' ? fatherColors : motherColors)[value];
  };

  const tooltipNode = (marker: PhasedMarker): React.ReactNode => (
    <div>
      <strong>
        {chrom}:{marker.pos.toLocaleString()}
      </strong>
      <div>
        paternal: {marker.paternal === null ? 'uninformative' : `homolog ${marker.paternal}`}
      </div>
      <div>
        maternal: {marker.maternal === null ? 'uninformative' : `homolog ${marker.maternal}`}
      </div>
    </div>
  );

  return (
    <div className="relative" style={{ width, height }}>
      <svg width={width} height={height}>
        <line
          x1={0}
          x2={width}
          y1={half}
          y2={half}
          stroke={cssVar('--color-grid')}
          strokeWidth={1}
        />
        {markers.map((marker, index) => {
          const x = ((marker.pos - regionStart) / regionLength) * width;
          return (
            <g key={index}>
              {marker.paternal !== null ? (
                <rect
                  x={x}
                  y={0}
                  width={1}
                  height={Math.max(half - 1, 1)}
                  fill={laneColor(marker, 'hap1') ?? cssVar('--color-haplotype-unknown')}
                />
              ) : null}
              {marker.maternal !== null ? (
                <rect
                  x={x}
                  y={half}
                  width={1}
                  height={Math.max(half - 1, 1)}
                  fill={laneColor(marker, 'hap2') ?? cssVar('--color-haplotype-unknown')}
                />
              ) : null}
              <rect
                x={x - 3}
                y={0}
                width={6}
                height={height}
                fill="transparent"
                className="cursor-pointer"
                onMouseMove={(event) =>
                  setTooltip({ x: event.clientX, y: event.clientY, node: tooltipNode(marker) })
                }
                onMouseLeave={() => setTooltip(null)}
              />
            </g>
          );
        })}
      </svg>
      {markers.length === 0 ? (
        <div className="viz-empty-overlay">No informative imputed markers in this region</div>
      ) : null}
      {tooltip ? (
        <VizTooltip x={tooltip.x} y={tooltip.y}>
          {tooltip.node}
        </VizTooltip>
      ) : null}
    </div>
  );
};

export default PhasedMarkerTrack;
