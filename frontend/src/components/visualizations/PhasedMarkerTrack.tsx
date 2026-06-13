import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../lib/api';
import { cssVar } from '../../lib/colors';
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

/** Nearest marker to a genomic position, by binary search over pos-sorted markers. */
const nearestByPos = (markers: PhasedMarker[], pos: number): PhasedMarker | null => {
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
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const [tooltip, setTooltip] = React.useState<{
    x: number;
    y: number;
    node: React.ReactNode;
  } | null>(null);

  // No span gate — the server-side endpoint is bounded for any window.
  const hasRegion = regionEnd > regionStart;

  // Per-marker parent-of-origin is computed server-side (it needs every sample's
  // phased GT across the dense imputed sites) and returned per child as RAW calls
  // — one point per informative site, no binning/denoising. This track is the
  // diagnostic layer showing where the phasing is uncertain about the haplotypes;
  // the "cleaned" view is the Haplotype block track. Shared cache key across the
  // family's children.
  const { data: phasedData } = useQuery<PhasedMarkerResponse>({
    queryKey: ['phased-markers', familyId, chrom, regionStart, regionEnd],
    queryFn: async () => {
      const res = await api.get(`/families/${familyId}/phased-markers`, {
        params: { chr: chrom, start: regionStart, end: regionEnd },
      });
      return res.data as PhasedMarkerResponse;
    },
    enabled: hasRegion,
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
    enabled: hasRegion,
    staleTime: Infinity,
  });

  const markers: PhasedMarker[] = React.useMemo(
    () => phasedData?.samples.find((entry) => entry.sample === sampleId)?.markers ?? [],
    [phasedData?.samples, sampleId],
  );

  // Pos-sorted copy for tooltip hit-testing (the backend returns markers in
  // positional order, but sort defensively so the binary search is correct).
  const sortedMarkers = React.useMemo(
    () => [...markers].sort((a, b) => a.pos - b.pos),
    [markers],
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

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = width;
    canvas.height = height;
    ctx.clearRect(0, 0, width, height);
    if (!hasRegion) return;

    const half = height / 2;
    const regionLength = regionEnd - regionStart;
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

    // Centre grid line.
    ctx.strokeStyle = cssVar('--color-grid');
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, half + 0.5);
    ctx.lineTo(width, half + 0.5);
    ctx.stroke();

    // One 1px column per raw marker — paternal lane on top, maternal below.
    const laneHeight = Math.max(half - 1, 1);
    markers.forEach((marker) => {
      const x = Math.floor(((marker.pos - regionStart) / regionLength) * width);
      if (marker.paternal !== null) {
        ctx.fillStyle = laneColor(marker, 'hap1') ?? unknownColor;
        ctx.fillRect(x, 0, 1, laneHeight);
      }
      if (marker.maternal !== null) {
        ctx.fillStyle = laneColor(marker, 'hap2') ?? unknownColor;
        ctx.fillRect(x, half, 1, laneHeight);
      }
    });
  }, [markers, diseaseModel, member, chrom, width, height, regionStart, regionEnd, hasRegion]);

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

  const handleMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || sortedMarkers.length === 0) {
      setTooltip(null);
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const regionLength = regionEnd - regionStart;
    const pos = regionStart + (x / width) * regionLength;
    const marker = nearestByPos(sortedMarkers, pos);
    if (!marker) {
      setTooltip(null);
      return;
    }
    const markerX = ((marker.pos - regionStart) / regionLength) * width;
    if (Math.abs(markerX - x) > 3) {
      setTooltip(null);
      return;
    }
    setTooltip({ x: event.clientX, y: event.clientY, node: tooltipNode(marker) });
  };

  if (!hasRegion) {
    return <svg width={width} height={height} />;
  }

  return (
    <div className="relative" style={{ width, height }}>
      <canvas
        ref={canvasRef}
        className="cursor-pointer"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      />
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
