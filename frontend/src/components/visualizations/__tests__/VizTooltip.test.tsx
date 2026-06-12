import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import VizTooltip from '../VizTooltip';

const getTooltip = () => document.body.querySelector<HTMLElement>('.viz-tooltip');

describe('VizTooltip', () => {
  it('portals a fixed, floating tooltip to the document body', () => {
    const { container } = render(
      <VizTooltip x={100} y={200}>
        <div>hello</div>
      </VizTooltip>,
    );

    // Rendered through a portal, not inside the component's own subtree.
    expect(container.querySelector('.viz-tooltip')).toBeNull();
    const tooltip = getTooltip();
    expect(tooltip).not.toBeNull();
    expect(tooltip).toHaveClass('viz-tooltip--floating');
    expect(tooltip?.textContent).toBe('hello');
    expect(tooltip?.style.left).toBe('112px'); // x + 12 offset
    expect(tooltip?.style.top).toBe('212px'); // y + 12 offset
  });

  it('flips to the left of the cursor when it would overflow the right edge', () => {
    // jsdom defaults window.innerWidth to 1024; x=1000 would overflow.
    render(
      <VizTooltip x={1000} y={50}>
        <div>edge</div>
      </VizTooltip>,
    );

    const tooltip = getTooltip();
    // 1000 - 12 - 320 = 668
    expect(tooltip?.style.left).toBe('668px');
    expect(tooltip?.style.top).toBe('62px');
  });
});
