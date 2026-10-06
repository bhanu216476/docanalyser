import React, { useState } from 'react';
import { FileText, Upload, CheckCircle2, Clock, AlertTriangle, Trash2, RefreshCw, Eye, Search, Plus } from 'lucide-react';
import DocumentDetailsSheet from '../components/DocumentDetailsSheet';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080';

export default function Documents({
  documents = [],
  setDocuments,
  handleUpload,
  isUploading,
  uploadMessage,
  uploadTitle,
  setUploadTitle,
  uploadCategory,
  setUploadCategory,
  uploadContent,
  setUploadContent
}) {
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);

  // Status counts
  const processedCount = documents.filter(d => d.status === 'PROCESSED' || d.status === 'INDEXED' || d.status === 'READY').length;
  const processingCount = documents.filter(d => d.status === 'PROCESSING' || d.status === 'UPLOADED').length;
  const failedCount = documents.filter(d => d.status === 'FAILED').length;

  // Filtered documents list
  const filteredDocs = documents.filter((doc) => {
    const matchesSearch = (doc.title || doc.fileName || '').toLowerCase().includes(searchQuery.toLowerCase());
    if (filterStatus === 'PROCESSED') return matchesSearch && (doc.status === 'PROCESSED' || doc.status === 'INDEXED' || doc.status === 'READY');
    if (filterStatus === 'PROCESSING') return matchesSearch && (doc.status === 'PROCESSING' || doc.status === 'UPLOADED');
    if (filterStatus === 'FAILED') return matchesSearch && doc.status === 'FAILED';
    return matchesSearch;
  });

  // Handle Drag and Drop
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      setUploadTitle(file.name);
      // Read file content if text
      const reader = new FileReader();
      reader.onload = (evt) => {
        setUploadContent(evt.target.result || `File content from ${file.name}`);
      };
      reader.readAsText(file);
    }
  };

  // Real Delete Document Handler
  const handleDeleteDocument = async (id) => {
    if (!window.confirm('Are you sure you want to delete this document from the knowledge base?')) return;
    try {
      const token = localStorage.getItem('token');
      if (token) {
        await fetch(`${API_BASE}/api/documents/${id}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` }
        });
      }
    } catch (e) {}
    setDocuments(prev => prev.filter(d => d.id !== id));
    if (selectedDoc?.id === id) setSelectedDoc(null);
  };

  // Real Retry Ingestion Handler
  const handleRetryDocument = async (id) => {
    try {
      const token = localStorage.getItem('token');
      if (token) {
        await fetch(`${API_BASE}/api/documents/${id}/retry`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` }
        });
      }
    } catch (e) {}

    setDocuments(prev => prev.map(d => d.id === id ? { ...d, status: 'PROCESSING' } : d));
    if (selectedDoc?.id === id) setSelectedDoc(prev => ({ ...prev, status: 'PROCESSING' }));
  };

  return (
    <div style={{ maxWidth: '1200px', width: '100%', margin: '0 auto', padding: '24px' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h1 className="page-title">Documents</h1>
        <p style={{ color: 'var(--t2)', fontSize: '13.5px', marginTop: '4px' }}>
          Add files once, then ask questions about all of them.
        </p>
      </div>

      {/* Main Grid: Left Upload Zone & Form / Right Table */}
      <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: '24px', alignItems: 'start' }}>
        {/* Drag & Drop Upload Zone & Ingestion Form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Drop Zone Box */}
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            className="card"
            style={{
              borderColor: isDragOver ? 'var(--ac)' : 'var(--bd)',
              backgroundColor: isDragOver ? 'var(--s2)' : 'var(--s1)',
              borderStyle: 'dashed',
              borderWidth: '2px',
              textAlign: 'center',
              padding: '28px 20px',
              transition: 'all 0.15s ease'
            }}
          >
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '50%',
                backgroundColor: 'rgba(47, 91, 255, 0.1)',
                color: 'var(--ac)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 12px'
              }}
            >
              <Upload size={20} />
            </div>
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--tx)', marginBottom: '4px' }}>
              Drop files here to add them
            </h3>
            <p style={{ fontSize: '12px', color: 'var(--t2)', marginBottom: '16px' }}>
              PDF, DOCX or TXT · up to 50 MB each
            </p>

            <label className="btn btn-secondary" style={{ display: 'inline-flex', cursor: 'pointer' }}>
              <span>Browse files</span>
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    const f = e.target.files[0];
                    setUploadTitle(f.name);
                    const reader = new FileReader();
                    reader.onload = (evt) => setUploadContent(evt.target.result || '');
                    reader.readAsText(f);
                  }
                }}
                style={{ display: 'none' }}
              />
            </label>
          </div>

          {/* Quick Ingestion Form */}
          <div className="card">
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--tx)', marginBottom: '14px' }}>
              Ingest Document Details
            </h3>

            {uploadMessage && (
              <div
                style={{
                  padding: '10px 12px',
                  borderRadius: 'var(--r-md)',
                  backgroundColor: uploadMessage.type === 'success' ? 'rgba(15,123,87,0.1)' : 'rgba(229,72,77,0.1)',
                  color: uploadMessage.type === 'success' ? 'var(--ok)' : 'var(--err)',
                  fontSize: '12px',
                  marginBottom: '14px'
                }}
              >
                {uploadMessage.text}
              </div>
            )}

            <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 500, color: 'var(--t2)', display: 'block', marginBottom: '4px' }}>
                  Document Name / Title
                </label>
                <input
                  type="text"
                  placeholder="e.g. Q4 Financial Report.pdf"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  className="input-base"
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 500, color: 'var(--t2)', display: 'block', marginBottom: '4px' }}>
                  Collection / Category
                </label>
                <select
                  value={uploadCategory}
                  onChange={(e) => setUploadCategory(e.target.value)}
                  className="input-base"
                  style={{ cursor: 'pointer' }}
                >
                  {['Engineering', 'Research', 'Architecture', 'Operations', 'Security', 'Legal'].map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 500, color: 'var(--t2)', display: 'block', marginBottom: '4px' }}>
                  Document Text / Content
                </label>
                <textarea
                  rows={4}
                  placeholder="Paste document text or content snippet for embedding vector index..."
                  value={uploadContent}
                  onChange={(e) => setUploadContent(e.target.value)}
                  className="input-base"
                  style={{ resize: 'vertical' }}
                  required
                />
              </div>

              <button
                type="submit"
                disabled={isUploading || !uploadTitle.trim()}
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '4px' }}
              >
                {isUploading ? (
                  <>
                    <Clock size={14} className="animate-spin" />
                    <span>Indexing document...</span>
                  </>
                ) : (
                  <>
                    <Plus size={14} />
                    <span>Upload & Index</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right Table Section */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Filters & Search Row */}
          <div className="card" style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
            {/* Filter pills */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                type="button"
                onClick={() => setFilterStatus('ALL')}
                className="btn btn-ghost"
                style={{
                  padding: '5px 12px',
                  fontSize: '12.5px',
                  backgroundColor: filterStatus === 'ALL' ? 'var(--s2)' : 'transparent',
                  color: filterStatus === 'ALL' ? 'var(--tx)' : 'var(--t2)',
                  fontWeight: filterStatus === 'ALL' ? 600 : 400
                }}
              >
                All ({documents.length})
              </button>
              <button
                type="button"
                onClick={() => setFilterStatus('PROCESSED')}
                className="btn btn-ghost"
                style={{
                  padding: '5px 12px',
                  fontSize: '12.5px',
                  backgroundColor: filterStatus === 'PROCESSED' ? 'var(--s2)' : 'transparent',
                  color: filterStatus === 'PROCESSED' ? 'var(--ok)' : 'var(--t2)',
                  fontWeight: filterStatus === 'PROCESSED' ? 600 : 400
                }}
              >
                Processed ({processedCount})
              </button>
              <button
                type="button"
                onClick={() => setFilterStatus('PROCESSING')}
                className="btn btn-ghost"
                style={{
                  padding: '5px 12px',
                  fontSize: '12.5px',
                  backgroundColor: filterStatus === 'PROCESSING' ? 'var(--s2)' : 'transparent',
                  color: filterStatus === 'PROCESSING' ? 'var(--ac)' : 'var(--t2)',
                  fontWeight: filterStatus === 'PROCESSING' ? 600 : 400
                }}
              >
                Processing ({processingCount})
              </button>
              <button
                type="button"
                onClick={() => setFilterStatus('FAILED')}
                className="btn btn-ghost"
                style={{
                  padding: '5px 12px',
                  fontSize: '12.5px',
                  backgroundColor: filterStatus === 'FAILED' ? 'var(--s2)' : 'transparent',
                  color: filterStatus === 'FAILED' ? 'var(--err)' : 'var(--t2)',
                  fontWeight: filterStatus === 'FAILED' ? 600 : 400
                }}
              >
                Failed ({failedCount})
              </button>
            </div>

            {/* Filter Search Input */}
            <div style={{ position: 'relative', width: '220px' }}>
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--mu)' }} />
              <input
                type="text"
                placeholder="Filter by name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-base"
                style={{ paddingLeft: '32px', paddingTop: '6px', paddingBottom: '6px', fontSize: '12.5px' }}
              />
            </div>
          </div>

          {/* Document Table Card */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {filteredDocs.length === 0 ? (
              <div style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--t2)' }}>
                <FileText size={36} style={{ color: 'var(--mu)', marginBottom: '12px', opacity: 0.6 }} />
                <h3 style={{ fontSize: '15px', color: 'var(--tx)', marginBottom: '4px' }}>No documents found</h3>
                <p style={{ fontSize: '12.5px' }}>Upload a file or change your search filter.</p>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Collection</th>
                    <th>Chunks</th>
                    <th>Status</th>
                    <th>Indexed</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDocs.map((doc) => {
                    const name = doc.title || doc.fileName || 'Document';
                    const ext = (doc.fileName?.split('.').pop() || 'pdf').toLowerCase();
                    const isProcessed = doc.status === 'PROCESSED' || doc.status === 'INDEXED' || doc.status === 'READY';
                    const isFailed = doc.status === 'FAILED';

                    return (
                      <tr
                        key={doc.id}
                        onClick={() => setSelectedDoc(doc)}
                        style={{ cursor: 'pointer' }}
                      >
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span className={`file-badge ${ext === 'pdf' ? 'pdf' : ext === 'docx' ? 'docx' : 'other'}`}>
                              {ext.toUpperCase()}
                            </span>
                            <span style={{ fontWeight: 600, color: 'var(--tx)' }}>{name}</span>
                          </div>
                        </td>
                        <td>
                          <span style={{ fontSize: '12px', color: 'var(--t2)' }}>{doc.category || 'Engineering'}</span>
                        </td>
                        <td>
                          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '12px', fontWeight: 600, color: 'var(--ac)' }}>
                            {doc.chunks || 0}
                          </span>
                        </td>
                        <td>
                          {isProcessed ? (
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: 'var(--ok)', fontSize: '12px', fontWeight: 500 }}>
                              <CheckCircle2 size={13} />
                              <span>Processed</span>
                            </div>
                          ) : isFailed ? (
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: 'var(--err)', fontSize: '12px', fontWeight: 500 }}>
                              <AlertTriangle size={13} />
                              <span>Failed</span>
                            </div>
                          ) : (
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: 'var(--ac)', fontSize: '12px', fontWeight: 500 }}>
                              <Clock size={13} className="animate-spin" />
                              <span>Processing</span>
                            </div>
                          )}
                        </td>
                        <td style={{ fontSize: '12px', color: 'var(--mu)' }}>
                          {doc.uploadedAt || 'Recently'}
                        </td>
                        <td style={{ textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                          <div style={{ display: 'inline-flex', gap: '4px' }}>
                            <button
                              type="button"
                              className="btn btn-ghost"
                              onClick={() => setSelectedDoc(doc)}
                              title="View Document Details"
                              style={{ padding: '4px 8px' }}
                            >
                              <Eye size={14} />
                            </button>

                            {isFailed && (
                              <button
                                type="button"
                                className="btn btn-ghost"
                                onClick={() => handleRetryDocument(doc.id)}
                                title="Retry Ingestion"
                                style={{ padding: '4px 8px', color: 'var(--ac)' }}
                              >
                                <RefreshCw size={14} />
                              </button>
                            )}

                            <button
                              type="button"
                              className="btn btn-ghost"
                              onClick={() => handleDeleteDocument(doc.id)}
                              title="Delete Document"
                              style={{ padding: '4px 8px', color: 'var(--err)' }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Details Sheet Modal */}
      {selectedDoc && (
        <DocumentDetailsSheet
          document={selectedDoc}
          onClose={() => setSelectedDoc(null)}
          onDelete={handleDeleteDocument}
          onRetry={handleRetryDocument}
        />
      )}
    </div>
  );
}
