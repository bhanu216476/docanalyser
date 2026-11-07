import React, { useState, useRef, useEffect } from 'react';
import { Paperclip, ArrowUp, ChevronDown, Check, FileText } from 'lucide-react';

export default function StudyComposer({
  queryInput,
  setQueryInput,
  isQuerying,
  handleSendQuery,
  documents = [],
  selectedDocId = 'all',
  setSelectedDocId
}) {
  const [showDocPicker, setShowDocPicker] = useState(false);
  const textareaRef = useRef(null);
  const pickerRef = useRef(null);

  const charCount = queryInput.length;
  const maxChars = 1000;
  const canSend = queryInput.trim().length > 0 && !isQuerying;

  // Auto-resize textarea based on content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [queryInput]);

  // Close picker on outside click
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) {
        setShowDocPicker(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (canSend) {
        handleSendQuery(e);
      }
    }
  };

  const selectedDocObj = documents.find(d => d.id === selectedDocId);
  const docLabel = selectedDocId === 'all'
    ? (documents.length > 0 ? `${documents.length} docs available` : 'No docs attached yet')
    : (selectedDocObj?.title || selectedDocObj?.fileName || '1 doc attached');

  return (
    <div className="study-composer-anchor">
      <div className="study-composer-card">
        {/* Input Textarea */}
        <textarea
          ref={textareaRef}
          rows={1}
          placeholder="Ask anything about your uploaded documents..."
          value={queryInput}
          onChange={(e) => setQueryInput(e.target.value.slice(0, maxChars))}
          onKeyDown={handleKeyDown}
          disabled={isQuerying}
          className="study-composer-textarea"
        />

        {/* Bottom Metadata & Send Action */}
        <div className="study-composer-bottom">
          {/* Document Attachment Indicator / Picker */}
          <div ref={pickerRef} style={{ position: 'relative' }}>
            <button
              type="button"
              onClick={() => setShowDocPicker(!showDocPicker)}
              className={`study-doc-attach-pill ${selectedDocId !== 'all' ? 'has-doc' : ''}`}
              title="Filter by specific document"
            >
              <Paperclip size={13} style={{ color: selectedDocId !== 'all' ? 'var(--ac)' : 'var(--mu)' }} />
              <span style={{ maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {docLabel}
              </span>
              <ChevronDown size={11} style={{ opacity: 0.6 }} />
            </button>

            {/* Document Picker Dropdown */}
            {showDocPicker && (
              <div
                style={{
                  position: 'absolute',
                  bottom: '36px',
                  left: 0,
                  backgroundColor: 'var(--s1)',
                  border: '1px solid var(--bd)',
                  borderRadius: 'var(--r-md)',
                  boxShadow: 'var(--shadow-lg)',
                  padding: '6px',
                  minWidth: '240px',
                  maxWidth: '300px',
                  zIndex: 50,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '2px'
                }}
              >
                <div style={{ padding: '4px 8px', fontSize: '11px', fontWeight: 600, color: 'var(--mu)', textTransform: 'uppercase' }}>
                  Target Document Context
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedDocId('all');
                    setShowDocPicker(false);
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 10px',
                    borderRadius: 'var(--r-sm)',
                    border: 'none',
                    background: selectedDocId === 'all' ? 'var(--ac-light)' : 'transparent',
                    color: selectedDocId === 'all' ? 'var(--ac)' : 'var(--tx)',
                    fontSize: '12px',
                    cursor: 'pointer',
                    textAlign: 'left'
                  }}
                >
                  <span>All documents ({documents.length})</span>
                  {selectedDocId === 'all' && <Check size={13} />}
                </button>

                {documents.map((doc) => {
                  const isCur = selectedDocId === doc.id;
                  return (
                    <button
                      key={doc.id}
                      type="button"
                      onClick={() => {
                        setSelectedDocId(doc.id);
                        setShowDocPicker(false);
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '6px 10px',
                        borderRadius: 'var(--r-sm)',
                        border: 'none',
                        background: isCur ? 'var(--ac-light)' : 'transparent',
                        color: isCur ? 'var(--ac)' : 'var(--tx)',
                        fontSize: '12px',
                        cursor: 'pointer',
                        textAlign: 'left'
                      }}
                    >
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {doc.title || doc.fileName}
                      </span>
                      {isCur && <Check size={13} style={{ flexShrink: 0 }} />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right Side: Char Counter & Circular Up-Arrow Send Button */}
          <div className="study-composer-actions">
            <span className="study-char-count">
              {charCount}/{maxChars}
            </span>

            <button
              type="button"
              onClick={handleSendQuery}
              disabled={!canSend}
              className={`btn-send-round ${canSend ? 'active' : ''}`}
              title="Send message (Enter)"
              aria-label="Send message"
            >
              <ArrowUp size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

