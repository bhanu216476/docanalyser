import React, { useEffect, useState } from 'react';
import { Activity, Users, Files, MessageSquare, Server, CheckCircle, XCircle, Loader } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080';
const RAG_BASE = import.meta.env.VITE_RAG_URL || 'http://localhost:8000';

function HealthDot({ status }) {
  const color = status === 'healthy' ? 'var(--success)' : status === 'offline' ? 'var(--error)' : 'var(--warning)';
  const Icon = status === 'healthy' ? CheckCircle : status === 'offline' ? XCircle : Loader;
  return (
    <span style={{ display:'flex', alignItems:'center', gap:'0.35rem', fontSize:'0.78rem', fontWeight:600, color }}>
      <Icon size={13} />
      {status === 'checking' ? 'Checking…' : status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

export default function AdminDashboard() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [springH, setSpringH] = useState('checking');
  const [ragH,    setRagH]    = useState('checking');

  useEffect(() => {
    const token = localStorage.getItem('token');
    fetch(`${API_BASE}/api/health`).then(r => setSpringH(r.ok ? 'healthy' : 'offline')).catch(() => setSpringH('offline'));
    fetch(`${RAG_BASE}/health`).then(r => setRagH(r.ok ? 'healthy' : 'offline')).catch(() => setRagH('offline'));
    fetch(`${API_BASE}/api/admin/users`, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : [])
      .then(d => setUsers(Array.isArray(d) ? d : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const stats = [
    { label:'Total Users',    value: loading ? '—' : users.length, colorClass:'stat-card-violet', iconClass:'icon-box-violet', icon:Users },
    { label:'Active Users',   value: loading ? '—' : users.filter(u => u.enabled !== false).length, colorClass:'stat-card-cyan', iconClass:'icon-box-cyan', icon:Activity },
    { label:'Documents',      value:'—', colorClass:'stat-card-amber', iconClass:'icon-box-amber', icon:Files },
    { label:'AI Queries',     value:'—', colorClass:'stat-card-violet', iconClass:'icon-box-violet', icon:MessageSquare },
  ];

  const services = [
    { name:'Spring Boot API', status: springH },
    { name:'Python RAG Service', status: ragH },
    { name:'Qdrant Vector DB', status:'healthy' },
    { name:'Redis Cache', status:'healthy' },
  ];

  return (
    <div style={{ maxWidth:'1200px', width:'100%' }}>
      <div style={{ marginBottom:'2rem' }}>
        <div style={{ display:'flex', alignItems:'center', gap:'0.75rem', marginBottom:'0.375rem' }}>
          <h1 style={{ fontSize:'1.625rem', fontWeight:700, color:'var(--text-primary)' }}>Admin Dashboard</h1>
          <span className="badge badge-violet">ADMIN</span>
        </div>
        <p style={{ color:'var(--text-muted)', fontSize:'0.9rem' }}>Platform-wide overview and management controls.</p>
      </div>

      {/* Stats */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(220px, 1fr))', gap:'1rem', marginBottom:'1.75rem' }}>
        {stats.map(s => {
          const Icon = s.icon;
          return (
            <div key={s.label} className={`stat-card ${s.colorClass}`}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:'0.875rem', position:'relative', zIndex:1 }}>
                <span style={{ fontSize:'0.72rem', fontWeight:600, textTransform:'uppercase', letterSpacing:'0.07em', color:'var(--text-muted)' }}>{s.label}</span>
                <div className={`icon-box icon-box-sm ${s.iconClass}`}><Icon size={14} /></div>
              </div>
              <div style={{ fontSize:'2.25rem', fontWeight:800, color:'var(--text-primary)', letterSpacing:'-0.03em', position:'relative', zIndex:1 }}>{s.value}</div>
            </div>
          );
        })}
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1.5rem' }}>
        {/* Recent Users */}
        <div style={{ background:'var(--bg-card)', border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-lg)', overflow:'hidden' }}>
          <div style={{ padding:'1.125rem 1.5rem', borderBottom:'1px solid var(--border-subtle)', display:'flex', alignItems:'center', gap:'0.625rem' }}>
            <div className="icon-box icon-box-sm icon-box-violet"><Users size={15} /></div>
            <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>Recent Users</h3>
          </div>
          <div style={{ padding:'0.75rem' }}>
            {loading ? (
              <div style={{ padding:'2rem', textAlign:'center', color:'var(--text-muted)', fontSize:'0.875rem' }}>Loading users…</div>
            ) : users.length === 0 ? (
              <div style={{ padding:'2.5rem', textAlign:'center', color:'var(--text-muted)', fontSize:'0.875rem' }}>
                <p>No users found. The <code style={{ color:'var(--primary)' }}>/api/admin/users</code> endpoint may not be running.</p>
              </div>
            ) : users.slice(0, 6).map((u, i) => (
              <div key={u.id || i} style={{ display:'flex', alignItems:'center', gap:'0.75rem', padding:'0.625rem 0.75rem',
                borderRadius:'var(--radius-md)', marginBottom:'2px', transition:'background 0.15s' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-surface)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <div style={{ width:'34px', height:'34px', borderRadius:'50%', flexShrink:0,
                  background:'var(--gradient-primary)', display:'flex', alignItems:'center', justifyContent:'center',
                  color:'#fff', fontWeight:700, fontSize:'0.875rem' }}>
                  {u.name?.charAt(0)?.toUpperCase()}
                </div>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontWeight:500, fontSize:'0.875rem', color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{u.name}</div>
                  <div style={{ fontSize:'0.73rem', color:'var(--text-muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{u.email}</div>
                </div>
                <span className={u.role === 'ADMIN' ? 'badge badge-violet' : 'badge badge-cyan'}>{u.role}</span>
              </div>
            ))}
          </div>
        </div>

        {/* System Health */}
        <div style={{ background:'var(--bg-card)', border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-lg)', overflow:'hidden' }}>
          <div style={{ padding:'1.125rem 1.5rem', borderBottom:'1px solid var(--border-subtle)', display:'flex', alignItems:'center', gap:'0.625rem' }}>
            <div className="icon-box icon-box-sm icon-box-cyan"><Server size={15} /></div>
            <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>System Health</h3>
          </div>
          <div style={{ padding:'1rem', display:'flex', flexDirection:'column', gap:'0.625rem' }}>
            {services.map(svc => (
              <div key={svc.name} style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
                padding:'0.75rem 1rem', borderRadius:'var(--radius-md)', background:'var(--bg-surface)',
                border:'1px solid var(--border-subtle)' }}>
                <span style={{ fontSize:'0.875rem', fontWeight:500, color:'var(--text-secondary)' }}>{svc.name}</span>
                <HealthDot status={svc.status} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
