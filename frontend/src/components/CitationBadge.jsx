import React from 'react';

export default function CitationBadge({ index, label, isActive, onClick }) {
  const displayLabel = label || `[${index}]`;

  return (
    <span
      className={`citation-badge ${isActive ? 'active' : ''}`}
      onClick={(e) => {
        e.stopPropagation();
        if (onClick) onClick(index);
      }}
      title={`Click to view citation source ${displayLabel}`}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (onClick) onClick(index);
        }
      }}
    >
      {displayLabel}
    </span>
  );
}
