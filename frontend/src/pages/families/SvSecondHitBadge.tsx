import React from 'react';
import type { SvSecondHit } from './smallVariantSearch';

/**
 * Flags a small variant whose gene is also hit by a structural variant — the cross-type
 * "second hit" that can complete a recessive genotype. A deletion (red) is highlighted
 * because it can remove the second copy and unmask a heterozygous SNV.
 */
const SvSecondHitBadge: React.FC<{ hit?: SvSecondHit | null }> = ({ hit }) => {
  if (!hit) return null;
  const types = hit.sv_types.length ? hit.sv_types.join(', ') : 'SV';
  const zygosity = hit.affected_zygosity ? ` · ${hit.affected_zygosity}` : '';
  const title = hit.has_deletion
    ? `This gene is also hit by a structural variant (${types}${zygosity}). A deletion can remove the second allele and unmask a heterozygous SNV — check for a possible compound heterozygote.`
    : `This gene is also hit by a structural variant (${types}${zygosity}) — a possible cross-type second hit.`;
  return (
    <span
      className={`sv-second-hit-badge${hit.has_deletion ? ' sv-second-hit-badge--del' : ''}`}
      title={title}
    >
      <svg
        className="sv-second-hit-badge-icon"
        viewBox="0 0 16 16"
        aria-hidden="true"
        focusable="false"
      >
        <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="8" cy="8" r="1.7" fill="currentColor" />
      </svg>
      SV: {types}
      {hit.sv_count > 1 ? ` ×${hit.sv_count}` : ''}
    </span>
  );
};

export default SvSecondHitBadge;
