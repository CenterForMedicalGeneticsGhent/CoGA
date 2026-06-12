import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../lib/api';
import { cssVar } from '../../lib/colors';
import VizTooltip from './VizTooltip';

type DgvClass = 'gain' | 'loss' | 'mixed' | 'other';

interface DgvVariant {
  chr: string;
  start: number;
  end: number;
  accession?: string | null;
  variant_type?: string | null;
  variant_subtype?: string | null;
  variant_class: DgvClass;
  frequency?: number | null;
  observed_gains?: number | null;
  observed_losses?: number | null;
  source?: string | null;
}

interface DgvDensityBin {
  start: number;
  end: number;
  gain: number;
  loss: number;
  mixed: number;
  other: number;
}

interface DgvTrackData {
  total: number;
  mode: 'lines' | 'density';
  bin_size: number;
  variants: DgvVariant[];
  bins: DgvDensityBin[];
}

interface Props {
  assembly: string;
  chrom: string;
  width: number;
  height: number;
  regionStart: number;
  regionEnd: number;
}

// gain = blue, loss = red, mixed (gain+loss/complex) = purple, other = grey.
const CLASS_VAR: Record<DgvClass, string> = {
  gain: '--color-dgv-gain',
  loss: '--color-dgv-loss',
  mixed: '--color-dgv-mixed',
  other: '--color-dgv-other',
};
const CLASS_ORDER: DgvClass[] = ['gain', 'loss', 'mixed', 'other'];
const LANE_GAP_PX = 1;
const LANE_MIN_HEIGHT = 2.5;

const dgvColor = (klass: DgvClass) => cssVar(CLASS_VAR[klass] ?? '--color-dgv-other');

const lineTooltip = (v: DgvVariant): React.ReactNode => (
  <div>
    <strong>{v.accession ?? 'DGV variant'}</strong>
    <div>{v.variant_subtype ?? v.variant_type ?? v.variant_class}</div>
    {typeof v.frequency === 'number' && v.frequency > 0 ? (
      <div>frequency {v.frequency.toFixed(4)}</div>
    ) : null}
  </div>
);

const densityTooltip = (b: DgvDensityBin, total: number): React.ReactNode => (
  <div>
    <strong>{total.toLocaleString()} DGV variants</strong>
    <div>
      gain {b.gain.toLocaleString()} · loss {b.loss.toLocaleString()} · mixed{' '}
      {b.mixed.toLocaleString()}
    </div>
  </div>
);

/**
 * DGV (Database of Genomic Variants) track. The server returns individual
 * variants when few enough overlap the view (`lines` mode, packed into lanes as
 * thin gain/loss-coloured bars), otherwise a per-bin density profile (`density`
 * mode) drawn as stacked bars so a whole chromosome stays legible.
 */
const DgvTrack: React.FC<Props> = ({
  assembly,
  chrom,
  width,
  height,
  regionStart,
  regionEnd,
}) => {
  const [tooltip, setTooltip] = React.useState<{
    x: number;
    y: number;
    node: React.ReactNode;
  } | null>(null);

  const { data } = useQuery<DgvTrackData>({
    queryKey: ['dgv', assembly, chrom, regionStart, regionEnd],
    queryFn: async () => {
      const res = await api.get(`/dgv/${assembly}/${chrom}`, {
        params: { start: regionStart, end: regionEnd },
      });
      return res.data as DgvTrackData;
    },
    enabled: regionEnd > regionStart,
  });

  if (!data) return <svg width={width} height={height} />;

  const regionLength = regionEnd - regionStart;
  // Tolerate an unexpected/empty response shape without crashing the track.
  const variants = Array.isArray(data.variants) ? data.variants : [];
  const bins = Array.isArray(data.bins) ? data.bins : [];
  const total = typeof data.total === 'number' ? data.total : variants.length;
  const mode: 'lines' | 'density' = data.mode === 'density' ? 'density' : 'lines';

  const renderLines = () => {
    const laneLastX: number[] = [];
    const maxLanes = Math.max(1, Math.floor(height / LANE_MIN_HEIGHT));
    let overflow = 0;
    const placed = variants
      .map((v) => {
        const s = Math.max(v.start, regionStart);
        const e = Math.min(v.end, regionEnd);
        const x = ((s - regionStart) / regionLength) * width;
        const w = Math.max(((e - s) / regionLength) * width, 1);
        return { v, x, w };
      })
      .sort((a, b) => a.x - b.x)
      .map((item) => {
        let lane = laneLastX.findIndex((lastX) => lastX <= item.x - LANE_GAP_PX);
        if (lane === -1) {
          if (laneLastX.length >= maxLanes) {
            overflow += 1;
            return null;
          }
          lane = laneLastX.length;
        }
        laneLastX[lane] = item.x + item.w;
        return { ...item, lane };
      })
      .filter((item): item is { v: DgvVariant; x: number; w: number; lane: number } =>
        item !== null,
      );

    const laneCount = Math.max(laneLastX.length, 1);
    const laneH = height / laneCount;
    const barH = Math.max(laneH - LANE_GAP_PX, 1);

    return (
      <>
        {placed.map((item, idx) => (
          <rect
            key={idx}
            x={item.x}
            y={item.lane * laneH}
            width={item.w}
            height={barH}
            fill={dgvColor(item.v.variant_class)}
            className="cursor-pointer"
            aria-label={item.v.accession ?? item.v.variant_subtype ?? 'DGV variant'}
            onMouseMove={(event) =>
              setTooltip({ x: event.clientX, y: event.clientY, node: lineTooltip(item.v) })
            }
            onMouseLeave={() => setTooltip(null)}
          />
        ))}
        {overflow > 0 ? (
          <text
            x={width - 2}
            y={height - 2}
            textAnchor="end"
            style={{ fill: cssVar('--color-text-muted'), fontSize: '9px' }}
          >
            +{overflow.toLocaleString()} more
          </text>
        ) : null}
      </>
    );
  };

  const renderDensity = () => {
    const maxTotal = bins.reduce(
      (m, b) => Math.max(m, b.gain + b.loss + b.mixed + b.other),
      0,
    );
    if (maxTotal === 0) return null;
    return (
      <>
        {bins.map((b, idx) => {
          const total = b.gain + b.loss + b.mixed + b.other;
          if (total === 0) return null;
          const x = ((b.start - regionStart) / regionLength) * width;
          const w = Math.max(((b.end - b.start) / regionLength) * width, 1);
          const barH = (total / maxTotal) * height;
          let y = height - barH;
          return (
            <g key={idx}>
              {CLASS_ORDER.map((klass) => {
                const n = b[klass];
                if (n === 0) return null;
                const segH = (n / total) * barH;
                const rect = (
                  <rect key={klass} x={x} y={y} width={w} height={segH} fill={dgvColor(klass)} />
                );
                y += segH;
                return rect;
              })}
              <rect
                x={x}
                y={height - barH}
                width={w}
                height={barH}
                fill="transparent"
                className="cursor-pointer"
                onMouseMove={(event) =>
                  setTooltip({ x: event.clientX, y: event.clientY, node: densityTooltip(b, total) })
                }
                onMouseLeave={() => setTooltip(null)}
              />
            </g>
          );
        })}
      </>
    );
  };

  return (
    <div className="relative" style={{ width, height }}>
      <svg width={width} height={height}>
        {mode === 'lines' ? renderLines() : renderDensity()}
      </svg>
      {total === 0 ? (
        <div className="viz-empty-overlay">No DGV variants in this region</div>
      ) : null}
      {mode === 'density' && total > 0 ? (
        <div
          style={{
            position: 'absolute',
            top: 2,
            right: 4,
            fontSize: '10px',
            color: cssVar('--color-text-muted'),
            pointerEvents: 'none',
          }}
        >
          density · {total.toLocaleString()} variants
        </div>
      ) : null}
      {tooltip ? (
        <VizTooltip x={tooltip.x} y={tooltip.y}>
          {tooltip.node}
        </VizTooltip>
      ) : null}
    </div>
  );
};

export default DgvTrack;
