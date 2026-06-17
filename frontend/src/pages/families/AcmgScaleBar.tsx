import type { AcmgClassification } from '../../lib/acmg';

type AcmgScaleBarProps = {
  classification: AcmgClassification;
};

// Visible point domain for the arrow. Totals outside this clamp to the ends.
const DOMAIN_MIN = -8;
const DOMAIN_MAX = 14;

// Band boundaries (point thresholds) shown as ticks under the bar.
const TICKS = [
  { points: -7, label: '−7' },
  { points: -1, label: '−1' },
  { points: 0, label: '0' },
  { points: 6, label: '6' },
  { points: 10, label: '10' },
];

function positionPct(points: number): number {
  const clamped = Math.min(DOMAIN_MAX, Math.max(DOMAIN_MIN, points));
  return ((clamped - DOMAIN_MIN) / (DOMAIN_MAX - DOMAIN_MIN)) * 100;
}

export default function AcmgScaleBar({ classification }: AcmgScaleBarProps) {
  const { points, label, standAloneBenign } = classification;
  const arrowPct = standAloneBenign ? 0 : positionPct(points);
  const pointsLabel = standAloneBenign ? 'BA1' : points > 0 ? `+${points}` : `${points}`;

  return (
    <div className="acmg-scalebar" role="img" aria-label={`ACMG classification: ${label}, ${pointsLabel} points`}>
      <div className="acmg-scalebar-readout">
        <span className="acmg-scalebar-class">{label}</span>
        <span className="acmg-scalebar-points">{pointsLabel} pts</span>
      </div>
      <div className="acmg-scalebar-track">
        <div className="acmg-scalebar-gradient" />
        {TICKS.map((tick) => (
          <span
            key={tick.points}
            className="acmg-scalebar-tick"
            style={{ left: `${positionPct(tick.points)}%` }}
          />
        ))}
        <span className="acmg-scalebar-arrow" style={{ left: `${arrowPct}%` }} aria-hidden="true" />
      </div>
      <div className="acmg-scalebar-legend">
        <span>Benign</span>
        <span>Likely benign</span>
        <span>VUS</span>
        <span>Likely pathogenic</span>
        <span>Pathogenic</span>
      </div>
    </div>
  );
}
