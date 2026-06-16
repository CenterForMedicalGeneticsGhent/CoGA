import React from 'react';
import type { ApiFamilyStatusRef } from '../lib/apiTypes';

interface FamilyStatusBadgeProps {
  status?: ApiFamilyStatusRef | null;
}

/** Coloured pill for a family's workflow status; renders an em dash when unset. */
const FamilyStatusBadge: React.FC<FamilyStatusBadgeProps> = ({ status }) => {
  if (!status) {
    return <span className="family-status-badge family-status-badge--empty">—</span>;
  }
  return (
    <span className="family-status-badge" title={status.label}>
      <span
        className="family-status-dot"
        style={{ backgroundColor: status.color }}
        aria-hidden="true"
      />
      <span className="family-status-label">{status.label}</span>
    </span>
  );
};

export default FamilyStatusBadge;
