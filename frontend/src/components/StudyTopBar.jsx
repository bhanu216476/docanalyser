import React, { useState } from 'react';
import { 
  PanelLeft, RotateCcw, Bot, Shield, ChevronDown, 
  Files, Database, GitMerge, ShieldCheck, Activity, Users, LogOut 
} from 'lucide-react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import ThemeSelector from './ThemeSelector';

export default function StudyTopBar({
  isSidebarOpen,
  onToggleSidebar,
  onResetChat,
  backendHealth = 'healthy',
  ragHealth = 'healthy',
  assistantName = 'MADDY'
}) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [showNavMenu, setShowNavMenu] = useState(false);

  const isConnected = backendHealth !== 'offline' && ragHealth !== 'offline';

  const navLinks = [
    { label: 'Document Q&A', path: '/ask-ai', icon: Bot },
    { label: 'Document Library', path: '/documents', icon: Files },
    { label: 'Knowledge Base', path: '/knowledge', icon: Database },
    { label: 'Hybrid Retrieval', path: '/retrieval', icon: GitMerge },
    { label: 'Citations & Faithfulness', path: '/verification', icon: ShieldCheck },
    { label: 'System Health', path: '/system', icon: Activity },
  ];

  if (user?.role === 'ADMIN') {
    navLinks.push(
      { label: 'Admin Dashboard', path: '/admin', icon: Activity },
      { label: 'User Management', path: '/admin/users', icon: Users }
    );
  }

  return (
    <header className="study-topbar">
      {/* Left side */}
      <div className="study-topbar-left">
        {/* Sidebar Toggle Button */}
        <button
          type="button"
          onClick={onToggleSidebar}
          className="icon-button"
          title={isSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          aria-label="Toggle sidebar"
        >
          <PanelLeft size={18} />
        </button>

        {/* Mode Pill: Study Assistant */}
        <div style={{ position: 'relative' }}>
          <button
            type="button"
            onClick={() => setShowNavMenu(!showNavMenu)}
            className="study-mode-pill"
            style={{ cursor: 'pointer', background: 'transparent' }}
            title="Switch Platform View"
          >
            <span className="pulse-dot" />
            <span>DocAnalyser</span>
            <ChevronDown size={12} style={{ color: 'var(--mu)', marginLeft: '2px' }} />
          </button>

          {/* Navigation Dropdown Menu to access other pages */}
          {showNavMenu && (
            <div
              style={{
                position: 'absolute',
                top: '44px',
                left: 0,
                backgroundColor: 'var(--s1)',
                border: '1px solid var(--bd)',
                borderRadius: 'var(--r-lg)',
                boxShadow: 'var(--shadow-lg)',
                padding: '8px',
                minWidth: '220px',
                zIndex: 60,
                display: 'flex',
                flexDirection: 'column',
                gap: '4px'
              }}
            >
              <div style={{ padding: '4px 8px 6px', fontSize: '11px', fontWeight: 600, color: 'var(--mu)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Views & Tools
              </div>
              {navLinks.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={() => setShowNavMenu(false)}
                    style={({ isActive }) => ({
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '7px 10px',
                      borderRadius: 'var(--r-md)',
                      fontSize: '12.5px',
                      fontWeight: isActive ? 600 : 500,
                      color: isActive ? 'var(--ac)' : 'var(--tx)',
                      backgroundColor: isActive ? 'var(--ac-light)' : 'transparent',
                      textDecoration: 'none',
                      transition: 'background-color 0.15s ease'
                    })}
                  >
                    <Icon size={14} style={{ color: 'inherit' }} />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}

              {user && (
                <div style={{ borderTop: '1px solid var(--bd)', marginTop: '4px', paddingTop: '4px' }}>
                  <button
                    type="button"
                    onClick={() => {
                      setShowNavMenu(false);
                      logout();
                      navigate('/login');
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '7px 10px',
                      borderRadius: 'var(--r-md)',
                      fontSize: '12px',
                      color: 'var(--err)',
                      background: 'none',
                      border: 'none',
                      width: '100%',
                      cursor: 'pointer',
                      textAlign: 'left'
                    }}
                  >
                    <LogOut size={13} />
                    <span>Sign Out ({user.name || user.username})</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right side: Sparky mascot badge, Connected badge, Theme Palette, Refresh */}
      <div className="study-topbar-right">
        {/* Mascot Sparky Pill */}
        <div className="sparky-badge">
          <Bot size={14} />
          <span>{assistantName}</span>
        </div>

        {/* Status Badge: Connected */}
        <div className="connected-badge">
          <span
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: isConnected ? 'var(--ok)' : 'var(--err)',
              boxShadow: isConnected ? '0 0 6px var(--ok)' : 'none'
            }}
          />
          <span>{isConnected ? 'Connected' : 'Offline'}</span>
        </div>

        {/* Multi-Color Theme Switcher */}
        <ThemeSelector />

        {/* Reset / New Chat Icon Button */}
        <button
          type="button"
          onClick={onResetChat}
          className="icon-button"
          title="Reset Conversation"
          aria-label="Reset Conversation"
        >
          <RotateCcw size={15} />
        </button>
      </div>
    </header>
  );
}

