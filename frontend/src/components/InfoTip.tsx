import React, { useState } from 'react';
import { createPortal } from 'react-dom';

/**
 * A small, reliable hover/focus tooltip that renders into document.body (fixed
 * position) so it is never clipped by a scrolling table container — and appears
 * immediately, unlike the native `title` attribute. Use for inline chips/badges in
 * tables where a CSS `::after` tooltip would be clipped by `overflow: auto`.
 */
interface Props {
  label: string;
  className?: string;
  children: React.ReactNode;
  as?: 'span';
}

const TIP_WIDTH = 260;

const InfoTip: React.FC<Props> = ({ label, className, children }) => {
  const [anchor, setAnchor] = useState<DOMRect | null>(null);

  const show = (el: HTMLElement) => setAnchor(el.getBoundingClientRect());
  const hide = () => setAnchor(null);

  return (
    <>
      <span
        className={className}
        tabIndex={0}
        role="button"
        aria-label={label}
        onMouseEnter={(e) => show(e.currentTarget)}
        onMouseLeave={hide}
        onFocus={(e) => show(e.currentTarget)}
        onBlur={hide}
      >
        {children}
      </span>
      {anchor &&
        createPortal(
          <div
            role="tooltip"
            className="info-tip-popover"
            style={{
              position: 'fixed',
              left: Math.max(8, Math.min(anchor.left, window.innerWidth - TIP_WIDTH - 8)),
              top: anchor.bottom + 6,
              width: TIP_WIDTH,
            }}
          >
            {label}
          </div>,
          document.body,
        )}
    </>
  );
};

export default InfoTip;
