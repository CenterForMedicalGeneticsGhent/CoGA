import React from 'react';
import { createPortal } from 'react-dom';

interface VizTooltipProps {
  /** Cursor position in viewport coordinates (event.clientX). */
  x: number;
  /** Cursor position in viewport coordinates (event.clientY). */
  y: number;
  children: React.ReactNode;
}

const CURSOR_OFFSET = 12;
// Mirrors the max-width of `.viz-tooltip` (20rem) so we can flip before measuring.
const ESTIMATED_WIDTH = 320;

/**
 * Track hover tooltip rendered through a portal to `document.body` and pinned
 * with `position: fixed`. Tracks live inside `.viz-frame` containers that clip
 * with `overflow: hidden`; rendering here lets the tooltip escape that clip so
 * it always sits above the track below instead of being cut off by it.
 */
export default function VizTooltip({ x, y, children }: VizTooltipProps) {
  if (typeof document === 'undefined') {
    return null;
  }
  const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : ESTIMATED_WIDTH;
  // Flip to the left of the cursor when the tooltip would overflow the right edge.
  const left =
    x + CURSOR_OFFSET + ESTIMATED_WIDTH > viewportWidth
      ? Math.max(CURSOR_OFFSET, x - CURSOR_OFFSET - ESTIMATED_WIDTH)
      : x + CURSOR_OFFSET;
  return createPortal(
    <div className="viz-tooltip viz-tooltip--floating" style={{ left, top: y + CURSOR_OFFSET }}>
      {children}
    </div>,
    document.body,
  );
}
