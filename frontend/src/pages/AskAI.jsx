import React, { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Zap, ShieldCheck, BookOpen, Loader, User } from 'lucide-react';

function UserMessage({ text }) {
  return (
    <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:'1rem' }}>
      <div style={{ maxWidth:'70%', padding:'0.875rem 1.125rem',
        background:'var(--bg-elevated)', border:'1px solid var(--border-subtle)',
        borderRadius:'var(--radius-lg) var(--radius-lg) 4px var(--radius-lg)',
        boxShadow:'var(--shadow-sm)' }}>
        <p style={{ fontSize:'0.9rem', color:'var(--text-primary)', lineHeight:1.6 }}>{text}</p>
      </div>
    </div>
  );
}

function AIMessage({ text, meta }) {
  return (
    <div style={{ display:'flex', gap:'0.75rem', marginBottom:'1.25rem', alignItems:'flex-start' }}>
      {/* AI avatar */}
      <div style={{ width:'32px', height:'32px', borderRadius:'50%', flexShrink:0,
        background:'var(--gradient-primary)', display:'flex', alignItems:'center', justifyContent:'center',
        boxShadow:'0 0 12px rgba(124,92,255,0.35)', marginTop:'2px' }}>
        <Zap size={15} color="#fff" />
      </div>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ padding:'0.875rem 1.125rem',
          background:'linear-gradient(145deg, rgba(124,92,255,0.07) 0%, var(--bg-card) 60%)',
          border:'1px solid rgba(124,92,255,0.15)',
          borderRadius:'4px var(--radius-lg) var(--radius-lg) var(--radius-lg)' }}>
          <p style={{ fontSize:'0.9rem', color:'var(--text-primary)', lineHeight:1.65 }}>{text}</p>
        </div>

        {meta && (
          <div style={{ marginTop:'0.625rem', display:'flex', flexWrap:'wrap', gap:'0.5rem' }}>
            {meta.verified !== undefined && (
              <span style={{ display:'flex', alignItems:'center', gap:'0.3rem',
                fontSize:'0.72rem', fontWeight:600, padding:'3px 8px', borderRadius:'var(--radius-full)',
                background: meta.verified ? 'var(--success-light)' : 'var(--amber-light)',
                color: meta.verified ? 'var(--success)' : 'var(--amber)',
                border: `1px solid ${meta.verified ? 'rgba(34,197,94,0.2)' : 'var(--border-amber)'}` }}>
                <ShieldCheck size={11} />
                {meta.verified ? 'Verified' : 'Unverified'}
              </span>
            )}
            {meta.confidence && (
              <span style={{ fontSize:'0.72rem', fontWeight:600, padding:'3px 8px', borderRadius:'var(--radius-full)',
                background:'var(--primary-light)', color:'var(--primary)', border:'1px solid var(--border-violet)' }}>
                {(meta.confidence * 100).toFixed(0)}% confidence
              </span>
            )}
          </div>
        )}

        {meta?.citations?.length > 0 && (
          <div style={{ marginTop:'0.75rem', display:'flex', flexDirection:'column', gap:'0.5rem' }}>
            <div style={{ display:'flex', alignItems:'center', gap:'0.375rem', fontSize:'0.72rem',
              fontWeight:600, color:'var(--amber)', textTransform:'uppercase', letterSpacing:'0.05em' }}>
              <BookOpen size={12} />
              Sources
            </div>
            {meta.citations.map((c, i) => (
              <div key={i} style={{ padding:'0.625rem 0.875rem',
                background:'linear-gradient(145deg, rgba(245,185,66,0.06) 0%, var(--bg-surface) 100%)',
                border:'1px solid var(--border-amber)', borderRadius:'var(--radius-md)',
                borderLeft:'3px solid var(--amber)' }}>
                <div style={{ fontSize:'0.775rem', fontWeight:600, color:'var(--amber)', marginBottom:'0.25rem' }}>
                  {c.source} · {(c.relevance * 100).toFixed(0)}% relevance
                </div>
                <div style={{ fontSize:'0.8rem', color:'var(--text-muted)', lineHeight:1.5 }}>{c.text}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AskAI({ messages, queryInput, setQueryInput, isQuerying, handleSendQuery }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior:'smooth' });
  }, [messages, isQuerying]);

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', maxHeight:'calc(100vh - 60px)' }}>
      {/* Messages */}
      <div style={{ flex:1, overflowY:'auto', padding:'1.5rem 1.5rem 1rem' }}>
        <div style={{ maxWidth:'860px', margin:'0 auto' }}>
          <AnimatePresence>
            {messages.map((msg, i) => (
              <motion.div key={i} initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} transition={{ duration:0.25 }}>
                {msg.role === 'user'
                  ? <UserMessage text={msg.text} />
                  : <AIMessage text={msg.text} meta={msg.meta} />
                }
              </motion.div>
            ))}
          </AnimatePresence>

          {isQuerying && (
            <div style={{ display:'flex', gap:'0.75rem', alignItems:'flex-start', marginBottom:'1rem' }}>
              <div style={{ width:'32px', height:'32px', borderRadius:'50%', background:'var(--gradient-primary)',
                display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0,
                boxShadow:'0 0 12px rgba(124,92,255,0.35)' }}>
                <Zap size={15} color="#fff" />
              </div>
              <div style={{ padding:'0.875rem 1.125rem',
                background:'linear-gradient(145deg, rgba(124,92,255,0.07) 0%, var(--bg-card) 60%)',
                border:'1px solid rgba(124,92,255,0.15)', borderRadius:'4px var(--radius-lg) var(--radius-lg) var(--radius-lg)',
                display:'flex', alignItems:'center', gap:'0.5rem', color:'var(--primary)' }}>
                <motion.div animate={{ rotate:360 }} transition={{ repeat:Infinity, duration:1, ease:'linear' }}>
                  <Loader size={14} />
                </motion.div>
                <span style={{ fontSize:'0.875rem', color:'var(--text-muted)' }}>Retrieving and verifying...</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input Bar */}
      <div style={{ borderTop:'1px solid var(--border-subtle)',
        background:'rgba(7,8,18,0.85)', backdropFilter:'blur(16px)',
        padding:'1rem 1.5rem' }}>
        <form onSubmit={handleSendQuery} style={{ maxWidth:'860px', margin:'0 auto' }}>
          <div style={{ display:'flex', gap:'0.75rem', alignItems:'flex-end',
            background:'var(--bg-card)', border:'1px solid var(--border-strong)',
            borderRadius:'var(--radius-lg)', padding:'0.625rem 0.75rem',
            boxShadow:'0 0 0 1px transparent',
            transition:'border-color 0.2s, box-shadow 0.2s' }}
            onFocusCapture={e => e.currentTarget.style.borderColor = 'rgba(124,92,255,0.4)'}
            onBlurCapture={e => e.currentTarget.style.borderColor = 'var(--border-strong)'}
          >
            <textarea
              rows={1}
              placeholder="Ask anything about your documents…"
              value={queryInput}
              onChange={e => { setQueryInput(e.target.value); e.target.style.height='auto'; e.target.style.height=Math.min(e.target.scrollHeight,140)+'px'; }}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendQuery(e); } }}
              style={{ flex:1, background:'transparent', border:'none', outline:'none', resize:'none',
                color:'var(--text-primary)', fontSize:'0.9rem', lineHeight:1.6, fontFamily:'inherit',
                maxHeight:'140px', overflowY:'auto' }}
            />
            <button type="submit" disabled={isQuerying || !queryInput.trim()}
              style={{ width:'36px', height:'36px', borderRadius:'var(--radius-md)', flexShrink:0,
                background: queryInput.trim() ? 'var(--gradient-btn)' : 'var(--bg-elevated)',
                border:'none', display:'flex', alignItems:'center', justifyContent:'center',
                cursor: queryInput.trim() ? 'pointer' : 'not-allowed',
                boxShadow: queryInput.trim() ? '0 0 14px rgba(124,92,255,0.35)' : 'none',
                transition:'all 0.2s' }}>
              <Send size={15} color={queryInput.trim() ? '#fff' : 'var(--text-muted)'} />
            </button>
          </div>
          <p style={{ fontSize:'0.7rem', color:'var(--text-muted)', textAlign:'center', marginTop:'0.5rem' }}>
            Answers are grounded in your documents · Hybrid BM25 + Dense Retrieval · NLI Verified
          </p>
        </form>
      </div>
    </div>
  );
}
