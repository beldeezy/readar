import React from 'react';
import './EmptyState.css';

interface EmptyStateProps {
  art?: React.ReactNode;
  title: string;
  message?: React.ReactNode;
  action?: React.ReactNode;
  compact?: boolean;
}

/**
 * Consistent empty/zero-state: flat illustration + title + message + optional action.
 */
export default function EmptyState({ art, title, message, action, compact }: EmptyStateProps) {
  return (
    <div className={`rd-empty${compact ? ' rd-empty--compact' : ''}`}>
      {art && <div className="rd-empty-art">{art}</div>}
      <h3 className="rd-empty-title">{title}</h3>
      {message && <p className="rd-empty-message">{message}</p>}
      {action && <div className="rd-empty-action">{action}</div>}
    </div>
  );
}
