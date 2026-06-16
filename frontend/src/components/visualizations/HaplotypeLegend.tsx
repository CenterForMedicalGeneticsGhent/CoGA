import React from 'react';
import { normalizeHaplotypeInheritance } from '../../lib/haplotypeRisk';

interface HaplotypeLegendProps {
  inheritanceModel?: string | null;
}

interface LegendEntry {
  label: string;
  color: string;
  /** Risk alleles are drawn as a frame over the homolog fill, not a solid block. */
  framed?: boolean;
}

// The four parental homologs (P1/P2 paternal, M1/M2 maternal) are always shown.
const HOMOLOG_ENTRIES: LegendEntry[] = [
  { label: 'P1', color: 'var(--color-haplotype-father-dark)' },
  { label: 'P2', color: 'var(--color-haplotype-father-light)' },
  { label: 'M1', color: 'var(--color-haplotype-mother-dark)' },
  { label: 'M2', color: 'var(--color-haplotype-mother-light)' },
];

const riskEntriesForModel = (inheritanceModel?: string | null): LegendEntry[] => {
  const mode = normalizeHaplotypeInheritance(inheritanceModel);
  if (mode === 'recessive') {
    return [{ label: 'Carrier', color: 'var(--color-haplotype-carrier)', framed: true }];
  }
  // dominant / x-linked / unknown
  return [{ label: 'Affected', color: 'var(--color-haplotype-affected)', framed: true }];
};

const swatchStyle = (entry: LegendEntry): React.CSSProperties =>
  entry.framed
    ? { background: 'var(--color-surface)', borderColor: entry.color, borderWidth: '1.5px' }
    : { background: entry.color };

const HaplotypeLegend: React.FC<HaplotypeLegendProps> = ({ inheritanceModel }) => (
  <div className="haplotype-legend" aria-label="Haplotype color legend">
    {[...HOMOLOG_ENTRIES, ...riskEntriesForModel(inheritanceModel)].map((entry) => (
      <span key={entry.label} className="haplotype-legend-item">
        <span className="haplotype-legend-swatch" style={swatchStyle(entry)} />
        {entry.label}
      </span>
    ))}
  </div>
);

export default HaplotypeLegend;
