import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import InfoTip from '../InfoTip';

describe('InfoTip', () => {
  it('shows the tooltip on hover and hides on leave', () => {
    render(<InfoTip label="Derived from the analysis">Affected / at risk</InfoTip>);
    const trigger = screen.getByText('Affected / at risk');
    expect(screen.queryByRole('tooltip')).toBeNull();

    fireEvent.mouseEnter(trigger);
    expect(screen.getByRole('tooltip').textContent).toBe('Derived from the analysis');

    fireEvent.mouseLeave(trigger);
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('also shows on keyboard focus (accessible)', () => {
    render(<InfoTip label="explain">chip</InfoTip>);
    fireEvent.focus(screen.getByText('chip'));
    expect(screen.getByRole('tooltip').textContent).toBe('explain');
  });
});
