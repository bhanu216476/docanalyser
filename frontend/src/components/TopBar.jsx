import React, { useState, useEffect } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { 
  FileText, Search, LogOut, Shield, Menu, X, 
  MessageSquare, Database, Cpu, ShieldCheck, Activity, User
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import ThemeToggle from './ThemeToggle';
import SearchCommand from './SearchCommand';

export default function TopBar({ backendHealth = 'checking', ragHealth = 'checking', documents = [] }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Lock body scroll when mobile drawer is open
  useEffect(() => {
    if (isMobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isMobileMenuOpen]);

  // Close drawer on ESC key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isMobileMenuOpen) {
        setIsMobileMenuOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isMobileMenuOpen]);

  // Overall system health calculation based on real health inputs
  let overallHealth = 'Healthy';
  let healthClass = 'healthy';

  if (backendHealth === 'offline' && ragHealth === 'offline') {
    overallHealth = 'Offline';
    healthClass = 'offline';
  } else if (backendHealth === 'offline' || ragHealth === 'offline') {
    overallHealth = 'Degraded';
    healthClass = 'degraded';
  } else if (backendHealth === 'checking' || ragHealth === 'checking') {
    overallHealth = 'Checking...';
    healthClass = 'degraded';
  }

  const navItems = [
    { label: 'Ask AI', path: '/ask-ai', icon: MessageSquare },
    { label: 'Documents', path: '/documents', icon: FileText },
    { label: 'Knowledge', path: '/knowledge', icon: Database },
    { label: 'Retrieval', path: '/retrieval', icon: Cpu },
    { label: 'Verification', path: '/verification', icon: ShieldCheck },
    { label: 'System', path: '/system', icon: Activity },
  ];

  return (
    <>
      <header className="topbar">
        {/* Left: Brand Logo & Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <NavLink to="/ask-ai" className="topbar-brand" aria-label="DocAnalyser Home">
            <div className="topbar-logo">
              <FileText size={17} />
            </div>
            <span className="topbar-title">DocAnalyser</span>
          </NavLink>

          {/* Desktop Navigation Links */}
          <nav className="topbar-nav" aria-label="Main Navigation">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path || (item.path === '/ask-ai' && location.pathname === '/');
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={`topbar-nav-item ${isActive ? 'active' : ''}`}
                >
                  {item.label}
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Right: Search, Health, Theme, Profile */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Search Trigger */}
          <button
            type="button"
            className="topbar-search-btn"
            onClick={() => setIsSearchOpen(true)}
            aria-label="Search documents (Ctrl + K)"
          >
            <Search size={14} />
            <span>Search documents</span>
            <span className="kbd-badge">Ctrl K</span>
          </button>

          {/* Real System Health Pill */}
          <div className="health-pill" title={`Spring API: ${backendHealth} | Python RAG: ${ragHealth}`}>
            <span className={`health-dot ${healthClass}`} />
            <span>{overallHealth}</span>
          </div>

          {/* Theme Toggle */}
          <ThemeToggle />

          {/* Admin link if user is ADMIN */}
          {user?.role === 'ADMIN' && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => navigate('/admin')}
              title="Admin Dashboard"
              style={{ padding: '6px 10px', minHeight: '36px' }}
            >
              <Shield size={16} style={{ color: 'var(--ac)' }} />
            </button>
          )}

          {/* Logout Button (Desktop) */}
          {user && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={logout}
              title="Sign Out"
              style={{ padding: '6px 10px', color: 'var(--mu)', minHeight: '36px' }}
            >
              <LogOut size={16} />
            </button>
          )}

          {/* Mobile Hamburger Toggle */}
          <button
            type="button"
            className="btn btn-ghost mobile-nav-menu"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            aria-label={isMobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={isMobileMenuOpen}
            style={{ padding: '8px', minWidth: '40px', minHeight: '40px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            {isMobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </header>

      {/* Mobile Drawer Menu */}
      {isMobileMenuOpen && (
        <div 
          className="mobile-drawer-overlay"
          onClick={() => setIsMobileMenuOpen(false)}
        >
          <div 
            className="mobile-drawer-content"
            onClick={(e) => e.stopPropagation()}
          >
            {/* User Profile Summary Header */}
            {user && (
              <div 
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '12px 14px',
                  backgroundColor: 'var(--s2)',
                  borderRadius: 'var(--r-md)',
                  marginBottom: '8px'
                }}
              >
                <div 
                  style={{
                    width: '38px',
                    height: '38px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--ac)',
                    color: '#FFFFFF',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 700,
                    fontSize: '15px'
                  }}
                >
                  {user.name ? user.name.charAt(0).toUpperCase() : <User size={18} />}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--tx)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {user.name || 'User'}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--t2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {user.email}
                  </div>
                </div>
                {user.role === 'ADMIN' && (
                  <span className="badge badge-violet">ADMIN</span>
                )}
              </div>
            )}

            {/* Quick Search Trigger in Drawer */}
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setIsMobileMenuOpen(false);
                setIsSearchOpen(true);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-start',
                gap: '10px',
                padding: '10px 14px',
                width: '100%',
                marginBottom: '8px',
                fontSize: '13.5px'
              }}
            >
              <Search size={15} style={{ color: 'var(--ac)' }} />
              <span>Search knowledge base...</span>
            </button>

            {/* Navigation links */}
            <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path || (item.path === '/ask-ai' && location.pathname === '/');
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={`mobile-nav-item ${isActive ? 'active' : ''}`}
                  >
                    <Icon size={17} style={{ color: isActive ? 'var(--ac)' : 'var(--mu)' }} />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}

              {/* Admin Portal Link */}
              {user?.role === 'ADMIN' && (
                <NavLink
                  to="/admin"
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`mobile-nav-item ${location.pathname.startsWith('/admin') ? 'active' : ''}`}
                >
                  <Shield size={17} style={{ color: 'var(--ac)' }} />
                  <span>Admin Console</span>
                </NavLink>
              )}
            </nav>

            {/* Bottom Actions */}
            <div 
              style={{
                marginTop: '12px',
                paddingTop: '12px',
                borderTop: '1px solid var(--bd)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '10px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ThemeToggle />
                <span style={{ fontSize: '12.5px', color: 'var(--t2)' }}>Theme</span>
              </div>

              {user && (
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => {
                    setIsMobileMenuOpen(false);
                    logout();
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    color: 'var(--err)',
                    fontSize: '13px',
                    padding: '8px 12px'
                  }}
                >
                  <LogOut size={15} />
                  <span>Sign Out</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Command Palette */}
      <SearchCommand
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        documents={documents}
      />
    </>
  );
}
