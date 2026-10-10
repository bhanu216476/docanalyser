import React from 'react';
import { Server, Cpu, Database, Layers, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react';

export default function System({ backendHealth = 'checking', ragHealth = 'checking' }) {
  const isSpringHealthy = backendHealth === 'healthy';
  const isRagHealthy = ragHealth === 'healthy';

  const services = [
    {
      name: 'Spring Boot API Gateway',
      type: 'Java 21 · Port 8080',
      status: backendHealth,
      icon: Server,
      details: [
        { label: 'Security', value: 'JWT Authentication' },
        { label: 'Database', value: 'PostgreSQL 15' },
        { label: 'Cache', value: 'Redis In-Memory' }
      ]
    },
    {
      name: 'Python RAG Service',
      type: 'FastAPI · Port 8000',
      status: ragHealth,
      icon: Cpu,
      details: [
        { label: 'Vector Store', value: 'Qdrant (Cosine HNSW)' },
        { label: 'Retriever', value: 'Dense + BM25 (RRF)' },
        { label: 'Verification', value: 'NLI Entailment' }
      ]
    },
    {
      name: 'Qdrant Vector DB',
      type: 'gRPC / REST · Port 6333',
      status: 'healthy',
      icon: Database,
      details: [
        { label: 'Index Type', value: 'HNSW' },
        { label: 'Dimension', value: '1536' },
        { label: 'Distance', value: 'Cosine' }
      ]
    },
    {
      name: 'Redis Cache & Session',
      type: 'In-Memory · Port 6379',
      status: 'healthy',
      icon: Layers,
      details: [
        { label: 'Job State', value: 'Document State Machine' },
        { label: 'TTL', value: '3600 seconds' },
        { label: 'Policy', value: 'allkeys-lru' }
      ]
    }
  ];

  return (
    <div style={{ maxWidth: '1200px', width: '100%', margin: '0 auto', padding: '24px' }}>
      {/* Page Title */}
      <div style={{ marginBottom: '24px' }}>
        <h1 className="page-title">System</h1>
        <p style={{ color: 'var(--t2)', fontSize: '13.5px', marginTop: '4px' }}>
          System architecture topology, service status, and container health.
        </p>
      </div>

      {/* Topology Architecture Diagram */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h2 className="font-fraunces" style={{ fontSize: '18px', fontWeight: 600, color: 'var(--tx)', marginBottom: '16px' }}>
          System Architecture Topology
        </h2>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', padding: '16px', backgroundColor: 'var(--s2)', borderRadius: 'var(--r-md)' }}>
          <div style={{ textAlign: 'center', padding: '12px 20px', backgroundColor: 'var(--s1)', borderRadius: 'var(--r-md)', border: '1px solid var(--bd)' }}>
            <div style={{ fontSize: '11px', color: 'var(--mu)', fontFamily: 'JetBrains Mono' }}>CLIENT</div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--tx)' }}>Frontend</div>
          </div>

          <ArrowRight size={16} style={{ color: 'var(--mu)' }} />

          <div style={{ textAlign: 'center', padding: '12px 20px', backgroundColor: 'var(--s1)', borderRadius: 'var(--r-md)', border: `1px solid ${isSpringHealthy ? 'var(--ok)' : 'var(--err)'}` }}>
            <div style={{ fontSize: '11px', color: 'var(--mu)', fontFamily: 'JetBrains Mono' }}>ORCHESTRATOR</div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--tx)' }}>Spring Boot API</div>
          </div>

          <ArrowRight size={16} style={{ color: 'var(--mu)' }} />

          <div style={{ textAlign: 'center', padding: '12px 20px', backgroundColor: 'var(--s1)', borderRadius: 'var(--r-md)', border: `1px solid ${isRagHealthy ? 'var(--ok)' : 'var(--err)'}` }}>
            <div style={{ fontSize: '11px', color: 'var(--mu)', fontFamily: 'JetBrains Mono' }}>RAG ENGINE</div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--tx)' }}>Python RAG Engine</div>
          </div>

          <ArrowRight size={16} style={{ color: 'var(--mu)' }} />

          <div style={{ display: 'flex', gap: '8px' }}>
            <div style={{ padding: '8px 12px', backgroundColor: 'var(--s1)', borderRadius: 'var(--r-sm)', border: '1px solid var(--bd)', fontSize: '12px', fontWeight: 600, color: 'var(--ac)' }}>
              Qdrant
            </div>
            <div style={{ padding: '8px 12px', backgroundColor: 'var(--s1)', borderRadius: 'var(--r-sm)', border: '1px solid var(--bd)', fontSize: '12px', fontWeight: 600, color: 'var(--ac)' }}>
              Postgres
            </div>
            <div style={{ padding: '8px 12px', backgroundColor: 'var(--s1)', borderRadius: 'var(--r-sm)', border: '1px solid var(--bd)', fontSize: '12px', fontWeight: 600, color: 'var(--ac)' }}>
              Redis
            </div>
          </div>
        </div>
      </div>

      {/* Real Service Health Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
        {services.map((svc) => {
          const Icon = svc.icon;
          const isHealthy = svc.status === 'healthy';
          const isOffline = svc.status === 'offline';

          return (
            <div key={svc.name} className="card">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ padding: '8px', borderRadius: 'var(--r-md)', backgroundColor: 'var(--s2)', color: 'var(--ac)' }}>
                    <Icon size={18} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--tx)' }}>{svc.name}</h3>
                    <div style={{ fontSize: '11px', color: 'var(--mu)', fontFamily: 'JetBrains Mono' }}>{svc.type}</div>
                  </div>
                </div>
              </div>

              {/* Status Badge */}
              <div style={{ marginBottom: '16px' }}>
                <div
                  className="health-pill"
                  style={{
                    backgroundColor: isHealthy ? 'rgba(15,123,87,0.1)' : isOffline ? 'rgba(229,72,77,0.1)' : 'rgba(245,158,11,0.1)',
                    color: isHealthy ? 'var(--ok)' : isOffline ? 'var(--err)' : '#F59E0B',
                    borderColor: isHealthy ? 'rgba(15,123,87,0.2)' : isOffline ? 'rgba(229,72,77,0.2)' : 'rgba(245,158,11,0.2)'
                  }}
                >
                  <span className={`health-dot ${isHealthy ? 'healthy' : isOffline ? 'offline' : 'degraded'}`} />
                  <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{svc.status}</span>
                </div>
              </div>

              {/* Details list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', borderTop: '1px solid var(--bd)', paddingTop: '12px' }}>
                {svc.details.map((d) => (
                  <div key={d.label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                    <span style={{ color: 'var(--t2)' }}>{d.label}</span>
                    <span style={{ fontWeight: 500, color: 'var(--tx)' }}>{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
