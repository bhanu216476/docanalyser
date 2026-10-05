import React from 'react';
import { Database, Layers, Hash, Box, Activity } from 'lucide-react';

function InfoRow({ label, value, color }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'0.625rem 0', borderBottom:'1px solid rgba(37,43,66,0.5)' }}>
      <span style={{ fontSize:'0.8125rem', color:'var(--text-muted)' }}>{label}</span>
      <span style={{ fontSize:'0.8125rem', fontWeight:600, color: color || 'var(--text-primary)', fontFamily:'monospace' }}>{value}</span>
    </div>
  );
}

function StoreCard({ title, icon: Icon, iconClass, colorClass, children }) {
  return (
    <div className={`card ${colorClass}`}>
      <div style={{ display:'flex', alignItems:'center', gap:'0.75rem', marginBottom:'1.25rem', paddingBottom:'1rem', borderBottom:'1px solid var(--border-subtle)' }}>
        <div className={`icon-box icon-box-md ${iconClass}`}><Icon size={20} /></div>
        <div>
          <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>{title}</h3>
        </div>
      </div>
      {children}
    </div>
  );
}

export default function KnowledgeBase({ documents }) {
  const totalChunks = documents.reduce((a, d) => a + (d.chunks || 0), 0);

  return (
    <div style={{ maxWidth:'1100px', width:'100%' }}>
      <div style={{ marginBottom:'2rem' }}>
        <h1 style={{ fontSize:'1.625rem', fontWeight:700, color:'var(--text-primary)', marginBottom:'0.375rem' }}>Knowledge Base</h1>
        <p style={{ color:'var(--text-muted)', fontSize:'0.9rem' }}>Vector store infrastructure and knowledge index status.</p>
      </div>

      {/* Stats */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:'1rem', marginBottom:'1.75rem' }}>
        {[
          { label:'Documents', value:documents.length, colorClass:'stat-card-cyan', iconClass:'icon-box-cyan', icon:Database },
          { label:'Total Chunks', value:totalChunks, colorClass:'stat-card-violet', iconClass:'icon-box-violet', icon:Layers },
          { label:'Embedding Dim', value:'1536', colorClass:'stat-card-violet', iconClass:'icon-box-violet', icon:Hash },
          { label:'Index Type', value:'HNSW', colorClass:'stat-card-amber', iconClass:'icon-box-amber', icon:Activity },
        ].map(s => {
          const Icon = s.icon;
          return (
            <div key={s.label} className={`stat-card ${s.colorClass}`}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'0.75rem', position:'relative', zIndex:1 }}>
                <span style={{ fontSize:'0.7rem', fontWeight:600, textTransform:'uppercase', letterSpacing:'0.07em', color:'var(--text-muted)' }}>{s.label}</span>
                <div className={`icon-box icon-box-sm ${s.iconClass}`}><Icon size={14} /></div>
              </div>
              <div style={{ fontSize:'1.875rem', fontWeight:800, color:'var(--text-primary)', letterSpacing:'-0.02em', position:'relative', zIndex:1 }}>{s.value}</div>
            </div>
          );
        })}
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:'1.25rem', marginBottom:'1.25rem' }}>
        {/* Qdrant */}
        <StoreCard title="Qdrant Vector Store" icon={Database} iconClass="icon-box-cyan" colorClass="card-cyan">
          <InfoRow label="Status" value="Connected" color="var(--success)" />
          <InfoRow label="Collection" value="documents" />
          <InfoRow label="Distance" value="Cosine" color="var(--secondary)" />
          <InfoRow label="Vectors" value={String(totalChunks)} color="var(--secondary)" />
          <InfoRow label="HNSW m" value="16" />
        </StoreCard>

        {/* PostgreSQL */}
        <StoreCard title="PostgreSQL Metadata" icon={Box} iconClass="icon-box-violet" colorClass="card-violet">
          <InfoRow label="Status" value="Connected" color="var(--success)" />
          <InfoRow label="Documents" value={String(documents.length)} color="var(--primary)" />
          <InfoRow label="Engine" value="PostgreSQL 15" />
          <InfoRow label="ORM" value="Spring Data JPA" />
          <InfoRow label="Schema" value="V4 (Flyway)" color="var(--primary)" />
        </StoreCard>

        {/* Redis */}
        <StoreCard title="Redis Cache" icon={Activity} iconClass="icon-box-amber" colorClass="card-amber">
          <InfoRow label="Status" value="Connected" color="var(--success)" />
          <InfoRow label="Mode" value="Session Cache" />
          <InfoRow label="TTL" value="3600s" color="var(--amber)" />
          <InfoRow label="Eviction" value="allkeys-lru" />
          <InfoRow label="Policy" value="Rate Limit" color="var(--amber)" />
        </StoreCard>
      </div>

      {/* Document Breakdown */}
      <div style={{ background:'var(--bg-card)', border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-lg)', overflow:'hidden' }}>
        <div style={{ padding:'1.125rem 1.5rem', borderBottom:'1px solid var(--border-subtle)', display:'flex', alignItems:'center', gap:'0.625rem' }}>
          <div className="icon-box icon-box-sm icon-box-cyan"><Layers size={15} /></div>
          <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>Document Index</h3>
        </div>
        <table className="data-table">
          <thead><tr><th>Document</th><th>Category</th><th>Chunks</th><th>Embedding</th><th>Status</th></tr></thead>
          <tbody>
            {documents.map((doc, i) => (
              <tr key={doc.id || i}>
                <td style={{ fontWeight:500, color:'var(--text-primary)' }}>{doc.title}</td>
                <td><span className="badge badge-violet">{doc.category}</span></td>
                <td><span style={{ color:'var(--secondary)', fontFamily:'monospace', fontWeight:600 }}>{doc.chunks}</span></td>
                <td><span style={{ color:'var(--text-muted)', fontSize:'0.8rem' }}>text-embedding-3-small</span></td>
                <td><span className="badge badge-success">Indexed</span></td>
              </tr>
            ))}
            {documents.length === 0 && (
              <tr><td colSpan={5} style={{ padding:'2.5rem', textAlign:'center', color:'var(--text-muted)' }}>No documents indexed.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
