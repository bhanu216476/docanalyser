import React from 'react';
import { X, FileText, Calendar, Database, Hash, AlertTriangle, RefreshCw, Trash2 } from 'lucide-react';

export default function DocumentDetailsSheet({ document, onClose, onDelete, onRetry }) {
  if (!document) return null;

  const docName = document.title || document.fileName || 'Untitled Document';
  const fileExt = (document.fileName?.split('.').pop() || 'pdf').toLowerCase();

  return (
    <div className="sheet-overlay" onClick={onClose}>
      <div className="sheet-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className={`file-badge ${fileExt === 'pdf' ? 'pdf' : fileExt === 'docx' ? 'docx' : 'other'}`}>
              {fileExt.toUpperCase()}
            </span>
            <h3 className="font-fraunces" style={{ fontSize: '18px', fontWeight: 600, color: 'var(--tx)' }}>
              Document Details
            </h3>
          </div>
          <button type="button" className="btn btn-ghost" onClick={onClose} style={{ padding: '4px' }}>
            <X size={18} />
          </button>
        </div>

        {/* Title */}
        <div className="card" style={{ marginBottom: '16px' }}>
          <div style={{ fontSize: '11px', color: 'var(--mu)', textTransform: 'uppercase', marginBottom: '4px' }}>
            Document Name
          </div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--tx)' }}>
            {docName}
          </div>
        </div>

        {/* Metadata Details Grid */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: 'var(--s2)', borderRadius: 'var(--r-md)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--t2)', fontSize: '13px' }}>
              <Database size={15} style={{ color: 'var(--ac)' }} />
              <span>Status</span>
            </div>
            <span style={{ fontWeight: 600, color: document.status === 'PROCESSED' ? 'var(--ok)' : document.status === 'FAILED' ? 'var(--err)' : 'var(--ac)' }}>
              {document.status}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: 'var(--s2)', borderRadius: 'var(--r-md)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--t2)', fontSize: '13px' }}>
              <FileText size={15} style={{ color: 'var(--ac)' }} />
              <span>Collection / Source</span>
            </div>
            <span style={{ fontWeight: 500, color: 'var(--tx)' }}>{document.category || 'Engineering'}</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: 'var(--s2)', borderRadius: 'var(--r-md)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--t2)', fontSize: '13px' }}>
              <Hash size={15} style={{ color: 'var(--ac)' }} />
              <span>Indexed Chunks</span>
            </div>
            <span style={{ fontFamily: 'JetBrains Mono', fontWeight: 600, color: 'var(--tx)' }}>{document.chunks || 0}</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: 'var(--s2)', borderRadius: 'var(--r-md)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--t2)', fontSize: '13px' }}>
              <Calendar size={15} style={{ color: 'var(--ac)' }} />
              <span>Uploaded At</span>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--t2)' }}>{document.uploadedAt || 'Recently'}</span>
          </div>
        </div>

        {/* Failure reason if FAILED */}
        {document.status === 'FAILED' && (
          <div className="card" style={{ borderColor: 'rgba(229,72,77,0.3)', backgroundColor: 'rgba(229,72,77,0.06)', marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--err)', fontWeight: 600, fontSize: '13px', marginBottom: '6px' }}>
              <AlertTriangle size={15} />
              <span>Ingestion Failure Reason</span>
            </div>
            <p style={{ fontSize: '12.5px', color: 'var(--tx)', lineHeight: 1.5 }}>
              {document.error || 'Qdrant vector store connection timed out during embedding extraction.'}
            </p>
          </div>
        )}

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: '10px', marginTop: 'auto' }}>
          {document.status === 'FAILED' && onRetry && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => onRetry(document.id)}
              style={{ flex: 1 }}
            >
              <RefreshCw size={14} />
              <span>Retry Ingestion</span>
            </button>
          )}

          {onDelete && (
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => onDelete(document.id)}
              style={{ flex: 1 }}
            >
              <Trash2 size={14} />
              <span>Delete Document</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
