import React, { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { FileText, Search, LogOut, Shield, Menu, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import ThemeToggle from './ThemeToggle';
import SearchCommand from './SearchCommand';

export default function TopBar({ backendHealth = 'checking', ragHealth = 'checking', documents = [] }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

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
    { label: 'Ask AI', path: '/ask-ai' },
    { label: 'Documents', path: '/documents' },
    { label: 'Knowledge', path: '/knowledge' },
    { label: 'Retrieval', path: '/retrieval' },
    { label: 'Verification', path: '/verification' },
    { label: 'System', path: '/system' },
  ];

  return (
    <>
      <header className="topbar">
        {/* Left: Brand Logo & Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <NavLink to="/ask-ai" className="topbar-brand">
            <div className="topbar-logo">
              <FileText size={17} />
            </div>
            <span className="topbar-title">DocAnalyser</span>
          </NavLink>

          {/* Desktop Navigation Links */}
          <nav className="topbar-nav">
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
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {/* Search Trigger */}
          <button
            type="button"
            className="topbar-search-btn"
            onClick={() => setIsSearchOpen(true)}
            aria-label="Search documents"
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
              style={{ padding: '6px 10px' }}
            >
              <Shield size={16} style={{ color: 'var(--ac)' }} />
            </button>
          )}

          {/* Logout Button */}
          {user && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={logout}
              title="Sign Out"
              style={{ padding: '6px 10px', color: 'var(--mu)' }}
            >
              <LogOut size={16} />
            </button>
          )}

          {/* Mobile Hamburger Toggle */}
          <button
            type="button"
            className="btn btn-ghost mobile-nav-menu"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            aria-label="Toggle navigation menu"
            style={{ padding: '6px' }}
          >
            {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </header>

      {/* Mobile Drawer Menu */}
      {isMobileMenuOpen && (
        <div
          style={{
            position: 'fixed',
            top: '54px',
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'var(--s1)',
            zIndex: 40,
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            borderBottom: '1px solid var(--bd)'
          }}
        >
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => setIsMobileMenuOpen(false)}
              style={{
                padding: '12px 16px',
                borderRadius: 'var(--r-md)',
                color: location.pathname === item.path ? 'var(--ac)' : 'var(--tx)',
                fontWeight: location.pathname === item.path ? '600' : '400',
                backgroundColor: location.pathname === item.path ? 'var(--s2)' : 'transparent',
                textDecoration: 'none',
                fontSize: '15px'
              }}
            >
              {item.label}
            </NavLink>
          ))}
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
