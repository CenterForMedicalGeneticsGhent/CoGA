import React from 'react';

interface AdminModalProps {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

/** Lightweight admin dialog: backdrop + centered card with a title and close. */
const AdminModal: React.FC<AdminModalProps> = ({ title, onClose, children }) => (
  <div
    className="modal-backdrop"
    role="dialog"
    aria-modal="true"
    aria-label={title}
    onClick={onClose}
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
