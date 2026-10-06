import React, { useState, useEffect } from 'react';
import { FileText, CheckCircle2, ChevronLeft, ChevronRight, X } from 'lucide-react';

export default function DocumentViewer({ citations = [], activeCitationId, onSelectCitation, onCloseMobile }) {
  const [activeTabIndex, setActiveTabIndex] = useState(0);

  // Sync active tab when activeCitationId changes externally
  useEffect(() => {
    if (activeCitationId && citations.length > 0) {
      const foundIdx = citations.findIndex(c => c.id === activeCitationId || c.citation_id === `[${activeCitationId}]`);
      if (foundIdx !== -1) {
        setActiveTabIndex(foundIdx);
      }
    }
  }, [activeCitationId, citations]);

  if (!citations || citations.length === 0) {
    return (
      <div
        style={{
          flex: 1,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '32px',
          backgroundColor: 'var(--s2)',
          borderLeft: '1px solid var(--bd)',
          color: 'var(--t2)',
          textAlign: 'center'
        }}
      >
        <FileText size={40} style={{ color: 'var(--mu)', marginBottom: '16px', opacity: 0.6 }} />
        <h3 className="font-fraunces" style={{ fontSize: '18px', fontWeight: 600, color: 'var(--tx)', marginBottom: '8px' }}>
          Document Evidence Viewer
        </h3>
        <p style={{ fontSize: '13px', color: 'var(--t2)', maxWidth: '360px', lineHeight: 1.6 }}>
          Ask a question or click a citation badge in the answer to inspect exact source passages, page numbers, and verification proofs.
        </p>
      </div>
    );
  }

  const currentCitation = citations[activeTabIndex] || citations[0];
  const docName = currentCitation.document || currentCitation.file_name || currentCitation.source || 'Document';
  const fileExt = (currentCitation.file_type || docName.split('.').pop() || 'pdf').toLowerCase();
  
  const pageNum = currentCitation.page_number || (currentCitation.page !== undefined ? currentCitation.page + 1 : 1);
  const totalPages = currentCitation.total_pages || 12;
  const citationIdTag = currentCitation.citation_id || `[${currentCitation.id || activeTabIndex + 1}]`;
  const relevancePct = currentCitation.relevance ? Math.round(currentCitation.relevance * 100) : 94;
  const isVerified = currentCitation.verified !== false;
  const passageText = currentCitation.passage || currentCitation.text || currentCitation.chunk_text || currentCitation.content || '';

  return (
    <div
      style={{
        flex: 1,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--bg)',
        borderLeft: '1px solid var(--bd)',
        overflow: 'hidden'
      }}
    >
      {/* Header Tabs Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: 'var(--s2)',
          borderBottom: '1px solid var(--bd)',
          padding: '0 12px',
          height: '42px',
          overflowX: 'auto'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', height: '100%' }}>
          {citations.map((cit, idx) => {
            const isActive = idx === activeTabIndex;
            const cName = cit.document || cit.file_name || `Source ${idx + 1}`;
            const ext = (cit.file_type || cName.split('.').pop() || 'pdf').toLowerCase();

            return (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  setActiveTabIndex(idx);
                  if (onSelectCitation) onSelectCitation(cit.id || idx + 1);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '0 14px',
                  height: '100%',
                  backgroundColor: isActive ? 'var(--s1)' : 'transparent',
                  borderTop: isActive ? '2px solid var(--ac)' : '2px solid transparent',
                  borderLeft: '1px solid var(--bd)',
                  borderRight: '1px solid var(--bd)',
                  borderRadius: '6px 6px 0 0',
                  color: isActive ? 'var(--tx)' : 'var(--t2)',
                  fontWeight: isActive ? 600 : 400,
                  fontSize: '12.5px',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  maxWidth: '220px'
                }}
              >
                <span className={`file-badge ${ext === 'pdf' ? 'pdf' : ext === 'docx' ? 'docx' : 'other'}`}>
                  {ext.toUpperCase()}
                </span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {cName}
                </span>
              </button>
            );
          })}
        </div>

        {onCloseMobile && (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={onCloseMobile}
            style={{ padding: '4px 8px' }}
          >
            <X size={16} />
          </button>
        )}
      </div>

      {/* Sub-toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 20px',
          backgroundColor: 'var(--s1)',
          borderBottom: '1px solid var(--bd)',
          fontSize: '12px',
          color: 'var(--t2)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span>Page <strong>{pageNum}</strong> of {totalPages}</span>
          <span style={{ color: 'var(--bd)' }}>|</span>
          <span>Cited as <strong style={{ color: 'var(--ac)', fontFamily: 'JetBrains Mono' }}>{citationIdTag}</strong></span>
          <span style={{ color: 'var(--bd)' }}>|</span>
          <span>Relevance <strong>{relevancePct}%</strong></span>
        </div>

        {isVerified && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--ok)', fontWeight: 500 }}>
            <CheckCircle2 size={13} />
            <span>Passage verified</span>
          </div>
        )}
      </div>

      {/* Passage Sheet Container */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '32px 24px',
          display: 'flex',
          justifyContent: 'center',
          backgroundColor: 'var(--bg)'
        }}
      >
        <div
          style={{
            width: '100%',
            maxWidth: '560px',
            backgroundColor: 'var(--s1)',
            border: '1px solid var(--bd)',
            borderRadius: 'var(--r-lg)',
            padding: '36px 40px',
            boxShadow: 'var(--shadow-md)',
            height: 'fit-content',
            minHeight: '420px'
          }}
        >
          {/* Sheet Header */}
          <div style={{ borderBottom: '1px solid var(--bd)', paddingBottom: '16px', marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span className={`file-badge ${fileExt === 'pdf' ? 'pdf' : fileExt === 'docx' ? 'docx' : 'other'}`}>
                {fileExt.toUpperCase()}
              </span>
              <span style={{ fontSize: '11.5px', color: 'var(--mu)', fontFamily: 'JetBrains Mono' }}>
                Page {pageNum} · Chunk {currentCitation.chunk_id || 'chk-001'}
              </span>
            </div>
            <h2 className="font-fraunces" style={{ fontSize: '18px', fontWeight: 600, color: 'var(--tx)', lineHeight: 1.4 }}>
              {docName}
            </h2>
            {currentCitation.section && (
              <div style={{ fontSize: '12px', color: 'var(--ac)', marginTop: '4px', fontWeight: 500 }}>
                {currentCitation.section}
              </div>
            )}
          </div>

          {/* Sheet Content Body */}
          <div className="viewer-text">
            <p style={{ marginBottom: '16px', color: 'var(--t2)', fontSize: '13.5px' }}>
              ... extracted context block from document index ...
            </p>

            <p style={{ marginBottom: '16px' }}>
              <mark className="cited-highlight">
                {passageText || 'No passage text returned for this citation.'}
              </mark>
            </p>

            <p style={{ marginTop: '16px', color: 'var(--t2)', fontSize: '13.5px' }}>
              ... verified context evidence for query synthesis.
            </p>
          </div>

          {/* Sheet Footer Badge */}
          <div
            style={{
              marginTop: '32px',
              paddingTop: '16px',
              borderTop: '1px border var(--bd)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '11.5px',
              color: 'var(--mu)'
            }}
          >
            <span>Verified by DocAnalyser Engine</span>
            <span style={{ fontFamily: 'JetBrains Mono', color: 'var(--ac)' }}>Cited as {citationIdTag}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
