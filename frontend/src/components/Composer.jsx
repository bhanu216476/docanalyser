import React, { useState } from 'react';
import { Send, Paperclip, ChevronDown, ArrowRight } from 'lucide-react';

export default function Composer({
  queryInput,
  setQueryInput,
  isQuerying,
  handleSendQuery,
  documents = []
}) {
  const [selectedDocId, setSelectedDocId] = useState('all');
  const [showDocSelect, setShowDocSelect] = useState(false);

  const selectedDocLabel = selectedDocId === 'all'
    ? 'All documents'
    : (documents.find(d => d.id === selectedDocId)?.title || 'Selected document');

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendQuery(e);
    }
  };

  return (
    <div
      style={{
        borderTop: '1px solid var(--bd)',
        backgroundColor: 'var(--s1)',
        padding: '14px 18px',
        width: '100%'
      }}
    >
      <form onSubmit={handleSendQuery}>
        {/* Main Textarea Container */}
        <div
          style={{
            backgroundColor: 'var(--s2)',
            border: '1px solid var(--bd)',
            borderRadius: 'var(--r-lg)',
            padding: '10px 14px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            boxShadow: 'var(--shadow-sm)',
            transition: 'border-color 0.15s ease'
          }}
        >
          <textarea
            rows={2}
            placeholder="Ask anything about your documents..."
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={isQuerying}
            style={{
              width: '100%',
              background: 'transparent',
              border: 'none',
              outline: 'none',
              resize: 'none',
              color: 'var(--tx)',
              fontSize: '13.5px',
              fontFamily: 'inherit',
              lineHeight: 1.5
            }}
          />

          {/* Controls row */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '4px' }}>
            {/* Left controls: Document Scope Selector */}
            <div style={{ position: 'relative' }}>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setShowDocSelect(!showDocSelect)}
                style={{
                  padding: '4px 8px',
                  fontSize: '12px',
                  color: 'var(--t2)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  border: '1px solid var(--bd)',
                  borderRadius: 'var(--r-sm)'
                }}
              >
                <Paperclip size={13} style={{ color: 'var(--ac)' }} />
                <span>{selectedDocLabel}</span>
                <ChevronDown size={12} />
              </button>

              {showDocSelect && (
                <div
                  style={{
                    position: 'absolute',
                    bottom: '34px',
                    left: 0,
                    backgroundColor: 'var(--s1)',
                    border: '1px solid var(--bd)',
                    borderRadius: 'var(--r-md)',
                    boxShadow: 'var(--shadow-md)',
                    padding: '6px',
                    minWidth: '200px',
                    zIndex: 50
                  }}
                >
                  <div
                    onClick={() => { setSelectedDocId('all'); setShowDocSelect(false); }}
                    style={{
                      padding: '6px 10px',
                      fontSize: '12px',
                      borderRadius: 'var(--r-sm)',
                      cursor: 'pointer',
                      color: selectedDocId === 'all' ? 'var(--ac)' : 'var(--tx)',
                      fontWeight: selectedDocId === 'all' ? 600 : 400,
                      backgroundColor: selectedDocId === 'all' ? 'var(--s2)' : 'transparent'
                    }}
                  >
                    All documents
                  </div>
                  {documents.map((doc) => (
                    <div
                      key={doc.id}
                      onClick={() => { setSelectedDocId(doc.id); setShowDocSelect(false); }}
                      style={{
                        padding: '6px 10px',
                        fontSize: '12px',
                        borderRadius: 'var(--r-sm)',
                        cursor: 'pointer',
                        color: selectedDocId === doc.id ? 'var(--ac)' : 'var(--tx)',
                        fontWeight: selectedDocId === doc.id ? 600 : 400,
                        backgroundColor: selectedDocId === doc.id ? 'var(--s2)' : 'transparent',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {doc.title || doc.fileName}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Right control: Submit Ask button */}
            <button
              type="submit"
              disabled={isQuerying || !queryInput.trim()}
              className="btn btn-primary"
              style={{
                padding: '6px 14px',
                fontSize: '13px',
                opacity: queryInput.trim() && !isQuerying ? 1 : 0.6,
                cursor: queryInput.trim() && !isQuerying ? 'pointer' : 'not-allowed'
              }}
            >
              <span>Ask</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
