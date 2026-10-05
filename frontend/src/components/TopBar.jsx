import React from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function TopBar({ backendHealth, ragHealth }) {
  const location = useLocation();
  const { user } = useAuth();

  const titles = {
    '/': 'Overview',
    '/ask-ai': 'Ask AI',
    '/documents': 'Documents',
    '/knowledge': 'Knowledge Base',
    '/retrieval': 'Retrieval Pipeline',
    '/verification': 'Verification',
    '/system': 'System',
    '/admin': 'Admin Dashboard',
    '/admin/users': 'User Management',
  };

  const title = titles[location.pathname] || 'DocAnalyser';

  const Dot = ({ status }) => {
    const color = status === 'healthy' ? 'var(--success)' : status === 'offline' ? 'var(--error)' : 'var(--warning)';
    return (
      <div style={{ display:'flex', alignItems:'center', gap:'0.5rem',
        padding:'0.3rem 0.75rem', borderRadius:'var(--radius-full)',
        background:'var(--bg-card)', border:'1px solid var(--border-subtle)', fontSize:'0.75rem', fontWeight:500, color:'var(--text-secondary)' }}>
        <div style={{ width:7, height:7, borderRadius:'50%', background:color, boxShadow:`0 0 6px ${color}` }} />
        <span>API</span>
      </div>
    );
  };

  return (
    <header className="topbar">
      <div>
        <h1 style={{ fontSize:'1.125rem', fontWeight:600, color:'var(--text-primary)', letterSpacing:'-0.01em' }}>{title}</h1>
      </div>

      <div style={{ display:'flex', gap:'0.625rem', alignItems:'center' }}>
        {[
          { label:'API',   status: backendHealth },
          { label:'RAG',   status: ragHealth     },
          { label:'Qdrant',status: 'healthy'     },
        ].map(({ label, status }) => {
          const color = status === 'healthy' ? 'var(--success)' : status === 'offline' ? 'var(--error)' : 'var(--warning)';
          return (
            <div key={label} style={{ display:'flex', alignItems:'center', gap:'0.4rem',
              padding:'0.3rem 0.7rem', borderRadius:'var(--radius-full)',
              background:'var(--bg-card)', border:'1px solid var(--border-subtle)',
              fontSize:'0.73rem', fontWeight:500, color:'var(--text-muted)' }}>
              <div style={{ width:6, height:6, borderRadius:'50%', background:color, boxShadow:`0 0 5px ${color}` }} />
              {label}
            </div>
          );
        })}
        {user?.role === 'ADMIN' && (
          <div style={{ padding:'0.25rem 0.625rem', borderRadius:'var(--radius-md)',
            background:'var(--primary-light)', border:'1px solid var(--border-violet)',
            fontSize:'0.68rem', fontWeight:700, color:'var(--primary)', letterSpacing:'0.06em' }}>
            ADMIN
          </div>
        )}
      </div>
    </header>
  );
}
