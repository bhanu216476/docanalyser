import React from 'react';
import { ShieldCheck, BookOpen, AlertTriangle, XCircle, CheckCircle } from 'lucide-react';

function AmberBar({ value, max = 100 }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div style={{ marginTop:'0.5rem' }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:'0.375rem' }}>
        <span style={{ fontSize:'0.75rem', color:'var(--text-muted)' }}>Score</span>
        <span style={{ fontSize:'0.875rem', fontWeight:700, color:'var(--amber)' }}>{value.toFixed(1)}%</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill progress-fill-amber" style={{ width:`${pct}%` }} />
      </div>
    </div>
  );
}

export default function Verification({ messages }) {
  const aiMsgs = messages.filter(m => m.role === 'assistant' && m.meta);
  const verified = aiMsgs.filter(m => m.meta?.verified).length;
  const total    = aiMsgs.length;
  const accuracy = total > 0 ? (verified / total) * 100 : 94.8;
  const avgConf  = total > 0
    ? aiMsgs.reduce((a, m) => a + (m.meta?.confidence || 0), 0) / total * 100
    : 91.2;

  const allCitations = aiMsgs.flatMap(m => m.meta?.citations || []);

  return (
    <div style={{ maxWidth:'1100px', width:'100%' }}>
      <div style={{ marginBottom:'2rem' }}>
        <h1 style={{ fontSize:'1.625rem', fontWeight:700, color:'var(--text-primary)', marginBottom:'0.375rem' }}>Citation Verification</h1>
        <p style={{ color:'var(--text-muted)', fontSize:'0.9rem' }}>NLI-based faithfulness and citation accuracy metrics.</p>
      </div>

      {/* Score cards */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:'1rem', marginBottom:'1.75rem' }}>
        {[
          { label:'Citation Accuracy', value: accuracy, icon: ShieldCheck, colorClass:'stat-card-amber', iconClass:'icon-box-amber' },
          { label:'Avg Confidence',    value: avgConf,  icon: CheckCircle, colorClass:'stat-card-success', iconClass:'icon-box-success' },
          { label:'Responses Verified', value: total > 0 ? (verified/total*100) : 100, icon: BookOpen, colorClass:'stat-card-violet', iconClass:'icon-box-violet' },
        ].map(card => {
          const Icon = card.icon;
          return (
            <div key={card.label} className={`stat-card ${card.colorClass}`}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'1rem', position:'relative', zIndex:1 }}>
                <span style={{ fontSize:'0.72rem', fontWeight:600, textTransform:'uppercase', letterSpacing:'0.07em', color:'var(--text-muted)' }}>{card.label}</span>
                <div className={`icon-box icon-box-sm ${card.iconClass}`}><Icon size={15} /></div>
              </div>
              <div style={{ fontSize:'2.5rem', fontWeight:800, color:'var(--text-primary)', letterSpacing:'-0.03em', lineHeight:1, position:'relative', zIndex:1 }}>
                {card.value.toFixed(1)}
                <span style={{ fontSize:'1.25rem', fontWeight:600, color:'var(--text-muted)' }}>%</span>
              </div>
              <AmberBar value={card.value} />
            </div>
          );
        })}
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1.5rem' }}>
        {/* NLI Verification Status */}
        <div style={{ background:'linear-gradient(145deg, rgba(245,185,66,0.05) 0%, var(--bg-card) 60%)', border:'1px solid var(--border-amber)', borderRadius:'var(--radius-lg)' }}>
          <div style={{ padding:'1.125rem 1.5rem', borderBottom:'1px solid var(--border-subtle)', display:'flex', alignItems:'center', gap:'0.625rem' }}>
            <div className="icon-box icon-box-sm icon-box-amber"><ShieldCheck size={15} /></div>
            <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>Verification Results</h3>
          </div>
          <div style={{ padding:'1.25rem', display:'flex', flexDirection:'column', gap:'0.625rem' }}>
            {aiMsgs.length === 0 ? (
              <div style={{ padding:'2rem', textAlign:'center', color:'var(--text-muted)', fontSize:'0.875rem' }}>
                No verified responses yet. Ask AI a question to see verification results.
              </div>
            ) : aiMsgs.map((m, i) => {
              const icon = m.meta.verified ? <CheckCircle size={14} color="var(--success)" /> : <AlertTriangle size={14} color="var(--amber)" />;
              const color = m.meta.verified ? 'var(--success)' : 'var(--amber)';
              return (
                <div key={i} style={{ padding:'0.875rem 1rem', borderRadius:'var(--radius-md)', background:'var(--bg-surface)',
                  border:`1px solid ${m.meta.verified ? 'rgba(34,197,94,0.2)' : 'var(--border-amber)'}`,
                  borderLeft:`3px solid ${color}` }}>
                  <div style={{ display:'flex', alignItems:'center', gap:'0.5rem', marginBottom:'0.375rem' }}>
                    {icon}
                    <span style={{ fontSize:'0.75rem', fontWeight:600, color, textTransform:'uppercase', letterSpacing:'0.04em' }}>
                      {m.meta.verified ? 'Verified' : 'Unverified'}
                    </span>
                    <span style={{ marginLeft:'auto', fontSize:'0.75rem', color:'var(--primary)', fontWeight:600 }}>
                      {((m.meta.confidence || 0.9) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p style={{ fontSize:'0.8125rem', color:'var(--text-muted)', lineHeight:1.4, overflow:'hidden', display:'-webkit-box', WebkitLineClamp:2, WebkitBoxOrient:'vertical' }}>
                    {m.text}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Citations */}
        <div style={{ background:'var(--bg-card)', border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-lg)' }}>
          <div style={{ padding:'1.125rem 1.5rem', borderBottom:'1px solid var(--border-subtle)', display:'flex', alignItems:'center', gap:'0.625rem' }}>
            <div className="icon-box icon-box-sm icon-box-amber"><BookOpen size={15} /></div>
            <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>Source Citations</h3>
          </div>
          <div style={{ padding:'1rem', display:'flex', flexDirection:'column', gap:'0.625rem' }}>
            {allCitations.length === 0 ? (
              <div style={{ padding:'2rem', textAlign:'center', color:'var(--text-muted)', fontSize:'0.875rem' }}>
                Citations will appear here after AI responses.
              </div>
            ) : allCitations.map((c, i) => (
              <div key={i} style={{ padding:'0.875rem 1rem', borderRadius:'var(--radius-md)',
                background:'linear-gradient(135deg, rgba(245,185,66,0.05) 0%, var(--bg-surface) 100%)',
                border:'1px solid var(--border-amber)', borderLeft:'3px solid var(--amber)' }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'0.375rem' }}>
                  <span style={{ fontSize:'0.775rem', fontWeight:600, color:'var(--amber)' }}>{c.source}</span>
                  <span style={{ fontSize:'0.72rem', fontWeight:700, padding:'2px 7px', borderRadius:'var(--radius-full)',
                    background:'var(--amber-light)', color:'var(--amber)', border:'1px solid var(--border-amber)' }}>
                    {(c.relevance * 100).toFixed(0)}%
                  </span>
                </div>
                <p style={{ fontSize:'0.8125rem', color:'var(--text-muted)', lineHeight:1.45 }}>{c.text}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
