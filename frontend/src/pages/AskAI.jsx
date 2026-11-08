import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Sparkles, Bot, FileText, CheckCircle2, 
  HelpCircle, ChevronRight, X, ArrowUpRight,
  BookOpen, Zap, Target, FileCheck, Lightbulb,
  Copy, Check, RotateCcw, Trash2
} from 'lucide-react';
import RobotMascot from '../components/RobotMascot';
import StudyComposer from '../components/StudyComposer';
import CitationBadge from '../components/CitationBadge';
import VerifiedPill from '../components/VerifiedPill';
import MarkdownRenderer from '../components/MarkdownRenderer';

export default function AskAI({
  messages = [],
  queryInput,
  setQueryInput,
  isQuerying,
  handleSendQuery,
  handleRegenerateQuery,
  handleClearChat,
  documents = [],
  selectedDocId = 'all',
  setSelectedDocId
}) {
  const [activeCitation, setActiveCitation] = useState(null);
  const [activeEvidenceModal, setActiveEvidenceModal] = useState(false);
  const [studyMode, setStudyMode] = useState('deep'); // 'deep' | 'flashcards' | 'quiz' | 'summary'
  const [copiedMsgId, setCopiedMsgId] = useState(null);
  const [thinkingStepIdx, setThinkingStepIdx] = useState(0);
  const bottomRef = useRef(null);

  const thinkingSteps = [
    "Searching across indexed document passages... 🔍",
    "Analyzing semantic context & verifying citations... 📖",
    "Synthesizing key insights & structuring findings... 💡",
    "Writing a clear, natural explanation for you... ✨"
  ];

  useEffect(() => {
    if (!isQuerying) {
      setThinkingStepIdx(0);
      return;
    }
    const timer = setInterval(() => {
      setThinkingStepIdx(prev => (prev + 1) % thinkingSteps.length);
    }, 1800);
    return () => clearInterval(timer);
  }, [isQuerying, thinkingSteps.length]);

  // Dynamic quick prompt cards based on active mode
  const cardsByMode = {
    deep: [
      {
        title: "Key Document Insights",
        desc: "Extract core themes and definitions",
        prompt: "What are the core concepts and fundamental definitions in the uploaded documents?"
      },
      {
        title: "Contextual Understanding",
        desc: "Explain complex mechanisms clearly",
        prompt: "Provide a clear, contextual explanation of the most complex mechanism discussed in these documents."
      },
      {
        title: "💡 Related Information",
        desc: "Explore implications and applications",
        prompt: "What are practical next steps, key implications, or related areas mentioned in these documents?"
      },
      {
        title: "🎯 Document Knowledge Check",
        desc: "Validate comprehension of key points",
        prompt: "Generate 5 questions based on the uploaded documents to test comprehension of the material."
      }
    ],
    flashcards: [
      {
        title: "⚡ Terminology & Entities",
        desc: "Key terms & concise definitions",
        prompt: "Identify and define the key technical terms, entities, and specialized vocabulary in these documents."
      },
      {
        title: "🧠 Cause & Effect Analysis",
        desc: "Analyze mechanisms and linkages",
        prompt: "Analyze the cause-and-effect relationships and mechanisms described across the documents."
      },
      {
        title: "📐 Standards & Specifications",
        desc: "Rules, criteria, and metrics",
        prompt: "Extract the core standards, specifications, rules, or formulas detailed in the documents."
      },
      {
        title: "🎯 Multi-Source Retrieval",
        desc: "In-depth cross-document search",
        prompt: "Retrieve nuanced details, critical caveats, and edge cases across all uploaded documents."
      }
    ],
    quiz: [
      {
        title: "🎯 Evidence Grounding Check",
        desc: "Verify factual claims against sources",
        prompt: "List the primary factual claims made in the documents along with exact citations supporting each claim."
      },
      {
        title: "❓ Verification Inquiries",
        desc: "Cross-reference key statements",
        prompt: "Cross-reference the findings across sections and highlight any corroborating or conflicting statements."
      },
      {
        title: "🔍 Detect Inconsistencies",
        desc: "Identify ambiguities or contradictions",
        prompt: "Identify any ambiguities, conflicting claims, or potential contradictions within the uploaded text."
      },
      {
        title: "⏱️ Fact Extraction Drill",
        desc: "Fast, verified factual retrieval",
        prompt: "Extract 5 verified key facts directly grounded in the text with precise source references."
      }
    ],
    summary: [
      {
        title: "📋 Executive Summary",
        desc: "Structured overview and takeaways",
        prompt: "Generate a structured executive summary summarizing all key sections, findings, and takeaways."
      },
      {
        title: "📊 Topic Hierarchy",
        desc: "Organized outline & relationships",
        prompt: "Break down the knowledge in these documents into an organized hierarchical outline with main topics and sub-topics."
      },
      {
        title: "💡 Practical Applications",
        desc: "Operational use cases and impact",
        prompt: "Provide concrete real-world applications and operational use cases for the concepts explained in these documents."
      },
      {
        title: "🔑 Critical Rules & Methodologies",
        desc: "Core logic and procedural steps",
        prompt: "List all methodologies, key procedures, and critical guidelines discussed in the documents with clear explanations."
      }
    ]
  };

  // Quick Action Chips
  const quickActionChips = [
    { label: "⚡ Generate Key Insights", prompt: "Extract the key insights and findings from the uploaded documents." },
    { label: "🎯 Test Document Understanding", prompt: "Test my understanding of these documents with 3 targeted questions." },
    { label: "📝 Generate Summary", prompt: "Generate a comprehensive summary of the main topics in these documents." },
    { label: "💡 Simplify Explanation", prompt: "Explain the central concepts in simple, accessible terms as if I were a beginner." }
  ];

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isQuerying]);

  const handleCardClick = (promptText) => {
    setQueryInput(promptText);
    handleSendQuery(null, promptText);
  };

  const handleCopyMessage = (text, id) => {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopiedMsgId(id);
      setTimeout(() => setCopiedMsgId(null), 2000);
    }).catch(err => console.warn('Copy failed', err));
  };

  const hasUserMessages = messages.some(m => m.role === 'user');
  const activeCards = cardsByMode[studyMode] || cardsByMode.deep;
  const activeDoc = selectedDocId !== 'all' ? documents.find(d => d.id === selectedDocId) : null;
  const isDocFailed = activeDoc && (activeDoc.status === 'FAILED' || activeDoc.status === 'ERROR');

  return (
    <div className="study-main-area">
      {/* Scrollable Chat Viewport */}
      <div className="study-chat-scroll">
        {!hasUserMessages ? (
          /* ========================================================
             HERO EMPTY STATE WITH MADDY & ENHANCED ELEMENTS
             ======================================================== */
          <div className="study-hero-state">
            {/* Animated Floating Robot Mascot MADDY (Hero Waving Mode) */}
            <RobotMascot
              size="hero"
              mode="hero"
              speech="Hi! I'm Maddy ✨"
            />

            {/* Headline & Subtitle */}
            <h1 className="study-hero-title">
              What would you like to know about your documents?
            </h1>
            <p className="study-hero-subtitle">
              Upload your documents and explore their contents using intelligent hybrid retrieval.
            </p>

            {/* Quick Action Chips (New Interactive Element) */}
            <div className="quick-action-chips">
              {quickActionChips.map((chip, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleCardClick(chip.prompt)}
                  className="action-chip-pill"
                >
                  <Sparkles size={13} style={{ color: 'var(--ac)' }} />
                  <span>{chip.label}</span>
                </button>
              ))}
            </div>

            {/* Interactive Mode Tab Switcher */}
            <div className="study-mode-tabs-container">
              <button
                type="button"
                onClick={() => setStudyMode('deep')}
                className={`study-mode-tab-btn ${studyMode === 'deep' ? 'active' : ''}`}
              >
                <BookOpen size={13} />
                <span>Document Q&A</span>
              </button>
              <button
                type="button"
                onClick={() => setStudyMode('flashcards')}
                className={`study-mode-tab-btn ${studyMode === 'flashcards' ? 'active' : ''}`}
              >
                <Zap size={13} />
                <span>Hybrid Retrieval</span>
              </button>
              <button
                type="button"
                onClick={() => setStudyMode('quiz')}
                className={`study-mode-tab-btn ${studyMode === 'quiz' ? 'active' : ''}`}
              >
                <Target size={13} />
                <span>Citation Verification</span>
              </button>
              <button
                type="button"
                onClick={() => setStudyMode('summary')}
                className={`study-mode-tab-btn ${studyMode === 'summary' ? 'active' : ''}`}
              >
                <FileCheck size={13} />
                <span>Document Summary</span>
              </button>
            </div>

            {/* 2x2 Quick Prompt Cards Grid */}
            <div className="study-prompt-grid">
              {activeCards.map((card, idx) => (
                <motion.div
                  key={`${studyMode}-${idx}`}
                  whileHover={{ y: -3, scale: 1.015 }}
                  transition={{ duration: 0.18 }}
                  onClick={() => handleCardClick(card.prompt)}
                  className="study-prompt-card"
                >
                  <div className="study-prompt-title">
                    <span>{card.title}</span>
                    <ArrowUpRight size={13} style={{ opacity: 0.6, marginLeft: 'auto' }} />
                  </div>
                  <div className="study-prompt-desc">
                    {card.desc}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        ) : (
          /* ========================================================
             ACTIVE CONVERSATION THREAD
             ======================================================== */
          <div style={{ width: '100%', maxWidth: '740px', display: 'flex', flexDirection: 'column', gap: '22px' }}>
            {/* Header controls bar */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 14px',
                backgroundColor: 'var(--s1)',
                borderRadius: '10px',
                border: '1px solid var(--bd)',
                marginBottom: '4px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: 600 }}>
                <Sparkles size={14} style={{ color: 'var(--ac)' }} />
                <span>Chatting with Maddy AI</span>
                <span style={{ fontSize: '11px', color: 'var(--mu)', fontWeight: 400 }}>• Natural AI Companion</span>
              </div>
              {handleClearChat && (
                <button
                  type="button"
                  onClick={handleClearChat}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--mu)',
                    fontSize: '11.5px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 8px',
                    borderRadius: '6px'
                  }}
                  title="Clear chat and start fresh"
                >
                  <Trash2 size={12} />
                  <span>Clear chat</span>
                </button>
              )}
            </div>

            {/* Warning if filtered to a failed document */}
            {isDocFailed && (
              <div
                style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '10px',
                  fontSize: '12.5px',
                  color: '#EF4444'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <HelpCircle size={15} />
                  <span>
                    <strong>{activeDoc.title || activeDoc.fileName}</strong> failed during ingestion and has no indexed content.
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedDocId('all')}
                  style={{
                    background: '#EF4444',
                    color: '#FFFFFF',
                    border: 'none',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    fontSize: '11.5px',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  Clear Filter
                </button>
              </div>
            )}

            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <motion.div
                  key={msg.id || Math.random()}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    width: '100%'
                  }}
                >
                  {msg.role === 'user' ? (
                    /* User Message Bubble */
                    <div
                      style={{
                        maxWidth: '82%',
                        padding: '12px 18px',
                        backgroundColor: 'var(--ac)',
                        color: '#FFFFFF',
                        borderRadius: '18px 18px 4px 18px',
                        fontSize: '13.5px',
                        lineHeight: 1.5,
                        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)'
                      }}
                    >
                      {msg.text}
                    </div>
                  ) : (
                    /* AI Assistant Message */
                    <div style={{ display: 'flex', gap: '12px', maxWidth: '94%', width: '100%' }}>
                      {/* Mascot Mini Avatar MADDY */}
                      <div style={{ flexShrink: 0, marginTop: '2px' }}>
                        <RobotMascot size="sm" />
                      </div>

                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {/* Meta status bar if citations/confidence available */}
                        {msg.meta && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                            {msg.meta.confidence > 0 && (
                              <VerifiedPill
                                score={msg.meta.confidence}
                                verification={msg.meta.verification}
                              />
                            )}
                            {msg.meta.citations?.length > 0 && (
                              <span style={{ fontSize: '11px', color: 'var(--mu)', fontWeight: 500 }}>
                                Grounded in {msg.meta.citations.length} sources
                              </span>
                            )}
                          </div>
                        )}

                        {/* Answer text container with Rich Markdown rendering */}
                        <div
                          style={{
                            backgroundColor: 'var(--s1)',
                            border: '1px solid var(--bd)',
                            borderRadius: '4px 18px 18px 18px',
                            padding: '14px 18px',
                            fontSize: '13.5px',
                            lineHeight: 1.6,
                            color: 'var(--tx)',
                            boxShadow: 'var(--shadow-card)'
                          }}
                        >
                          <MarkdownRenderer
                            content={msg.text}
                            citations={msg.meta?.citations || []}
                            activeCitation={activeCitation}
                            onCitationClick={(cit) => {
                              setActiveCitation(cit);
                              setActiveEvidenceModal(true);
                            }}
                          />
                        </div>

                        {/* Action buttons below assistant response */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '2px', fontSize: '11.5px', color: 'var(--mu)' }}>
                          <button
                            type="button"
                            onClick={() => handleCopyMessage(msg.text, msg.id)}
                            style={{
                              background: 'transparent',
                              border: 'none',
                              color: copiedMsgId === msg.id ? '#10B981' : 'var(--mu)',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '2px 6px',
                              borderRadius: '4px'
                            }}
                            title="Copy answer"
                          >
                            {copiedMsgId === msg.id ? (
                              <>
                                <Check size={12} />
                                <span>Copied!</span>
                              </>
                            ) : (
                              <>
                                <Copy size={12} />
                                <span>Copy answer</span>
                              </>
                            )}
                          </button>

                          {handleRegenerateQuery && (
                            <button
                              type="button"
                              onClick={handleRegenerateQuery}
                              disabled={isQuerying}
                              style={{
                                background: 'transparent',
                                border: 'none',
                                color: 'var(--mu)',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '2px 6px',
                                borderRadius: '4px'
                              }}
                              title="Regenerate this response"
                            >
                              <RotateCcw size={12} />
                              <span>Regenerate</span>
                            </button>
                          )}

                          <span style={{ marginLeft: 'auto', fontSize: '10.5px', opacity: 0.7 }}>
                            Maddy AI • Friendly Companion
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {/* Animated Thinking Maddy Card (Active during response generation) */}
            {isQuerying && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="maddy-thinking-card"
              >
                <RobotMascot size="sm" mode="thinking" />
                <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12.5px', fontWeight: 600, color: 'var(--tx)' }}>
                    <span>Maddy is thinking...</span>
                    <span style={{ fontSize: '11px', color: 'var(--ac)' }}>✨ Active</span>
                  </div>
                  <div style={{ fontSize: '11.5px', color: 'var(--mu)', minHeight: '18px', transition: 'all 0.3s ease' }}>
                    {thinkingSteps[thinkingStepIdx]}
                  </div>
                </div>
              </motion.div>
            )}

            <div ref={bottomRef} style={{ height: '40px' }} />
          </div>
        )}
      </div>

      {/* Floating Bottom Input Composer */}
      <StudyComposer
        queryInput={queryInput}
        setQueryInput={setQueryInput}
        isQuerying={isQuerying}
        handleSendQuery={handleSendQuery}
        documents={documents}
        selectedDocId={selectedDocId}
        setSelectedDocId={setSelectedDocId}
      />

      {/* Floating Bottom-Right Companion Mascot ("Ask MADDY...") */}
      <div
        className="floating-corner-bot"
        onClick={() => {
          const textarea = document.querySelector('.study-composer-textarea');
          if (textarea) textarea.focus();
        }}
        title="MADDY — AI Document Assistant"
      >
        <div className="floating-bot-bubble">
          Ask MADDY...
        </div>
        <RobotMascot size="sm" />
      </div>

      {/* Citation Evidence Sheet Modal (When citation badge is clicked) */}
      {activeEvidenceModal && activeCitation && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.55)',
            backdropFilter: 'blur(4px)',
            zIndex: 70,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px'
          }}
          onClick={() => setActiveEvidenceModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              backgroundColor: 'var(--s1)',
              border: '1px solid var(--bd)',
              borderRadius: 'var(--r-xl)',
              maxWidth: '520px',
              width: '100%',
              padding: '22px',
              boxShadow: 'var(--shadow-lg)',
              animation: 'fadeIn 0.2s ease-out'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="badge badge-cyan" style={{ fontSize: '12px' }}>
                  Citation [{activeCitation.index || 1}]
                </span>
                <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--tx)' }}>
                  {activeCitation.document_title || activeCitation.file_name || 'Grounding Source'}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setActiveEvidenceModal(false)}
                className="icon-button"
              >
                <X size={16} />
              </button>
            </div>

            <div
              style={{
                backgroundColor: 'var(--s2)',
                padding: '14px',
                borderRadius: 'var(--r-md)',
                fontSize: '13px',
                lineHeight: 1.55,
                color: 'var(--tx)',
                maxHeight: '260px',
                overflowY: 'auto',
                borderLeft: '3px solid var(--ac)'
              }}
            >
              {activeCitation.text || activeCitation.excerpt || activeCitation.chunk_text || 'Source excerpt text'}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '14px', fontSize: '11.5px', color: 'var(--mu)' }}>
              <span>Page / Section: {activeCitation.page || activeCitation.section || 'N/A'}</span>
              <span>Relevance Score: {activeCitation.score ? `${Math.round(activeCitation.score * 100)}%` : 'Verified'}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
