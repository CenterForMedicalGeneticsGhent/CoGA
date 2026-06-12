import React from 'react';

interface AdminModalProps {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  /**
   * When another modal is stacked on top of this one, mark it inactive: the
   * dialog drops `aria-modal`, is hidden from assistive tech, and becomes
   * inert (non-focusable / non-interactive) so only the topmost dialog is
   * modal and keyboard focus can't reach the obscured content underneath.
   */
  inactive?: boolean;
}

/** Lightweight admin dialog: backdrop + centered card with a title and close. */
const AdminModal: React.FC<AdminModalProps> = ({ title, onClose, children, inactive = false }) => (
  <div
    className="modal-backdrop"
    role="dialog"
    aria-modal={inactive ? undefined : 'true'}
    aria-hidden={inactive || undefined}
    aria-label={title}
    inert={inactive}
    onClick={inactive ? undefined : onClose}
  >
    <div
      className="modal-surface surface-card admin-modal"
      onClick={(event) => event.stopPropagation()}
    >
      <div className="analysis-toolbar items-center">
        <h2 className="section-title">{title}</h2>
        <button
          type="button"
          className="button-ghost"
          style={{ marginLeft: 'auto' }}
          onClick={onClose}
          aria-label="Close"
        >
          Close
        </button>
      </div>
      <div className="admin-modal-body">{children}</div>
    </div>
  </div>
);

export default AdminModal;
