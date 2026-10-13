import React from 'react';
import { LayoutDashboard, FileText, Database, MessageSquare, ShieldCheck, TrendingUp, CheckCircle, XCircle, Loader } from 'lucide-react';

function StatCard({ label, value, sub, colorClass, iconClass, icon: Icon }) {
  return (
    <div className={`stat-card ${colorClass}`}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'1rem', position:'relative', zIndex:1 }}>
        <span style={{ fontSize:'0.73rem', fontWeight:600, textTransform:'uppercase', letterSpacing:'0.07em', color:'var(--text-muted)' }}>{label}</span>
        <div className={`icon-box icon-box-sm ${iconClass}`}>
          <Icon size={15} />
        </div>
      </div>
      <div style={{ fontSize:'2.25rem', fontWeight:800, color:'var(--text-primary)', letterSpacing:'-0.03em', lineHeight:1, position:'relative', zIndex:1 }}>{value}</div>
      {sub && <div style={{ fontSize:'0.75rem', color:'var(--text-muted)', marginTop:'0.375rem', position:'relative', zIndex:1 }}>{sub}</div>}
    </div>
  );
}

function HealthRow({ label, status }) {
  const color = status === 'healthy' ? 'var(--success)' : status === 'offline' ? 'var(--error)' : 'var(--warning)';
  const Icon = status === 'healthy' ? CheckCircle : status === 'offline' ? XCircle : Loader;
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
      padding:'0.75rem 1rem', borderRadius:'var(--radius-md)', background:'var(--bg-surface)',
      border:'1px solid var(--border-subtle)' }}>
      <span style={{ fontSize:'0.875rem', fontWeight:500, color:'var(--text-secondary)' }}>{label}</span>
      <span style={{ display:'flex', alignItems:'center', gap:'0.375rem', fontSize:'0.8rem', color }}>
        <Icon size={14} />
        {status === 'checking' ? 'Checking…' : status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    </div>
  );
}

export default function Overview({ documents, messages, backendHealth, ragHealth }) {
  const docCount = documents.length;
  const chunks   = documents.reduce((a, d) => a + (d.chunks || 0), 0);
  const queries  = messages.filter(m => m.role === 'user').length;
  const verified = messages.filter(m => m.meta?.verified).length;

  return (
    <div style={{ maxWidth:'1200px', width:'100%' }}>
      {/* Header */}
      <div style={{ marginBottom:'2rem' }}>
        <h1 style={{ fontSize:'1.625rem', fontWeight:700, color:'var(--text-primary)', marginBottom:'0.375rem' }}>Platform Overview</h1>
        <p style={{ color:'var(--text-muted)', fontSize:'0.9rem' }}>Live intelligence metrics for your DocAnalyser workspace.</p>
      </div>

      {/* Stat Cards */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(220px, 1fr))', gap:'1rem', marginBottom:'1.75rem' }}>
        <StatCard label="Documents" value={docCount} sub="Indexed in knowledge base" colorClass="stat-card-violet" iconClass="icon-box-violet" icon={FileText} />
        <StatCard label="Knowledge Chunks" value={chunks} sub="Vector store embeddings" colorClass="stat-card-cyan" iconClass="icon-box-cyan" icon={Database} />
        <StatCard label="Queries" value={queries} sub="RAG queries executed" colorClass="stat-card-violet" iconClass="icon-box-violet" icon={MessageSquare} />
        <StatCard label="Verified Answers" value={verified} sub="NLI citation verified" colorClass="stat-card-amber" iconClass="icon-box-amber" icon={ShieldCheck} />
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1.5rem' }}>
        {/* Recent Documents */}
        <div style={{ background:'var(--bg-card)', border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-lg)', overflow:'hidden' }}>
          <div style={{ padding:'1.25rem 1.5rem', borderBottom:'1px solid var(--border-subtle)', display:'flex', alignItems:'center', gap:'0.625rem' }}>
            <div className="icon-box icon-box-sm icon-box-cyan"><FileText size={15} /></div>
            <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>Recent Documents</h3>
          </div>
          <div style={{ padding:'0.75rem' }}>
            {documents.slice(0, 5).map((doc, i) => (
              <div key={doc.id || i} style={{ display:'flex', alignItems:'center', gap:'0.875rem',
                padding:'0.75rem', borderRadius:'var(--radius-md)', marginBottom:'2px',
                transition:'background 0.15s' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-surface)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <div className="icon-box icon-box-sm icon-box-cyan"><FileText size={14} /></div>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontSize:'0.875rem', fontWeight:500, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{doc.title}</div>
                  <div style={{ fontSize:'0.73rem', color:'var(--text-muted)', marginTop:'1px' }}>{doc.chunks} chunks · {doc.uploadedAt}</div>
                </div>
                <span className="badge badge-success">{doc.status}</span>
              </div>
            ))}
            {documents.length === 0 && (
              <div style={{ padding:'2rem', textAlign:'center', color:'var(--text-muted)', fontSize:'0.875rem' }}>No documents yet.</div>
            )}
          </div>
        </div>

        {/* System Health & Recent Activity */}
        <div style={{ display:'flex', flexDirection:'column', gap:'1.25rem' }}>
          <div style={{ background:'var(--bg-card)', border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-lg)', overflow:'hidden' }}>
            <div style={{ padding:'1.25rem 1.5rem', borderBottom:'1px solid var(--border-subtle)', display:'flex', alignItems:'center', gap:'0.625rem' }}>
              <div className="icon-box icon-box-sm icon-box-violet"><TrendingUp size={15} /></div>
              <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>System Health</h3>
            </div>
            <div style={{ padding:'0.75rem', display:'flex', flexDirection:'column', gap:'0.5rem' }}>
              <HealthRow label="Spring Boot API" status={backendHealth} />
              <HealthRow label="Python RAG Service" status={ragHealth} />
              <HealthRow label="Qdrant Vector DB" status="healthy" />
              <HealthRow label="Redis Cache" status="healthy" />
            </div>
          </div>

          <div style={{ background:'linear-gradient(145deg, rgba(245,185,66,0.05) 0%, var(--bg-card) 70%)', border:'1px solid var(--border-amber)', borderRadius:'var(--radius-lg)', padding:'1.25rem 1.5rem' }}>
            <div style={{ display:'flex', alignItems:'center', gap:'0.625rem', marginBottom:'1rem' }}>
              <div className="icon-box icon-box-sm icon-box-amber"><ShieldCheck size={15} /></div>
              <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>RAG Pipeline</h3>
            </div>
            <div style={{ display:'flex', flexDirection:'column', gap:'0.5rem' }}>
              {[
                { label:'Hybrid Retrieval', value:'BM25 + Dense', color:'var(--secondary)' },
                { label:'Fusion Strategy', value:'RRF', color:'var(--primary)' },
                { label:'Reranking', value:'Cross-Encoder', color:'var(--amber)' },
                { label:'Verification', value:'NLI-based', color:'var(--success)' },
              ].map(row => (
                <div key={row.label} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', fontSize:'0.8125rem' }}>
                  <span style={{ color:'var(--text-muted)' }}>{row.label}</span>
                  <span style={{ color:row.color, fontWeight:600 }}>{row.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
