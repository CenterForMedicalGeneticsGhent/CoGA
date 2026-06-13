import React, { useMemo, useRef, useState } from 'react';
import RoiMarkerOverlay from '../../components/visualizations/RoiMarkerOverlay';

interface ViewerRoiRange {
  startX: number;
  endX: number;
}

interface ViewerTrackBlockProps {
  label: string;
  width: number;
  children: React.ReactNode;
  meta?: React.ReactNode;
  frameClassName?: string;
  roiRange?: ViewerRoiRange | null;
  roiTitle?: string;
  viewportInteraction?: {
    chromSize: number;
    regionStart: number;
    regionEnd: number;
    onChange: (start: number, end: number) => void;
  };
}

const clampViewport = (start: number, end: number, chromSize: number) => {
  const safeSpan = Math.max(Math.round(end - start), 1);
  if (safeSpan >= chromSize) {
    return { start: 0, end: chromSize };
  }

  let nextStart = Math.round(start);
  let nextEnd = nextStart + safeSpan;

  if (nextStart < 0) {
    nextStart = 0;
    nextEnd = safeSpan;
  }
  if (nextEnd > chromSize) {
    nextEnd = chromSize;
    nextStart = chromSize - safeSpan;
  }

  return { start: nextStart, end: Math.max(nextEnd, nextStart + 1) };
};

const ViewerTrackBlock: React.FC<ViewerTrackBlockProps> = ({
  label,
  width,
  children,
  meta,
  frameClassName,
  roiRange,
  roiTitle,
  viewportInteraction,
}) => {
  const frameRef = useRef<HTMLDivElement | null>(null);
  const [dragStart, setDragStart] = useState<number | null>(null);
  const [dragCurrent, setDragCurrent] = useState<number | null>(null);

  const span = Math.max(
    (viewportInteraction?.regionEnd ?? 0) - (viewportInteraction?.regionStart ?? 0),
    1,
  );

  // x within the track frame, derived from the frame's own bounding box rather
  // than event.offsetX. offsetX is relative to whichever child element the event
  // lands on (an SVG <rect>, a canvas, a tooltip hitbox, …), so drag-to-zoom only
  // worked on tracks whose content was a single element at the frame's origin.
  // Measuring against the frame makes zoom work uniformly on every track.
  const frameOffsetX = (event: React.MouseEvent<HTMLDivElement>): number => {
    const rect = frameRef.current?.getBoundingClientRect();
    const x = rect ? event.clientX - rect.left : event.nativeEvent.offsetX;
    return Math.max(0, Math.min(x, width));
  };

  const commitViewport = (start: number, end: number) => {
    if (!viewportInteraction) return;
    const nextViewport = clampViewport(start, end, viewportInteraction.chromSize);
    viewportInteraction.onChange(nextViewport.start, nextViewport.end);
  };

  const handleMouseDown = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!viewportInteraction || event.button !== 0) return;
    const x = frameOffsetX(event);
    setDragStart(x);
    setDragCurrent(x);
  };

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (dragStart === null) return;
    setDragCurrent(frameOffsetX(event));
  };

  const clearDrag = () => {
    setDragStart(null);
    setDragCurrent(null);
  };

  const handleMouseUp = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!viewportInteraction || dragStart === null) {
      clearDrag();
      return;
    }

    const endX = frameOffsetX(event);
    const x1 = Math.min(dragStart, endX);
    const x2 = Math.max(dragStart, endX);
    clearDrag();
    if (Math.abs(x2 - x1) < 5) return;
    const nextStart = viewportInteraction.regionStart + (x1 / width) * span;
    const nextEnd = viewportInteraction.regionStart + (x2 / width) * span;
    commitViewport(nextStart, nextEnd);
  };

  const dragRectStyle = useMemo<React.CSSProperties | undefined>(() => {
    if (dragStart === null || dragCurrent === null) return undefined;
    const left = Math.min(dragStart, dragCurrent);
    return {
      left,
      width: Math.abs(dragCurrent - dragStart),
    };
  }, [dragCurrent, dragStart]);

  const interactiveClassName = viewportInteraction
    ? `viewer-track-interactive viewer-track-interactive--${dragStart !== null ? 'zoom' : 'idle'}`
    : undefined;

  return (
    <div className="viewer-track-block" style={{ width }}>
      <div className="viewer-track-head">
        <span className="viewer-track-label">{label}</span>
        {meta}
      </div>
      <div
        ref={frameRef}
        className={[
          frameClassName ? `viz-frame ${frameClassName}` : 'viz-frame',
          interactiveClassName,
        ]
          .filter(Boolean)
          .join(' ')}
        style={{ width: '100%' }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={clearDrag}
        role={viewportInteraction ? 'application' : undefined}
        aria-label={viewportInteraction ? `${label} viewport` : undefined}
      >
        {children}
        <RoiMarkerOverlay
          startX={roiRange?.startX ?? null}
          endX={roiRange?.endX ?? null}
          title={roiTitle}
        />
        {dragRectStyle ? <div className="viewer-track-selection" style={dragRectStyle} /> : null}
      </div>
    </div>
  );
};

export default ViewerTrackBlock;
