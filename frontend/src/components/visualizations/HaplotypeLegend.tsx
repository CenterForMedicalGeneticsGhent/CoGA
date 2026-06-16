import React from 'react';
import { normalizeHaplotypeInheritance } from '../../lib/haplotypeRisk';

interface HaplotypeLegendProps {
  inheritanceModel?: string | null;
}

interface LegendEntry {
  label: string;
  color: string;
  /** Risk haplotypes are drawn as a hatch over the origin fill, not a solid block. */
  hatched?: boolean;
}

// Parent-of-origin fills are always present; the risk entries depend on the model.
const ORIGIN_ENTRIES: LegendEntry[] = [
  { label: 'Paternal', color: 'var(--color-haplotype-father-dark)' },
  { label: 'Maternal', color: 'var(--color-haplotype-mother-dark)' },
];

const riskEntriesForModel = (inheritanceModel?: string | null): LegendEntry[] => {
  const mode = normalizeHaplotypeInheritance(inheritanceModel);
  if (mode === 'recessive') {
    return [
      { label: 'Maternal risk', color: 'var(--color-haplotype-recessive-maternal)', hatched: true },
      { label: 'Paternal risk', color: 'var(--color-haplotype-recessive-paternal)', hatched: true },
    ];
  }
  if (mode === 'x_linked_dominant' || mode === 'x_linked_recessive') {
    return [{ label: 'Disease X', color: 'var(--color-haplotype-x-linked)', hatched: true }];
  }
  return [{ label: 'Disease haplotype', color: 'var(--color-haplotype-dominant)', hatched: true }];
};

const swatchStyle = (entry: LegendEntry): React.CSSProperties =>
  entry.hatched
    ? { background: `repeating-linear-gradient(45deg, ${entry.color} 0 1.5px, transparent 1.5px 4px)` }
    : { background: entry.color };

const HaplotypeLegend: React.FC<HaplotypeLegendProps> = ({ inheritanceModel }) => (
  <div className="haplotype-legend" aria-label="Haplotype color legend">
    {[...ORIGIN_ENTRIES, ...riskEntriesForModel(inheritanceModel)].map((entry) => (
      <span key={entry.label} className="haplotype-legend-item">
        <span className="haplotype-legend-swatch" style={swatchStyle(entry)} />
        {entry.label}
      </span>
    ))}
  </div>
);

export default HaplotypeLegend;
