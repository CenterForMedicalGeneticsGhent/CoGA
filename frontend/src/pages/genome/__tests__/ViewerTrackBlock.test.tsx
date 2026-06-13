import { createEvent, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ViewerTrackBlock from '../ViewerTrackBlock';

const dispatchMouseEvent = (
  element: HTMLElement,
  type: 'mouseDown' | 'mouseMove' | 'mouseUp',
  offsetX: number,
  options?: { shiftKey?: boolean; button?: number },
) => {
  const event = createEvent[type](element, {
    bubbles: true,
    button: options?.button ?? 0,
    shiftKey: options?.shiftKey ?? false,
  });
  // The block measures x from the frame's bounding box + clientX (jsdom reports a
  // zero-origin rect, so clientX maps directly to the in-frame x). We deliberately
  // do NOT set offsetX — the fix must not depend on it.
  Object.defineProperty(event, 'clientX', { value: offsetX });
  fireEvent(element, event);
};

describe('ViewerTrackBlock', () => {
  it('zooms the viewport when dragging across a track block', () => {
    const onChange = vi.fn();

    render(
      <ViewerTrackBlock
        label="Coverage"
        width={200}
        viewportInteraction={{
          chromSize: 1000,
          regionStart: 100,
          regionEnd: 300,
          onChange,
        }}
      >
        <div style={{ height: 20 }} />
      </ViewerTrackBlock>,
    );

    const track = screen.getByRole('application', { name: /coverage viewport/i });
    dispatchMouseEvent(track, 'mouseDown', 50);
    dispatchMouseEvent(track, 'mouseMove', 150);
    dispatchMouseEvent(track, 'mouseUp', 150);

    expect(onChange).toHaveBeenCalledWith(150, 250);
  });

  it('zooms when the drag starts on a nested child element (e.g. an SVG feature)', () => {
    const onChange = vi.fn();

    render(
      <ViewerTrackBlock
        label="SVs"
        width={200}
        viewportInteraction={{
          chromSize: 1000,
          regionStart: 100,
          regionEnd: 300,
          onChange,
        }}
      >
        <svg>
          <rect data-testid="feature" x={120} y={0} width={8} height={20} />
        </svg>
      </ViewerTrackBlock>,
    );

    // Events fire on the inner <rect>, not the frame — they must still be measured
    // relative to the frame (clientX), not the child (which broke offsetX-based zoom).
    const feature = screen.getByTestId('feature');
    dispatchMouseEvent(feature, 'mouseDown', 50);
    dispatchMouseEvent(feature, 'mouseMove', 150);
    dispatchMouseEvent(feature, 'mouseUp', 150);

    expect(onChange).toHaveBeenCalledWith(150, 250);
  });

  it('ignores shift-drag panning and wheel input', () => {
    const onChange = vi.fn();

    render(
      <ViewerTrackBlock
        label="SVs"
        width={200}
        viewportInteraction={{
          chromSize: 1000,
          regionStart: 200,
          regionEnd: 400,
          onChange,
        }}
      >
        <div style={{ height: 20 }} />
      </ViewerTrackBlock>,
    );

    const track = screen.getByRole('application', { name: /svs viewport/i });
    dispatchMouseEvent(track, 'mouseDown', 100, { shiftKey: true });
    dispatchMouseEvent(track, 'mouseMove', 150, { shiftKey: true });
    dispatchMouseEvent(track, 'mouseUp', 150, { shiftKey: true });

    expect(onChange).toHaveBeenCalledWith(300, 350);
    onChange.mockClear();

    const wheelEvent = createEvent.wheel(track, {
      bubbles: true,
      clientX: 100,
      deltaY: -100,
    });
    fireEvent(track, wheelEvent);

    expect(onChange).not.toHaveBeenCalled();
  });
});
