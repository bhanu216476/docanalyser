import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard, MessageSquare, Files, Database, GitMerge,
  ShieldCheck, Server, Activity, Users, LogOut
} from 'lucide-react';

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const path = location.pathname;

  const baseNav = [
    { id: '/',             label: 'Overview',       icon: LayoutDashboard },
    { id: '/ask-ai',       label: 'Ask AI',         icon: MessageSquare },
    { id: '/documents',    label: 'Documents',      icon: Files },
    { id: '/knowledge',    label: 'Knowledge Base', icon: Database },
    { id: '/retrieval',    label: 'Retrieval',      icon: GitMerge },
    { id: '/verification', label: 'Verification',   icon: ShieldCheck },
    { id: '/system',       label: 'System',         icon: Server },
  ];

  const adminNav = [
    { id: '/admin',        label: 'Admin Dashboard', icon: Activity },
    { id: '/admin/users',  label: 'User Management', icon: Users },
  ];

  const navItems = user?.role === 'ADMIN' ? [...baseNav, ...adminNav] : baseNav;

  const isActive = (id) => id === '/' ? path === '/' : path.startsWith(id);

  const handleLogout = () => { logout(); navigate('/login'); };

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div style={{ padding:'1.25rem 1rem 1rem', display:'flex', alignItems:'center', gap:'0.75rem', borderBottom:'1px solid var(--border-subtle)' }}>
        <div style={{ width:'34px', height:'34px', borderRadius:'9px', background:'var(--gradient-primary)',
          display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0,
          boxShadow:'0 0 16px rgba(124,92,255,0.35)' }}>
          <Database size={17} color="#fff" />
        </div>
        <div>
          <h2 style={{ fontSize:'0.9375rem', fontWeight:700, color:'var(--text-primary)', letterSpacing:'-0.02em', lineHeight:1 }}>DocAnalyser</h2>
          <p style={{ fontSize:'0.65rem', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.07em', marginTop:'2px' }}>Enterprise RAG</p>
        </div>
      </div>

      {/* Nav section label */}
      <div style={{ padding:'1.25rem 1rem 0.5rem' }}>
        <span style={{ fontSize:'0.65rem', fontWeight:600, textTransform:'uppercase', letterSpacing:'0.08em', color:'var(--text-muted)' }}>Navigation</span>
      </div>

      {/* Nav Items */}
      <nav style={{ flex:1, padding:'0 0.625rem', display:'flex', flexDirection:'column', gap:'2px', overflowY:'auto' }}>
        {navItems.map(item => {
          const Icon = item.icon;
          const active = isActive(item.id);
          const isAdminItem = item.id.startsWith('/admin');
          return (
            <button key={item.id}
              onClick={() => navigate(item.id)}
              className={`nav-item ${active ? 'active' : ''}`}
            >
              <Icon size={17} className="nav-icon"
                style={{ color: active ? 'var(--primary)' : isAdminItem ? 'var(--amber)' : 'inherit', transition:'color 0.2s' }} />
              <span style={{ flex:1 }}>{item.label}</span>
              {isAdminItem && (
                <span style={{ fontSize:'0.6rem', background:'var(--amber-light)', color:'var(--amber)',
                  padding:'2px 6px', borderRadius:'4px', fontWeight:700, border:'1px solid var(--border-amber)' }}>
                  ADMIN
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* User Profile */}
      <div style={{ borderTop:'1px solid var(--border-subtle)', padding:'0.875rem 0.625rem' }}>
        <div style={{ display:'flex', alignItems:'center', gap:'0.75rem', padding:'0.625rem 0.625rem 0.75rem',
          borderRadius:'var(--radius-md)', marginBottom:'4px' }}>
          <div style={{ width:'34px', height:'34px', borderRadius:'50%', flexShrink:0,
            background:'var(--gradient-primary)',
            display:'flex', alignItems:'center', justifyContent:'center',
            color:'#fff', fontWeight:700, fontSize:'0.9rem', boxShadow:'0 0 12px rgba(124,92,255,0.3)' }}>
            {user?.name?.charAt(0).toUpperCase()}
          </div>
          <div style={{ flex:1, minWidth:0 }}>
            <div style={{ fontSize:'0.8125rem', fontWeight:600, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
              {user?.name}
            </div>
            <div style={{ fontSize:'0.7rem', color:'var(--text-muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
              {user?.profileType || user?.role}
            </div>
          </div>
          {user?.role === 'ADMIN' && (
            <span style={{ fontSize:'0.6rem', background:'var(--primary-light)', color:'var(--primary)',
              padding:'2px 6px', borderRadius:'4px', fontWeight:700, border:'1px solid var(--border-violet)', flexShrink:0 }}>
              ADMIN
            </span>
          )}
        </div>
        <button onClick={handleLogout}
          className="nav-item"
          style={{ width:'100%', color:'var(--error)' }}>
          <LogOut size={17} />
          Sign Out
        </button>
      </div>
    </aside>
  );
}
