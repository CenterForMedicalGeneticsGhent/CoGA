import React, { useEffect, useMemo, useRef, useState } from 'react';
import { cssVar } from '../../lib/colors';
import { storage } from '../../lib/storage';
import VizLoadingOverlay from './VizLoadingOverlay';
import VizTooltip from './VizTooltip';

const DEFAULT_CHROMS = [
  ...Array.from({ length: 22 }, (_, i) => String(i + 1)),
  'X',
  'Y',
];

const normalizeChrom = (value: string): string =>
  value.toLowerCase().startsWith('chr') ? value.slice(3) : value;

interface ApcadBin {
  chr: string;
  start: number;
  end: number;
  value: number;
  origin: string;
}

type ApcadSegment = ApcadBin;

interface Layout {
  offsets: Record<string, number>;
  lengths: Record<string, number>;
  total: number;
}

interface ApcadTrackData {
  bins: ApcadBin[];
  segments: ApcadSegment[];
}

interface SegmentHitbox {
  x1: number;
  x2: number;
  y: number;
  segment: ApcadSegment;
}

interface BedRecordPayload<T> {
  items: T[];
}

const fetchJsonOrNull = async <T,>(
  url: string,
  headers: Record<string, string>,
  signal: AbortSignal,
): Promise<BedRecordPayload<T> | null> => {
  try {
    const response = await fetch(url, { headers, signal });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as BedRecordPayload<T>;
  } catch {
    if (signal.aborted) {
      throw new DOMException('Aborted', 'AbortError');
    }
    return null;
  }
};

const splitKey = (key: string): string[] => (key ? key.split('\n').filter(Boolean) : []);

const deriveLayoutFromBins = (
  bins: ApcadBin[],
  chroms: string[],
  regionStart?: number,
  regionEnd?: number,
): Layout => {
  const lengths: Record<string, number> = {};
  chroms.forEach((chrom) => {
    lengths[chrom] = 0;
  });

  bins.forEach((bin) => {
    lengths[bin.chr] = Math.max(lengths[bin.chr] ?? 0, bin.end);
  });

  const offsets: Record<string, number> = {};
  let total = 0;
  chroms.forEach((chrom) => {
    offsets[chrom] = total;
    total += lengths[chrom] ?? 0;
  });

  if (
    regionStart !== undefined &&
    regionEnd !== undefined &&
    chroms.length === 1
  ) {
    total = regionEnd - regionStart;
  }

  return { offsets, lengths, total };
};

interface Props {
  apcadUrls: string[];
  pcfUrls?: string[];
  width?: number;
  height?: number;
  chroms?: string[];
  regionStart?: number;
  regionEnd?: number;
  onChromosomeClick?: (chrom: string) => void;
  onLayout?: (layout: Layout & { chroms: string[] }) => void;
  layout?: Layout;
}

const ApcadChart: React.FC<Props> = ({
  apcadUrls,
  pcfUrls = [],
  width = 800,
  height = 120,
  chroms = DEFAULT_CHROMS,
  regionStart,
  regionEnd,
  onChromosomeClick,
  onLayout,
  layout,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasData, setHasData] = useState<boolean | null>(null);
  const [trackData, setTrackData] = useState<ApcadTrackData | null>(null);
  const [hoverSegment, setHoverSegment] = useState<{
    x: number;
    y: number;
    segment: ApcadSegment;
  } | null>(null);
  const layoutRef = useRef<Layout>({ offsets: {}, lengths: {}, total: 0 });
  const segmentHitboxesRef = useRef<SegmentHitbox[]>([]);

  const apcadUrlKey = apcadUrls.join('\n');
  const pcfUrlKey = pcfUrls.join('\n');
  const chromKey = chroms.join('\n');

  const stableApcadUrls = useMemo(() => splitKey(apcadUrlKey), [apcadUrlKey]);
  const stablePcfUrls = useMemo(() => splitKey(pcfUrlKey), [pcfUrlKey]);
  const stableChroms = useMemo(() => splitKey(chromKey), [chromKey]);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    const load = async () => {
      if (stableApcadUrls.length === 0 && stablePcfUrls.length === 0) {
        if (active) {
          setTrackData(null);
          setHasData(false);
          setLoading(false);
        }
        return;
      }

      if (active) {
        setLoading(true);
      }

      const headers: Record<string, string> = {};
      const token = storage.getItem('token');
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }

      try {
        const allowedChroms = new Set(stableChroms.map(normalizeChrom));
        const [apcadPayloads, pcfPayloads] = await Promise.all([
          Promise.all(
            stableApcadUrls.map((url) =>
              fetchJsonOrNull<ApcadBin>(url, headers, controller.signal),
            ),
          ),
          Promise.all(
            stablePcfUrls.map((url) =>
              fetchJsonOrNull<ApcadSegment>(url, headers, controller.signal),
            ),
          ),
        ]);

        if (!active) {
          return;
        }

        const bins: ApcadBin[] = [];
        const segments: ApcadSegment[] = [];
        apcadPayloads.forEach((payload) => {
          if (!payload) {
            return;
          }
          payload.items.forEach((item) => {
            const chromName = normalizeChrom(item.chr);
            if (!allowedChroms.has(chromName)) {
              return;
            }
            const origin = (item.origin || 'und').toLowerCase();
            if (origin !== 'paternal' && origin !== 'maternal') {
              return;
            }
            bins.push({
              chr: chromName,
              start: item.start,
              end: item.end,
              value: item.value,
              origin,
            });
          });
        });
        pcfPayloads.forEach((payload) => {
          if (!payload) {
            return;
          }
          payload.items.forEach((item) => {
            const chromName = normalizeChrom(item.chr);
            if (!allowedChroms.has(chromName)) {
              return;
            }
            const origin = (item.origin || 'und').toLowerCase();
            if (origin !== 'paternal' && origin !== 'maternal') {
              return;
            }
            if (!Number.isFinite(item.value)) {
              return;
            }
            segments.push({
              chr: chromName,
              start: item.start,
              end: item.end,
              value: item.value,
              origin,
            });
          });
        });

        if (active) {
          setTrackData({ bins, segments });
          setHasData(bins.length > 0 || segments.length > 0);
        }
      } catch {
        if (controller.signal.aborted) {
          return;
        }
        if (active) {
          setTrackData(null);
          setHasData(false);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      active = false;
      controller.abort();
    };
  }, [stableApcadUrls, stableChroms, stablePcfUrls]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) {
      return;
    }

    ctx.clearRect(0, 0, width, height);
    segmentHitboxesRef.current = [];
    setHoverSegment(null);

    if (!trackData || (trackData.bins.length === 0 && trackData.segments.length === 0)) {
      layoutRef.current = { offsets: {}, lengths: {}, total: 0 };
      return;
    }

    const { bins, segments } = trackData;
    let chromLengths: Record<string, number>;
    let offsets: Record<string, number>;
    let totalLength: number;

    if (layout) {
      chromLengths = layout.lengths;
      offsets = layout.offsets;
      totalLength = layout.total;
    } else {
      const derivedLayout = deriveLayoutFromBins(
        [...bins, ...segments],
        stableChroms,
        regionStart,
        regionEnd,
      );
      chromLengths = derivedLayout.lengths;
      offsets = derivedLayout.offsets;
      totalLength = derivedLayout.total;
    }

    layoutRef.current = { offsets, lengths: chromLengths, total: totalLength };
    if (!layout) {
      onLayout?.({
        offsets,
        lengths: chromLengths,
        total: totalLength,
        chroms: stableChroms,
      });
    }

    const isFocusedRegion =
      regionStart !== undefined &&
      regionEnd !== undefined &&
      stableChroms.length === 1;
    const xDomainStart = isFocusedRegion ? regionStart : 0;
    const xDomainEnd = isFocusedRegion ? regionEnd : totalLength;
    const xDomainSpan = xDomainEnd - xDomainStart;
    if (xDomainSpan <= 0) {
      return;
    }

    const xScale = (value: number) =>
      ((value - xDomainStart) / xDomainSpan) * width;
    const yScale = (value: number) => (1 - value) * height;

    const tickValues = [0, 0.33, 0.5, 0.66, 1];
    const gridColor = cssVar('--color-grid');
    const textColor = cssVar('--color-apcad-default');
    const paternalColor = cssVar('--color-apcad-paternal');
    const maternalColor = cssVar('--color-apcad-maternal');

    ctx.save();
    ctx.font = '10px sans-serif';
    ctx.textBaseline = 'middle';
    ctx.strokeStyle = gridColor;
    ctx.fillStyle = textColor;
    tickValues.forEach((tick) => {
      const y = yScale(tick);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
      ctx.fillText(tick.toFixed(2), 4, y);
    });
    ctx.restore();

    bins.forEach((bin) => {
      if (
        isFocusedRegion &&
        (bin.end < regionStart || bin.start > regionEnd)
      ) {
        return;
      }

      const offset = offsets[bin.chr] ?? 0;
      const center = (bin.start + bin.end) / 2;
      const genomeCenter = isFocusedRegion ? center : offset + center;
      const cx = xScale(genomeCenter);
      const cy = yScale(bin.value);

      let fill = textColor;
      if (bin.origin === 'paternal') {
        fill = paternalColor;
      } else if (bin.origin === 'maternal') {
        fill = maternalColor;
      }

      ctx.fillStyle = fill;
      ctx.beginPath();
      ctx.arc(cx, cy, 1, 0, Math.PI * 2);
      ctx.fill();
    });

    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = 0.8;
    segments.forEach((segment) => {
      if (
        isFocusedRegion &&
        (segment.end < regionStart || segment.start > regionEnd)
      ) {
        return;
      }

      const offset = offsets[segment.chr] ?? 0;
      const genomeStart = isFocusedRegion ? segment.start : offset + segment.start;
      const genomeEnd = isFocusedRegion ? segment.end : offset + segment.end;
      const x1 = Math.max(0, Math.min(width, xScale(genomeStart)));
      const x2 = Math.max(0, Math.min(width, xScale(genomeEnd)));
      const y = yScale(segment.value);
      const stroke =
        segment.origin === 'paternal'
          ? paternalColor
          : segment.origin === 'maternal'
            ? maternalColor
            : textColor;

      ctx.strokeStyle = stroke;
      ctx.beginPath();
      ctx.moveTo(x1, y);
      ctx.lineTo(x2, y);
      ctx.stroke();
      segmentHitboxesRef.current.push({
        x1: Math.min(x1, x2),
        x2: Math.max(x1, x2),
        y,
        segment,
      });
    });
    ctx.restore();

    if (stableChroms.length > 1) {
      ctx.strokeStyle = cssVar('--color-grid');
      ctx.lineWidth = 0.5;
      stableChroms.slice(0, -1).forEach((chrom) => {
        const boundary = (offsets[chrom] ?? 0) + (chromLengths[chrom] ?? 0);
        const x = xScale(boundary);
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      });
    }
  }, [
    height,
    layout,
    onLayout,
    regionEnd,
    regionStart,
    stableChroms,
    trackData,
    width,
  ]);

  const handleClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onChromosomeClick) {
      return;
    }

    const { offsets, lengths, total } = layoutRef.current;
    if (total <= 0) {
      return;
    }

    const genomePos = (event.nativeEvent.offsetX / width) * total;
    for (const chrom of stableChroms) {
      const start = offsets[chrom] ?? 0;
      const end = start + (lengths[chrom] ?? 0);
      if (genomePos >= start && genomePos < end) {
        onChromosomeClick(chrom);
        break;
      }
    }
  };

  const handleMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const x = event.nativeEvent.offsetX;
    const y = event.nativeEvent.offsetY;
    const hit = segmentHitboxesRef.current.find(
      (item) => x >= item.x1 && x <= item.x2 && Math.abs(y - item.y) <= 6,
    );
    if (!hit) {
      setHoverSegment(null);
      return;
    }
    setHoverSegment({ x: event.clientX, y: event.clientY, segment: hit.segment });
  };

  return (
    <div className="relative" style={{ width, height }}>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverSegment(null)}
      />
      {hoverSegment && (
        <VizTooltip x={hoverSegment.x} y={hoverSegment.y}>
          <div>PCF {hoverSegment.segment.origin}</div>
          <div>value {hoverSegment.segment.value.toFixed(4)}</div>
        </VizTooltip>
      )}
      {loading && <VizLoadingOverlay message="Loading APCAD" />}
      {!loading && hasData === false && (
        <div className="viz-empty-overlay">No APCAD data in this region</div>
      )}
    </div>
  );
};

export default ApcadChart;
