import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../lib/api';
import { cssVar } from '../../lib/colors';
import { drawHaplotypeRiskOverlay } from '../../lib/haplotypeCanvas';
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
  // Value drawn on each lane (0/1). Child: inherited paternal (hap1) / maternal
  // (hap2) homolog; parent: the allele on their own hap1 / hap2.
  hap1: number | null;
  hap2: number | null;
}

interface PhasedMarkerResponse {
  samples: { sample: string; markers: PhasedMarker[] }[];
}

const isDeletedHaplotype = (value: string): boolean => value === '.';

const laneValue = (value: number | null): string => (value === null ? '.' : String(value));
const gtString = (marker?: PhasedMarker): string =>
  marker ? `${laneValue(marker.hap1)}|${laneValue(marker.hap2)}` : '—';

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

const sampleIdForRole = (members: HaplotypeMemberLike[], role: string): string | null =>
  members.find((member) => (member.role || '').toLowerCase() === role)?.sample_id ?? null;

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
   * Overlay the raw per-marker phasing as dots on top of the (thin) haplotype
   * line. Enabled for the whole family when both parents are present. For a child
   * the dots are the inherited parental homolog; for a parent, the alleles on
   * their own homologs. Disagreements with the cleaned blocks stand out.
   */
  showMarkers?: boolean;
}

const BAND_THICKNESS = 4;
// Markers are drawn as crisp 1px vertical ticks at the floored x so they stay
// sharp (no anti-alias blur) and taller than the band so disagreements stand out.
const MARKER_WIDTH = 1;
const MARKER_LANE_PADDING = 2;
// Stable empty fallback so the optional familyMembers prop keeps one reference
// across renders (an inline `= []` default would defeat the memos below).
const EMPTY_MEMBERS: HaplotypeMemberLike[] = [];

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
  familyMembers = EMPTY_MEMBERS,
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

  // Raw per-marker phasing (computed server-side, returned per member). Only
  // fetched when we are overlaying markers.
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
  const membersForRisk = useMemo(
    () => (familyMembers.length > 0 ? familyMembers : [currentMember]),
    [familyMembers, currentMember],
  );
  const analysisRegion = useMemo(
    () => riskRegion || defaultHaplotypeRiskRegion(chrom, regionStart, regionEnd),
    [riskRegion, chrom, regionStart, regionEnd],
  );
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
  const markersFor = (id: string | null): PhasedMarker[] =>
    id ? phasedData?.samples.find((entry) => entry.sample === id)?.markers || [] : [];
  const markers = useMemo(
    () => (showMarkers ? markersFor(sampleId) : []),
    [showMarkers, phasedData?.samples, sampleId],
  );
  const sortedMarkers = useMemo(() => [...markers].sort((a, b) => a.pos - b.pos), [markers]);

  // Father / mother markers, indexed by position, to reconstruct their genotype
  // at a hovered site for the tooltip.
  const parentGtByPos = useMemo(() => {
    if (!showMarkers) return null;
    const toMap = (id: string | null) => new Map(markersFor(id).map((m) => [m.pos, m]));
    return {
      father: toMap(sampleIdForRole(familyMembers, 'father')),
      mother: toMap(sampleIdForRole(familyMembers, 'mother')),
    };
  }, [showMarkers, phasedData?.samples, familyMembers]);

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
    const laneRiskKind = (seg: Segment, lane: HaplotypeLane): DiseaseHaplotypeKind | null =>
      diseaseHaplotypeKindForLane(diseaseModel, currentMember, seg, lane, chrom);

    // Lane divider.
    ctx.strokeStyle = cssVar('--color-grid');
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, half + 0.5);
    ctx.lineTo(width, half + 0.5);
    ctx.stroke();

    // Haplotype blocks — always a thin line; markers (when shown) sit on top.
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
        const y = laneCenter(lane, single) - BAND_THICKNESS / 2;
        ctx.fillStyle = baseColorForLane(seg, lane);
        ctx.fillRect(x1, y, w, BAND_THICKNESS);
        if (isDeletedHaplotype(seg[lane])) {
          ctx.strokeStyle = deletedStroke;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(x1 + 0.75, y);
          ctx.lineTo(x2 - 0.75, y + BAND_THICKNESS);
          ctx.stroke();
        }
        const riskKind = laneRiskKind(seg, lane);
        if (riskKind) drawHaplotypeRiskOverlay(ctx, x1, y, w, BAND_THICKNESS, riskColors[riskKind]);
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

    // Raw per-marker calls as dots on top of the thin line, coloured by the same
    // parent-of-origin palette as the block lane beneath them. Risk is shown by
    // the hatch on the cleaned blocks, not by recolouring individual dots.
    const dotColor = (marker: PhasedMarker, lane: HaplotypeLane): string => {
      const synthetic: Segment = {
        start: marker.pos,
        end: marker.pos + 1,
        hap1: laneValue(marker.hap1),
        hap2: laneValue(marker.hap2),
        ps: null,
      };
      return baseColorForLane(synthetic, lane);
    };
    const paternalCy = laneCenter('hap1', false);
    const maternalCy = laneCenter('hap2', false);
    const markerHalfHeight = Math.max(half / 2 - MARKER_LANE_PADDING, 1);
    const drawMarker = (x: number, cy: number, color: string) => {
      ctx.fillStyle = color;
      ctx.fillRect(Math.floor(x), cy - markerHalfHeight, MARKER_WIDTH, markerHalfHeight * 2);
    };
    markers.forEach((marker) => {
      const x = ((marker.pos - regionStart) / span) * width;
      if (marker.hap1 !== null) drawMarker(x, paternalCy, dotColor(marker, 'hap1'));
      if (marker.hap2 !== null) drawMarker(x, maternalCy, dotColor(marker, 'hap2'));
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
  const riskState = useMemo(
    () =>
      hasSegments
        ? interpretSampleHaplotypeRisk({
            model: diseaseModel,
            samples: haplotypeData?.samples || [],
            member: currentMember,
            region: analysisRegion,
          })
        : 'uninformative',
    [hasSegments, diseaseModel, haplotypeData?.samples, currentMember, analysisRegion],
  );

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
    const fatherGt = gtString(parentGtByPos?.father.get(marker.pos));
    const motherGt = gtString(parentGtByPos?.mother.get(marker.pos));
    setTooltip({
      x: event.clientX,
      y: event.clientY,
      node: (
        <div>
          <strong>
            {chrom}:{marker.pos.toLocaleString()}
          </strong>
          <div>Father: {fatherGt}</div>
          <div>Mother: {motherGt}</div>
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
