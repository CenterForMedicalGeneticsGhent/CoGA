import React from 'react';
import { normalizeHaplotypeInheritance } from '../../lib/haplotypeRisk';

interface HaplotypeLegendProps {
  inheritanceModel?: string | null;
}

const legendEntriesForModel = (inheritanceModel?: string | null) => {
  const mode = normalizeHaplotypeInheritance(inheritanceModel);
  if (mode === 'recessive') {
    return [
      {
        label: 'Maternal risk',
        color: 'var(--color-haplotype-recessive-maternal)',
      },
      {
        label: 'Paternal risk',
        color: 'var(--color-haplotype-recessive-paternal)',
      },
    ];
  }
  if (mode === 'x_linked_dominant' || mode === 'x_linked_recessive') {
    return [{ label: 'Disease X', color: 'var(--color-haplotype-x-linked)' }];
  }
  return [{ label: 'Disease haplotype', color: 'var(--color-haplotype-dominant)' }];
};

const HaplotypeLegend: React.FC<HaplotypeLegendProps> = ({ inheritanceModel }) => (
  <div className="haplotype-legend" aria-label="Haplotype color legend">
    {legendEntriesForModel(inheritanceModel).map((entry) => (
      <span key={entry.label} className="haplotype-legend-item">
        <span className="haplotype-legend-swatch" style={{ background: entry.color }} />
        {entry.label}
      </span>
    ))}
  </div>
);

export default HaplotypeLegend;
