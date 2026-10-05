import React from 'react';
import { GitMerge, Search, Zap, Filter, ArrowDown, CheckCircle } from 'lucide-react';

const pipeline = [
  { icon: Search,      label: 'Query Input',       desc: 'User natural language query',    color: 'var(--primary)',   borderClass: 'pipeline-step-violet', dotClass: 'status-dot-violet' },
  { icon: Zap,         label: 'Dense Retrieval',    desc: 'OpenAI text-embedding-3-small',  color: 'var(--secondary)', borderClass: 'pipeline-step-cyan',   dotClass: 'status-dot-cyan'   },
  { icon: Search,      label: 'BM25 Retrieval',     desc: 'Sparse keyword scoring',         color: 'var(--secondary)', borderClass: 'pipeline-step-cyan',   dotClass: 'status-dot-cyan'   },
  { icon: GitMerge,    label: 'RRF Fusion',         desc: 'Reciprocal Rank Fusion merge',   color: 'var(--primary)',   borderClass: 'pipeline-step-violet', dotClass: 'status-dot-violet' },
  { icon: Filter,      label: 'Cross-Encoder',      desc: 'MS-MARCO reranking',             color: '#A855F7',          borderClass: 'pipeline-step-violet', dotClass: 'status-dot-violet' },
  { icon: Zap,         label: 'Context Window',     desc: 'Top-k chunks assembled',         color: 'var(--amber)',     borderClass: 'pipeline-step-amber',  dotClass: 'status-dot-amber'  },
  { icon: Zap,         label: 'LLM Generation',     desc: 'GPT-4 grounded generation',      color: 'var(--secondary)', borderClass: 'pipeline-step-cyan',   dotClass: 'status-dot-cyan'   },
  { icon: CheckCircle, label: 'Verified Answer',    desc: 'NLI citation verification',      color: 'var(--success)',   borderClass: 'pipeline-step-green',  dotClass: 'status-dot-green'  },
];

export default function Retrieval({ messages }) {
  const recentQueries = messages.filter(m => m.role === 'user').slice(-4).reverse();

  return (
    <div style={{ maxWidth:'1100px', width:'100%' }}>
      <div style={{ marginBottom:'2rem' }}>
        <h1 style={{ fontSize:'1.625rem', fontWeight:700, color:'var(--text-primary)', marginBottom:'0.375rem' }}>Retrieval Pipeline</h1>
        <p style={{ color:'var(--text-muted)', fontSize:'0.9rem' }}>Hybrid RAG architecture — Dense + BM25 → RRF → Reranking → NLI Verification.</p>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1.5rem' }}>
        {/* Pipeline Visualization */}
        <div style={{ background:'var(--bg-card)', border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-lg)', overflow:'hidden' }}>
          <div style={{ padding:'1.125rem 1.5rem', borderBottom:'1px solid var(--border-subtle)', display:'flex', alignItems:'center', gap:'0.625rem' }}>
            <div className="icon-box icon-box-sm icon-box-violet"><GitMerge size={15} /></div>
            <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>Pipeline Architecture</h3>
          </div>
          <div style={{ padding:'1.25rem', display:'flex', flexDirection:'column', gap:'0' }}>
            {pipeline.map((step, i) => {
              const Icon = step.icon;
              return (
                <React.Fragment key={step.label}>
                  <div className={`pipeline-step ${step.borderClass}`}>
                    <div style={{ width:'32px', height:'32px', borderRadius:'var(--radius-md)', flexShrink:0,
                      background: step.color === 'var(--primary)' ? 'var(--primary-light)'
                        : step.color === 'var(--secondary)' ? 'var(--secondary-light)'
                        : step.color === 'var(--amber)' ? 'var(--amber-light)'
                        : step.color === 'var(--success)' ? 'var(--success-light)'
                        : 'rgba(168,85,247,0.12)',
                      display:'flex', alignItems:'center', justifyContent:'center' }}>
                      <Icon size={16} color={step.color} />
                    </div>
                    <div style={{ flex:1 }}>
                      <div style={{ fontSize:'0.8375rem', fontWeight:600, color:'var(--text-primary)' }}>{step.label}</div>
                      <div style={{ fontSize:'0.73rem', color:'var(--text-muted)', marginTop:'1px' }}>{step.desc}</div>
                    </div>
                    <div className={`status-dot ${step.dotClass}`} />
                  </div>
                  {i < pipeline.length - 1 && (
                    <div style={{ display:'flex', alignItems:'center', padding:'0 1.1rem' }}>
                      <div style={{ width:'2px', height:'16px', background:'linear-gradient(180deg, var(--border-strong) 0%, transparent 100%)', margin:'0 auto', opacity:0.5 }} />
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Right column */}
        <div style={{ display:'flex', flexDirection:'column', gap:'1.25rem' }}>
          {/* Config */}
          <div style={{ background:'linear-gradient(145deg, rgba(34,211,238,0.05) 0%, var(--bg-card) 60%)', border:'1px solid var(--border-cyan)', borderRadius:'var(--radius-lg)' }}>
            <div style={{ padding:'1.125rem 1.5rem', borderBottom:'1px solid var(--border-subtle)', display:'flex', alignItems:'center', gap:'0.625rem' }}>
              <div className="icon-box icon-box-sm icon-box-cyan"><Filter size={15} /></div>
              <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>Retrieval Config</h3>
            </div>
            <div style={{ padding:'1.25rem', display:'flex', flexDirection:'column', gap:'0.75rem' }}>
              {[
                { label:'Top-K Dense', value:'10', color:'var(--secondary)' },
                { label:'Top-K BM25', value:'10', color:'var(--secondary)' },
                { label:'RRF k constant', value:'60', color:'var(--primary)' },
                { label:'Reranker Top-K', value:'5', color:'#A855F7' },
                { label:'Embedding Model', value:'text-embedding-3-small', color:'var(--text-secondary)' },
                { label:'Chunk Size', value:'512 tokens', color:'var(--amber)' },
              ].map(r => (
                <div key={r.label} style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
                  padding:'0.5rem 0.75rem', borderRadius:'var(--radius-sm)', background:'var(--bg-surface)' }}>
                  <span style={{ fontSize:'0.8125rem', color:'var(--text-muted)' }}>{r.label}</span>
                  <span style={{ fontSize:'0.8125rem', fontWeight:600, color:r.color, fontFamily:'monospace' }}>{r.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Queries */}
          <div style={{ background:'var(--bg-card)', border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-lg)' }}>
            <div style={{ padding:'1.125rem 1.5rem', borderBottom:'1px solid var(--border-subtle)', display:'flex', alignItems:'center', gap:'0.625rem' }}>
              <div className="icon-box icon-box-sm icon-box-violet"><Search size={15} /></div>
              <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>Recent Queries</h3>
            </div>
            <div style={{ padding:'0.75rem' }}>
              {recentQueries.length === 0 ? (
                <div style={{ padding:'2rem', textAlign:'center', color:'var(--text-muted)', fontSize:'0.875rem' }}>No queries yet. Ask a question in the Ask AI tab.</div>
              ) : recentQueries.map((m, i) => (
                <div key={i} style={{ padding:'0.75rem', borderRadius:'var(--radius-md)', marginBottom:'4px',
                  background:'var(--bg-surface)', border:'1px solid var(--border-subtle)' }}>
                  <div style={{ display:'flex', alignItems:'center', gap:'0.5rem', marginBottom:'0.25rem' }}>
                    <div className="status-dot status-dot-violet" />
                    <span style={{ fontSize:'0.7rem', color:'var(--primary)', fontWeight:600, textTransform:'uppercase', letterSpacing:'0.05em' }}>Query</span>
                  </div>
                  <p style={{ fontSize:'0.8375rem', color:'var(--text-secondary)', lineHeight:1.4, overflow:'hidden', display:'-webkit-box', WebkitLineClamp:2, WebkitBoxOrient:'vertical' }}>{m.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
