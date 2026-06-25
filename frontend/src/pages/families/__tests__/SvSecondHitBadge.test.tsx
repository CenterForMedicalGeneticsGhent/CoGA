import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SvSecondHitBadge from '../SvSecondHitBadge';

describe('SvSecondHitBadge', () => {
  it('renders nothing when there is no second hit', () => {
    const { container } = render(<SvSecondHitBadge hit={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows the SV type/count and reveals the deletion tooltip on hover', () => {
    const { container } = render(
      <SvSecondHitBadge
        hit={{ sv_count: 2, sv_types: ['DEL', 'INS'], affected_zygosity: 'het', has_deletion: true }}
      />,
    );
    const badge = container.querySelector('.sv-second-hit-badge') as HTMLElement;
    expect(badge).not.toBeNull();
    expect(badge.classList.contains('sv-second-hit-badge--del')).toBe(true);
    expect(screen.getByText(/SV: DEL, INS/)).toBeInTheDocument();
    expect(screen.getByText(/×2/)).toBeInTheDocument();

    // Tooltip is hidden until hover, then carries the explanation.
    expect(screen.queryByRole('tooltip')).toBeNull();
    fireEvent.mouseEnter(badge);
    expect(screen.getByRole('tooltip').textContent).toMatch(/unmask a heterozygous SNV/i);
    fireEvent.mouseLeave(badge);
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('uses the non-deletion tooltip for a duplication-only hit, on focus too', () => {
    const { container } = render(
      <SvSecondHitBadge
        hit={{ sv_count: 1, sv_types: ['DUP'], affected_zygosity: 'hom', has_deletion: false }}
      />,
    );
    const badge = container.querySelector('.sv-second-hit-badge') as HTMLElement;
    expect(badge.classList.contains('sv-second-hit-badge--del')).toBe(false);
    fireEvent.focus(badge);
    expect(screen.getByRole('tooltip').textContent).toMatch(/cross-type second hit/i);
  });
});
