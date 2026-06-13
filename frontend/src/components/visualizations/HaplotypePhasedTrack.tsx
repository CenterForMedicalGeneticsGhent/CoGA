import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../lib/api';
import { cssVar } from '../../lib/colors';
import {
  defaultHaplotypeRiskRegion,
  diseaseHaplotypeKindForLane,
  getHaplotypeLaneSignature,
  getRenderableHaplotypeLanes,
  inferDiseaseHaplotypes,
  interpretSampleHaplotypeRisk,
  resolveHaplotypeInheritanceModel,
  type DiseaseHaplotypeKind,
  type HaplotypeLane,
  type HaplotypeMemberLike,
  type HaplotypeRiskRegion,
} from '../../lib/haplotypeRisk';
import VizLoadingOverlay from './VizLoadingOverlay';
import VizTooltip from './VizTooltip';

interface Segment {
  start: number;
  end: number;
  hap1: string;
  hap2: string;
  ps?: number | null;
}

interface SampleSegments {
  sample: string;
  segments: Segment[];
}

interface HaplotypeResponse {
  chr: string;
  start: number;
  end: number;
  samples: SampleSegments[];
}

interface PhasedMarker {
  pos: number;
  paternal: number | null;
  maternal: number | null;
}

interface PhasedMarkerResponse {
  samples: { sample: string; markers: PhasedMarker[] }[];
}

const isDeletedHaplotype = (value: string): boolean => value === '.';

/** Nearest marker to a genomic position, by binary search over pos-sorted markers. */
const nearestMarkerByPos = (markers: PhasedMarker[], pos: number): PhasedMarker | null => {
  if (markers.length === 0) return null;
  let lo = 0;
  let hi = markers.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (markers[mid].pos < pos) lo = mid + 1;
    else hi = mid;
  }
  const candidate = markers[lo];
  if (lo > 0 && Math.abs(markers[lo - 1].pos - pos) < Math.abs(candidate.pos - pos)) {
    return markers[lo - 1];
  }
  return candidate;
};

interface Props {
  familyId: string;
  sampleId: string;
  chrom: string;
  regionStart: number;
  regionEnd: number;
  width: number;
  height: number;
  role: string;
  affected: boolean;
  sex?: string | null;
  carrierStatus?: boolean | null;
  carrierType?: string | null;
  highlightRiskHaplotype?: boolean;
  disorder?: 'dominant' | 'recessive';
  inheritanceModel?: string | null;
  familyMembers?: HaplotypeMemberLike[];
  riskRegion?: HaplotypeRiskRegion | null;
  /**
   * Overlay the raw per-marker parent-of-origin calls on top of the haplotype
   * blocks. Enabled for a child with both parents present; the haplotype block is
   * then drawn as a thin line and the markers as dots on top so disagreements
   * (phasing noise / switches) stand out against the cleaned blocks.
   */
  showMarkers?: boolean;
}

const HaplotypePhasedTrack: React.FC<Props> = ({
  familyId,
  sampleId,
  chrom,
  regionStart,
  regionEnd,
  width,
  height,
  role,
  affected,
  sex,
  carrierStatus = false,
  carrierType,
  highlightRiskHaplotype,
  disorder = 'dominant',
  inheritanceModel,
  familyMembers = [],
  riskRegion,
  showMarkers = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; node: React.ReactNode } | null>(
    null,
  );

  const hasRegion = regionEnd > regionStart;

  const { data: haplotypeData, isLoading } = useQuery<HaplotypeResponse>({
    queryKey: ['haplotypes', familyId, chrom, regionStart, regionEnd],
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/haplotypes`, {
        params: { chr: chrom, start: regionStart, end: regionEnd },
      });
      return res.data as HaplotypeResponse;
    },
    enabled: hasRegion,
    staleTime: Infinity,
    gcTime: Infinity,
  });

  // Raw per-marker parent-of-origin (computed server-side, returned per child).
  // Only fetched when we are overlaying markers for this member.
  const { data: phasedData } = useQuery<PhasedMarkerResponse>({
    queryKey: ['phased-markers', familyId, chrom, regionStart, regionEnd],
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/phased-markers`, {
        params: { chr: chrom, start: regionStart, end: regionEnd },
      });
      return res.data as PhasedMarkerResponse;
    },
    enabled: hasRegion && showMarkers,
  });

  const effectiveInheritanceModel = inheritanceModel || (disorder === 'recessive' ? 'AR' : 'AD');
  const currentMember: HaplotypeMemberLike = useMemo(
    () => ({
      sample_id: sampleId,
      role,
      affected,
      sex,
      carrier_status: carrierStatus ? 'carrier' : 'unknown',
      carrier_type: carrierType,
    }),
    [affected, carrierStatus, carrierType, role, sampleId, sex],
  );
  const membersForRisk = familyMembers.length > 0 ? familyMembers : [currentMember];
  const analysisRegion = riskRegion || defaultHaplotypeRiskRegion(chrom, regionStart, regionEnd);
  const riskEnabled =
    highlightRiskHaplotype ??
    membersForRisk.some((member) => member.affected || member.carrier_status === 'carrier');
  const diseaseModel = useMemo(
    () =>
      riskEnabled
        ? inferDiseaseHaplotypes({
            samples: haplotypeData?.samples || [],
            members: membersForRisk,
            inheritanceModel: resolveHaplotypeInheritanceModel(effectiveInheritanceModel, membersForRisk),
            region: analysisRegion,
          })
        : inferDiseaseHaplotypes({
            samples: [],
            members: [],
            inheritanceModel: effectiveInheritanceModel,
            region: analysisRegion,
          }),
    [analysisRegion, haplotypeData?.samples, effectiveInheritanceModel, membersForRisk, riskEnabled],
  );

  const segments = useMemo(
    () => haplotypeData?.samples.find((entry) => entry.sample === sampleId)?.segments || [],
    [haplotypeData?.samples, sampleId],
  );
  const markers = useMemo(
    () =>
      showMarkers
        ? phasedData?.samples.find((entry) => entry.sample === sampleId)?.markers || []
        : [],
    [showMarkers, phasedData?.samples, sampleId],
  );
  const sortedMarkers = useMemo(() => [...markers].sort((a, b) => a.pos - b.pos), [markers]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = width;
    canvas.height = height;
    ctx.clearRect(0, 0, width, height);
    if (isLoading || !hasRegion) return;

    const span = regionEnd - regionStart || 1;
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
    const unknownColor = cssVar('--color-haplotype-unknown');
    const deletedFill = cssVar('--color-haplotype-deleted-fill');
    const deletedStroke = cssVar('--color-haplotype-deleted-stroke');

    const BAND_THICKNESS = 4;
    const DOT_RADIUS = 2.2;
    const laneCenter = (lane: HaplotypeLane, single: boolean): number =>
      single ? half : lane === 'hap1' ? half / 2 : half + half / 2;

    const baseColorForLane = (seg: Segment, lane: HaplotypeLane): string => {
      const value = seg[lane];
      if (isDeletedHaplotype(value)) return deletedFill;
      const parsed = parseInt(value, 10);
      const signature = getHaplotypeLaneSignature(currentMember, seg, lane, chrom);
      if (!signature) return unknownColor;
      const palette = signature.origin === 'paternal' ? fatherColors : motherColors;
      return Number.isNaN(parsed) ? unknownColor : palette[parsed] || unknownColor;
    };

    // Lane divider.
    ctx.strokeStyle = cssVar('--color-grid');
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, half + 0.5);
    ctx.lineTo(width, half + 0.5);
    ctx.stroke();

    // Haplotype blocks. With markers overlaid they shrink to a thin line so the
    // dots sit on top; otherwise they fill their lane like the classic block view.
    const recombXs: number[] = [];
    segments.forEach((seg, idx) => {
      const x1 = ((seg.start - regionStart) / span) * width;
      const x2 = ((seg.end - regionStart) / span) * width;
      const w = Math.max(x2 - x1, 1);
      if (idx > 0) {
        const prev = segments[idx - 1];
        if (seg.ps !== prev.ps || seg.hap1 !== prev.hap1 || seg.hap2 !== prev.hap2) {
          recombXs.push(x1);
        }
      }
      const lanes = getRenderableHaplotypeLanes(currentMember, seg, chrom);
      const single = lanes.length === 1;
      lanes.forEach((lane) => {
        const riskKind = diseaseHaplotypeKindForLane(diseaseModel, currentMember, seg, lane, chrom);
        const color = riskKind ? riskColors[riskKind] : baseColorForLane(seg, lane);
        let y: number;
        let h: number;
        if (showMarkers) {
          y = laneCenter(lane, single) - BAND_THICKNESS / 2;
          h = BAND_THICKNESS;
        } else if (single) {
          y = 1;
          h = height - 2;
        } else if (lane === 'hap1') {
          y = 1;
          h = half - 2;
        } else {
          y = half + 1;
          h = half - 2;
        }
        ctx.fillStyle = color;
        ctx.fillRect(x1, y, w, h);
        if (isDeletedHaplotype(seg[lane])) {
          ctx.strokeStyle = deletedStroke;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(x1 + 0.75, y + 1);
          ctx.lineTo(x2 - 0.75, y + h - 1);
          ctx.stroke();
        }
      });
    });

    // Recombination boundaries.
    ctx.strokeStyle = cssVar('--color-axis');
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 2]);
    recombXs.forEach((x) => {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    });
    ctx.setLineDash([]);

    if (!showMarkers) return;

    // Raw per-marker calls as dots on top of the thin haplotype line.
    const markerColor = (marker: PhasedMarker, lane: HaplotypeLane): string | null => {
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
      const riskKind = diseaseHaplotypeKindForLane(diseaseModel, currentMember, segment, lane, chrom);
      if (riskKind) return riskColors[riskKind];
      return (lane === 'hap1' ? fatherColors : motherColors)[value];
    };
    const paternalCy = laneCenter('hap1', false);
    const maternalCy = laneCenter('hap2', false);
    markers.forEach((marker) => {
      const x = ((marker.pos - regionStart) / span) * width;
      if (marker.paternal !== null) {
        ctx.fillStyle = markerColor(marker, 'hap1') ?? unknownColor;
        ctx.beginPath();
        ctx.arc(x, paternalCy, DOT_RADIUS, 0, Math.PI * 2);
        ctx.fill();
      }
      if (marker.maternal !== null) {
        ctx.fillStyle = markerColor(marker, 'hap2') ?? unknownColor;
        ctx.beginPath();
        ctx.arc(x, maternalCy, DOT_RADIUS, 0, Math.PI * 2);
        ctx.fill();
      }
    });
  }, [
    segments,
    markers,
    showMarkers,
    diseaseModel,
    currentMember,
    chrom,
    width,
    height,
    regionStart,
    regionEnd,
    isLoading,
    hasRegion,
  ]);

  const hasSegments = segments.length > 0;
  const riskState = hasSegments
    ? interpretSampleHaplotypeRisk({
        model: diseaseModel,
        samples: haplotypeData?.samples || [],
        member: currentMember,
        region: analysisRegion,
      })
    : 'uninformative';

  const handleMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!showMarkers || sortedMarkers.length === 0) {
      setTooltip(null);
      return;
    }
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const span = regionEnd - regionStart || 1;
    const pos = regionStart + (x / width) * span;
    const marker = nearestMarkerByPos(sortedMarkers, pos);
    if (!marker) {
      setTooltip(null);
      return;
    }
    const markerX = ((marker.pos - regionStart) / span) * width;
    if (Math.abs(markerX - x) > 3) {
      setTooltip(null);
      return;
    }
    setTooltip({
      x: event.clientX,
      y: event.clientY,
      node: (
        <div>
          <strong>
            {chrom}:{marker.pos.toLocaleString()}
          </strong>
          <div>paternal: {marker.paternal === null ? 'uninformative' : `homolog ${marker.paternal}`}</div>
          <div>maternal: {marker.maternal === null ? 'uninformative' : `homolog ${marker.maternal}`}</div>
        </div>
      ),
    });
  };

  return (
    <div
      className={`relative haplotype-track haplotype-track--${riskState}`}
      data-risk-state={riskState}
      style={{ width, height }}
    >
      <canvas
        ref={canvasRef}
        className={showMarkers ? 'cursor-pointer' : undefined}
        aria-label={`Haplotype risk state: ${riskState}`}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      />
      {isLoading && <VizLoadingOverlay message="Loading haplotypes" />}
      {!isLoading && !hasSegments && (
        <div className="viz-empty-overlay">No haplotype data in this region</div>
      )}
      {tooltip && (
        <VizTooltip x={tooltip.x} y={tooltip.y}>
          {tooltip.node}
        </VizTooltip>
      )}
    </div>
  );
};

export default HaplotypePhasedTrack;
