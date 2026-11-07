import React, { useRef, useState } from 'react';
import { 
  SquarePen, UploadCloud, FileText, CheckCircle2, 
  ShieldCheck, Trash2, Loader2, Sparkles, AlertCircle 
} from 'lucide-react';

export default function StudySidebar({
  isOpen = true,
  onStartNewChat,
  documents = [],
  selectedDocId = 'all',
  setSelectedDocId,
  onUploadFile,
  isUploading = false,
  uploadMessage = null,
  onDeleteDocument
}) {
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file && onUploadFile) {
      onUploadFile(file);
    }
    // Reset file input so user can re-upload same file if desired
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && onUploadFile) {
      onUploadFile(file);
    }
  };

  return (
    <aside className={`study-sidebar ${!isOpen ? 'collapsed' : ''}`} aria-label="Documents Sidebar">
      <div className="study-sidebar-content">
        {/* Start New Chat Button */}
        <button
          type="button"
          onClick={onStartNewChat}
          className="btn-new-chat"
        >
          <SquarePen size={15} style={{ color: 'var(--ac)' }} />
          <span>Start new chat</span>
        </button>

        {/* Documents Heading & Badge */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div className="study-materials-header">
            <h2 className="study-materials-title">Documents</h2>
            <span className="study-badge-pill">PDF, TXT, MD</span>
          </div>
          <p className="study-materials-desc">
            Upload enterprise documents, research papers, or technical reports (up to 50MB).
          </p>
        </div>

        {/* Drag & Drop Upload Zone */}
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`study-dropzone ${isDragging ? 'dragging' : ''}`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />

          <div className="study-dropzone-icon-circle">
            {isUploading ? (
              <Loader2 size={22} className="animate-spin" />
            ) : (
              <UploadCloud size={22} />
            )}
          </div>

          <div className="study-dropzone-cta">
            <strong>Click to upload</strong> or drag & drop
          </div>
          <div className="study-dropzone-sub">
            PDF, TXT, or MD documents (max 50MB)
          </div>
        </div>

        {/* Upload Status Alert (if any) */}
        {uploadMessage && (
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--r-md)',
              fontSize: '11.5px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: uploadMessage.type === 'error' ? 'var(--error-light)' : 'var(--ac-light)',
              color: uploadMessage.type === 'error' ? 'var(--err)' : 'var(--ac)',
              border: `1px solid ${uploadMessage.type === 'error' ? 'rgba(239, 68, 68, 0.2)' : 'var(--ac-border)'}`
            }}
          >
            {uploadMessage.type === 'error' ? <AlertCircle size={14} /> : <CheckCircle2 size={14} />}
            <span>{uploadMessage.text}</span>
          </div>
        )}

        {/* Knowledge Base Card */}
        <div className="knowledge-vitals-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--ac)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Knowledge Base
            </span>
            <span style={{ fontSize: '10px', backgroundColor: 'var(--s1)', padding: '2px 6px', borderRadius: 'var(--r-full)', color: 'var(--ok)', fontWeight: 600, border: '1px solid var(--bd)' }}>
              100% Grounded
            </span>
          </div>
          <div className="vitals-row">
            <span className="vitals-label"><FileText size={12} /> Processed Documents</span>
            <span className="vitals-val">{documents.length}</span>
          </div>
          <div className="vitals-row">
            <span className="vitals-label"><Sparkles size={12} /> Document Chunks</span>
            <span className="vitals-val">
              {documents.reduce((acc, d) => acc + (d.chunks || 12), 0)}
            </span>
          </div>
        </div>

        {/* Document Materials List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--t2)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Uploaded Documents ({documents.length})
            </span>
            {selectedDocId !== 'all' && (
              <button
                type="button"
                onClick={() => setSelectedDocId('all')}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '11px',
                  color: 'var(--ac)',
                  cursor: 'pointer',
                  fontWeight: 500
                }}
              >
                Clear filter
              </button>
            )}
          </div>

          <div className="study-docs-list">
            {documents.length === 0 ? (
              <div style={{ fontSize: '12px', color: 'var(--mu)', textAlign: 'center', padding: '16px 0' }}>
                No documents uploaded yet
              </div>
            ) : (
              documents.map((doc) => {
                const isSelected = selectedDocId === doc.id;
                return (
                  <div
                    key={doc.id}
                    onClick={() => setSelectedDocId(isSelected ? 'all' : doc.id)}
                    className={`study-doc-item ${isSelected ? 'active' : ''}`}
                    title={isSelected ? 'Click to query all documents' : `Focus search on ${doc.title}`}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                      <FileText size={15} style={{ color: isSelected ? 'var(--ac)' : 'var(--mu)', flexShrink: 0 }} />
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{
                          fontSize: '12px',
                          fontWeight: isSelected ? 600 : 500,
                          color: 'var(--tx)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis'
                        }}>
                          {doc.title || doc.fileName}
                        </div>
                        <div style={{ fontSize: '10.5px', color: 'var(--mu)' }}>
                          {doc.chunks ? `${doc.chunks} chunks` : 'Indexed'} • {doc.status || 'Ready'}
                        </div>
                      </div>
                    </div>
                    {isSelected && (
                      <span style={{
                        fontSize: '10px',
                        fontWeight: 600,
                        backgroundColor: 'var(--ac)',
                        color: '#FFFFFF',
                        padding: '1px 6px',
                        borderRadius: 'var(--r-full)'
                      }}>
                        Active
                      </span>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Sidebar Footer: Grounded Answer Mode */}
      <div className="study-sidebar-footer">
        <div className="grounded-badge">
          <ShieldCheck size={16} className="grounded-badge-icon" />
          <span>Grounded Answer Mode</span>
        </div>
      </div>
    </aside>
  );
}

