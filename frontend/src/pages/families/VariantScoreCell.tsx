import { useState } from 'react';

import { type SmallVariant } from './smallVariantSearch';
import VariantPriorityBlock from './VariantPriorityBlock';

/**
 * The table's Score cell with a reliable hover/focus popover showing the priority
 * breakdown. A fixed-positioned popover (rather than a native `title`, which is easy to
 * miss, or a CSS tooltip, which the table's scroll container would clip) so the
 * breakdown is always visible.
 */
export default function VariantScoreCell({ variant }: { variant: SmallVariant }) {
  const [anchor, setAnchor] = useState<{ top: number; left: number } | null>(null);
  const priority = variant.priority;

  if (!priority) {
    return <td className="table-mono">—</td>;
  }

  const open = (event: React.MouseEvent | React.FocusEvent) => {
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    setAnchor({ top: rect.bottom + 6, left: rect.left });
  };
  const close = () => setAnchor(null);

  return (
    <td className="table-mono variant-score-cell">
      <span
        className="variant-priority-score"
        tabIndex={0}
        role="button"
        aria-label={`Priority score ${priority.combined_score.toFixed(2)} — hover for the breakdown`}
        onMouseEnter={open}
        onMouseLeave={close}
        onFocus={open}
        onBlur={close}
      >
        {priority.combined_score.toFixed(2)}
        {priority.phenotype_matches.length ? (
          <span className="variant-priority-pheno" aria-hidden>
            ✦
          </span>
        ) : null}
      </span>
      {anchor ? (
        <div
          className="variant-priority-popover"
          role="tooltip"
          style={{ top: anchor.top, left: anchor.left }}
        >
          <VariantPriorityBlock priority={priority} />
        </div>
      ) : null}
    </td>
  );
}
