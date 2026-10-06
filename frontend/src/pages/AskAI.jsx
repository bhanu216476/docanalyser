import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, Sparkles, HelpCircle, Loader, FileText, ArrowUpRight } from 'lucide-react';
import CitationBadge from '../components/CitationBadge';
import VerifiedPill from '../components/VerifiedPill';
import DocumentViewer from '../components/DocumentViewer';
import Composer from '../components/Composer';

export default function AskAI({
  messages = [],
  queryInput,
  setQueryInput,
  isQuerying,
  handleSendQuery,
  documents = []
}) {
  const [activeCitationId, setActiveCitationId] = useState(null);
  const [currentCitations, setCurrentCitations] = useState([]);
  const [isMobileViewerOpen, setIsMobileViewerOpen] = useState(false);
  const bottomRef = useRef(null);

  // Suggested question cards for empty state
  const suggestedQuestions = [
    "What are the core architecture components of our Hybrid RAG system?",
    "How does citation verification guarantee response faithfulness?",
    "Summarize key document ingestion pipelines and indexing stages.",
    "Explain Reciprocal Rank Fusion (RRF) and cross-encoder reranking."
  ];

  // Auto-scroll to bottom of chat on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });

    // Update active citations list from last assistant message with citations
    const lastAiMsg = [...messages].reverse().find(m => m.role === 'assistant' && m.meta?.citations?.length > 0);
    if (lastAiMsg && lastAiMsg.meta?.citations) {
      setCurrentCitations(lastAiMsg.meta.citations);
    }
  }, [messages, isQuerying]);

  const handleSelectCitation = (citationId) => {
    setActiveCitationId(citationId);
    setIsMobileViewerOpen(true);
  };

  const handleSuggestionClick = (questionText) => {
    setQueryInput(questionText);
    setTimeout(() => {
      handleSendQuery();
    }, 50);
  };

  // Helper to parse answer text and turn [1], [2] into interactive CitationBadges
  const renderFormattedAnswer = (text, citations = []) => {
    if (!text) return null;
    const parts = text.split(/(\[\d+\])/g);

    return parts.map((part, index) => {
      const match = part.match(/^\[(\d+)\]$/);
      if (match) {
        const citationNum = parseInt(match[1], 10);
        const isActive = activeCitationId === citationNum;
        return (
          <CitationBadge
            key={index}
            index={citationNum}
            label={part}
            isActive={isActive}
            onClick={() => handleSelectCitation(citationNum)}
          />
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  const hasUserMessages = messages.some(m => m.role === 'user');

  return (
    <div
      style={{
        display: 'flex',
        height: 'calc(100vh - 54px)',
        width: '100%',
        overflow: 'hidden',
        backgroundColor: 'var(--bg)'
      }}
    >
      {/* ============================================================
         LEFT CHAT COLUMN (430px desktop, 380px @ 1024px, 100% @ <900px)
         ============================================================ */}
      <div
        style={{
          width: '100%',
          maxWidth: '430px',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: 'var(--s1)',
          borderRight: '1px solid var(--bd)',
          flexShrink: 0
        }}
        className="ask-chat-column"
      >
        {/* Chat Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--bd)',
            backgroundColor: 'var(--s1)'
          }}
        >
          <h1 className="chat-heading">Ask your knowledge base</h1>
          <p style={{ fontSize: '12.5px', color: 'var(--t2)', marginTop: '4px' }}>
            Answers come with proof from your own documents.
          </p>
        </div>

        {/* Messages Body Scroll Area */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px'
          }}
        >
          {/* Empty State when no user query yet */}
          {!hasUserMessages && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--ac)' }}>
                <Sparkles size={16} />
                <span style={{ fontSize: '13px', fontWeight: 600 }}>Ask questions about your documents</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {suggestedQuestions.map((qText, idx) => (
                  <div
                    key={idx}
                    onClick={() => handleSuggestionClick(qText)}
                    className="card"
                    style={{
                      padding: '12px 14px',
                      cursor: 'pointer',
                      fontSize: '12.5px',
                      color: 'var(--tx)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      transition: 'border-color 0.15s ease, background-color 0.15s ease'
                    }}
                  >
                    <span>{qText}</span>
                    <ArrowUpRight size={14} style={{ color: 'var(--mu)', flexShrink: 0 }} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Messages trajectory */}
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id || Math.random()}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.15 }}
              >
                {msg.role === 'user' ? (
                  /* User Message: Right aligned bubble */
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <div
                      style={{
                        maxWidth: '88%',
                        padding: '10px 14px',
                        backgroundColor: 'var(--s2)',
                        border: '1px solid var(--bd)',
                        borderRadius: '12px 12px 2px 12px',
                        color: 'var(--tx)',
                        fontSize: '13px',
                        lineHeight: 1.55
                      }}
                    >
                      {msg.text}
                    </div>
                  </div>
                ) : (
                  /* AI Message: Structured non-bubble content */
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {/* Status counts bar */}
                    {msg.meta && (
                      <div
                        style={{
                          fontSize: '11.5px',
                          color: 'var(--t2)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          fontWeight: 500
                        }}
                      >
                        <Check size={13} style={{ color: 'var(--ok)' }} />
                        <span>
                          Searched {msg.meta.searchedDocuments || documents.length || 2} documents ·{' '}
                          {msg.meta.passagesFound || 14} passages found ·{' '}
                          {msg.meta.citations?.length || msg.meta.citedCount || 2} cited
                        </span>
                      </div>
                    )}

                    {/* Main Answer paragraph */}
                    <div className="answer-body">
                      {renderFormattedAnswer(msg.text, msg.meta?.citations)}
                    </div>

                    {/* Verification status pill */}
                    {msg.meta?.verification && (
                      <div style={{ marginTop: '4px' }}>
                        <VerifiedPill verification={msg.meta.verification} />
                      </div>
                    )}

                    {/* Follow-up suggestions */}
                    {msg.meta?.citations?.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
                        <button
                          type="button"
                          className="suggestion-chip"
                          onClick={() => handleSuggestionClick("Can you expand on citation verification details?")}
                        >
                          Expand verification details
                        </button>
                        <button
                          type="button"
                          className="suggestion-chip"
                          onClick={() => handleSuggestionClick("Show retrieval pipeline confidence scores.")}
                        >
                          View confidence breakdown
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Loading Skeleton & Progress State */}
          {isQuerying && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '12px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--ac)', fontSize: '12.5px', fontWeight: 500 }}>
                <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}>
                  <Loader size={14} />
                </motion.div>
                <span>Searching documents → Ranking passages → Writing answer → Verifying sources...</span>
              </div>
              <div style={{ height: '12px', width: '85%', borderRadius: '4px', backgroundColor: 'var(--s2)' }} className="animate-shimmer" />
              <div style={{ height: '12px', width: '65%', borderRadius: '4px', backgroundColor: 'var(--s2)' }} className="animate-shimmer" />
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Pinned Composer */}
        <Composer
          queryInput={queryInput}
          setQueryInput={setQueryInput}
          isQuerying={isQuerying}
          handleSendQuery={handleSendQuery}
          documents={documents}
        />
      </div>

      {/* ============================================================
         RIGHT DOCUMENT VIEWER COLUMN (Remaining width)
         ============================================================ */}
      <div style={{ flex: 1, height: '100%', minWidth: 0 }}>
        <DocumentViewer
          citations={currentCitations}
          activeCitationId={activeCitationId}
          onSelectCitation={(id) => setActiveCitationId(id)}
        />
      </div>

      {/* Mobile Slide-Over Panel (<900px) */}
      {isMobileViewerOpen && (
        <div className="sheet-overlay" onClick={() => setIsMobileViewerOpen(false)}>
          <div className="sheet-content" onClick={(e) => e.stopPropagation()} style={{ padding: 0, width: '90%', maxWidth: '540px' }}>
            <DocumentViewer
              citations={currentCitations}
              activeCitationId={activeCitationId}
              onSelectCitation={(id) => setActiveCitationId(id)}
              onCloseMobile={() => setIsMobileViewerOpen(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
