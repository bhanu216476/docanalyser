import React from 'react';
import { Server, Database, Activity, Layers, CheckCircle, XCircle, Loader } from 'lucide-react';

function ServiceCard({ name, type, icon: Icon, iconClass, status, details }) {
  const statusColor = status === 'healthy' ? 'var(--success)' : status === 'offline' ? 'var(--error)' : 'var(--warning)';
  const StatusIcon = status === 'healthy' ? CheckCircle : status === 'offline' ? XCircle : Loader;

  return (
    <div style={{ background:'var(--bg-card)', border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-lg)',
      padding:'1.25rem', transition:'border-color 0.2s, transform 0.2s' }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border-cyan)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-subtle)'; e.currentTarget.style.transform = 'translateY(0)'; }}
    >
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:'1rem' }}>
        <div style={{ display:'flex', alignItems:'center', gap:'0.75rem' }}>
          <div className={`icon-box icon-box-md ${iconClass}`}><Icon size={20} /></div>
          <div>
            <div style={{ fontWeight:600, fontSize:'0.9rem', color:'var(--text-primary)' }}>{name}</div>
            <div style={{ fontSize:'0.72rem', color:'var(--text-muted)', marginTop:'1px' }}>{type}</div>
          </div>
        </div>
        <span style={{ display:'flex', alignItems:'center', gap:'0.3rem', fontSize:'0.775rem',
          fontWeight:600, color:statusColor }}>
          <StatusIcon size={13} />
          {status.charAt(0).toUpperCase() + status.slice(1)}
        </span>
      </div>
      <div style={{ display:'flex', flexDirection:'column', gap:'0.375rem' }}>
        {details.map(d => (
          <div key={d.label} style={{ display:'flex', justifyContent:'space-between', fontSize:'0.78rem',
            padding:'0.3rem 0', borderBottom:'1px solid rgba(37,43,66,0.4)' }}>
            <span style={{ color:'var(--text-muted)' }}>{d.label}</span>
            <span style={{ color: d.color || 'var(--text-secondary)', fontWeight:500, fontFamily:'monospace' }}>{d.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function System({ backendHealth, ragHealth }) {
  const services = [
    {
      name:'Spring Boot API', type:'Java 21 · Port 8080', icon:Server, iconClass:'icon-box-cyan', status:backendHealth,
      details:[
        { label:'Framework', value:'Spring Boot 3.3.4' },
        { label:'Security', value:'Spring Security + JWT', color:'var(--secondary)' },
        { label:'ORM', value:'Spring Data JPA' },
        { label:'DB Migrations', value:'Flyway V4', color:'var(--primary)' },
      ]
    },
    {
      name:'Python RAG Service', type:'FastAPI · Port 8000', icon:Activity, iconClass:'icon-box-violet', status:ragHealth,
      details:[
        { label:'Framework', value:'FastAPI' },
        { label:'Retrieval', value:'BM25 + Dense', color:'var(--primary)' },
        { label:'Fusion', value:'RRF (k=60)', color:'var(--primary)' },
        { label:'Reranking', value:'Cross-Encoder', color:'#A855F7' },
      ]
    },
    {
      name:'Qdrant Vector Store', type:'REST API · Port 6333', icon:Database, iconClass:'icon-box-cyan', status:'healthy',
      details:[
        { label:'Distance', value:'Cosine' },
        { label:'Index', value:'HNSW', color:'var(--secondary)' },
        { label:'Embedding Dim', value:'1536', color:'var(--secondary)' },
        { label:'m parameter', value:'16' },
      ]
    },
    {
      name:'Redis Cache', type:'In-Memory · Port 6379', icon:Layers, iconClass:'icon-box-amber', status:'healthy',
      details:[
        { label:'Mode', value:'Session + Rate Limit' },
        { label:'Eviction', value:'allkeys-lru', color:'var(--amber)' },
        { label:'TTL', value:'3600s', color:'var(--amber)' },
        { label:'Persistence', value:'RDB snapshots' },
      ]
    },
  ];

  return (
    <div style={{ maxWidth:'1100px', width:'100%' }}>
      <div style={{ marginBottom:'2rem' }}>
        <h1 style={{ fontSize:'1.625rem', fontWeight:700, color:'var(--text-primary)', marginBottom:'0.375rem' }}>System Infrastructure</h1>
        <p style={{ color:'var(--text-muted)', fontSize:'0.9rem' }}>Container topology and service health for the DocAnalyser platform.</p>
      </div>

      {/* Summary */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:'1rem', marginBottom:'1.75rem' }}>
        {[
          { label:'Services', value:'4', colorClass:'stat-card-cyan', iconClass:'icon-box-cyan', icon:Server },
          { label:'Healthy', value:([backendHealth, ragHealth, 'healthy', 'healthy'].filter(s => s === 'healthy').length).toString(), colorClass:'stat-card-success', iconClass:'icon-box-success', icon:CheckCircle },
          { label:'Infrastructure', value:'Docker', colorClass:'stat-card-violet', iconClass:'icon-box-violet', icon:Layers },
          { label:'Observability', value:'OTEL', colorClass:'stat-card-amber', iconClass:'icon-box-amber', icon:Activity },
        ].map(s => {
          const Icon = s.icon;
          return (
            <div key={s.label} className={`stat-card ${s.colorClass}`}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'0.75rem', position:'relative', zIndex:1 }}>
                <span style={{ fontSize:'0.7rem', fontWeight:600, textTransform:'uppercase', letterSpacing:'0.07em', color:'var(--text-muted)' }}>{s.label}</span>
                <div className={`icon-box icon-box-sm ${s.iconClass}`}><Icon size={14} /></div>
              </div>
              <div style={{ fontSize:'1.875rem', fontWeight:800, color:'var(--text-primary)', position:'relative', zIndex:1 }}>{s.value}</div>
            </div>
          );
        })}
      </div>

      {/* Service Cards */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(2, 1fr)', gap:'1.25rem' }}>
        {services.map(svc => <ServiceCard key={svc.name} {...svc} />)}
      </div>

      {/* Architecture note */}
      <div style={{ marginTop:'1.5rem', padding:'1.25rem 1.5rem',
        background:'linear-gradient(145deg, rgba(34,211,238,0.05) 0%, var(--bg-card) 80%)',
        border:'1px solid var(--border-cyan)', borderRadius:'var(--radius-lg)',
        display:'flex', alignItems:'center', gap:'1rem' }}>
        <div className="icon-box icon-box-sm icon-box-cyan"><Server size={15} /></div>
        <div>
          <p style={{ fontSize:'0.8375rem', color:'var(--text-secondary)', lineHeight:1.5 }}>
            All services run as Docker containers orchestrated via <span style={{ color:'var(--secondary)', fontWeight:600 }}>docker-compose</span>. 
            Observability is powered by <span style={{ color:'var(--primary)', fontWeight:600 }}>OpenTelemetry + Prometheus + Loki</span>. 
            Internal Python↔Spring communication uses a shared <span style={{ color:'var(--amber)', fontWeight:600 }}>X-Internal-Token</span>.
          </p>
        </div>
      </div>
    </div>
  );
}
