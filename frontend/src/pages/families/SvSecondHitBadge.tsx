import React, { useState, type MouseEvent, type FocusEvent } from 'react';
import type { SvSecondHit } from './smallVariantSearch';

/**
 * Flags a small variant whose gene is also hit by a structural variant — the cross-type
 * "second hit" that can complete a recessive genotype. A deletion (red) is highlighted
 * because it can remove the second copy and unmask a heterozygous SNV.
 *
 * The explanation is shown via a fixed-position hover/focus tooltip rather than the native
 * `title` attribute: the badge's inline SVG icon swallows the pointer, so `title` never
 * fired, and a fixed tooltip also escapes the variant table's scroll clipping.
 */
const SvSecondHitBadge: React.FC<{ hit?: SvSecondHit | null }> = ({ hit }) => {
  const [tip, setTip] = useState<{ top: number; left: number } | null>(null);
  if (!hit) return null;

  const types = hit.sv_types.length ? hit.sv_types.join(', ') : 'SV';
  const zygosity = hit.affected_zygosity ? ` · ${hit.affected_zygosity}` : '';
  const message = hit.has_deletion
    ? `This gene is also hit by a structural variant (${types}${zygosity}). A deletion can remove the second allele and unmask a heterozygous SNV — check for a possible compound heterozygote.`
    : `This gene is also hit by a structural variant (${types}${zygosity}) — a possible cross-type second hit.`;

  const showTip = (event: MouseEvent<HTMLSpanElement> | FocusEvent<HTMLSpanElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setTip({ top: rect.bottom + 6, left: rect.left });
  };
  const hideTip = () => setTip(null);

  return (
    <>
      <span
        className={`sv-second-hit-badge${hit.has_deletion ? ' sv-second-hit-badge--del' : ''}`}
        tabIndex={0}
        onMouseEnter={showTip}
        onMouseLeave={hideTip}
        onFocus={showTip}
        onBlur={hideTip}
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
      {tip ? (
        <span
          className="sv-second-hit-tooltip"
          style={{ top: tip.top, left: tip.left }}
          role="tooltip"
        >
          {message}
        </span>
      ) : null}
    </>
  );
};

export default SvSecondHitBadge;
