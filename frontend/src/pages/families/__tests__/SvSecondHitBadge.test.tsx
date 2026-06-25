import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SvSecondHitBadge from '../SvSecondHitBadge';

describe('SvSecondHitBadge', () => {
  it('renders nothing when there is no second hit', () => {
    const { container } = render(<SvSecondHitBadge hit={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows the SV type and count, with the deletion styling and tooltip', () => {
    const { container } = render(
      <SvSecondHitBadge
        hit={{ sv_count: 2, sv_types: ['DEL', 'INS'], affected_zygosity: 'het', has_deletion: true }}
      />,
    );
    const badge = container.querySelector('.sv-second-hit-badge');
    expect(badge).not.toBeNull();
    expect(badge?.classList.contains('sv-second-hit-badge--del')).toBe(true);
    expect(screen.getByText(/SV: DEL, INS/)).toBeInTheDocument();
    expect(screen.getByText(/×2/)).toBeInTheDocument();
    expect(badge?.getAttribute('title')).toMatch(/unmask a heterozygous SNV/i);
  });

  it('uses the non-deletion styling for a duplication-only hit', () => {
    const { container } = render(
      <SvSecondHitBadge
        hit={{ sv_count: 1, sv_types: ['DUP'], affected_zygosity: 'hom', has_deletion: false }}
      />,
    );
    const badge = container.querySelector('.sv-second-hit-badge');
    expect(badge?.classList.contains('sv-second-hit-badge--del')).toBe(false);
    expect(badge?.getAttribute('title')).toMatch(/cross-type second hit/i);
  });
});
