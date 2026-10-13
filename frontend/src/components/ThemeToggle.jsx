import React, { useState, useEffect } from 'react';
import { Sun, Moon } from 'lucide-react';

export default function ThemeToggle() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('docanalyser_theme') || 'paper';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('docanalyser_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'paper' ? 'midnight' : 'paper'));
  };

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="btn btn-ghost"
      title={`Switch to ${theme === 'paper' ? 'Midnight' : 'Paper'} theme`}
      style={{ padding: '6px 10px', borderRadius: 'var(--r-md)' }}
      aria-label="Toggle theme"
    >
      {theme === 'paper' ? (
        <Moon size={16} style={{ color: 'var(--t2)' }} />
      ) : (
        <Sun size={16} style={{ color: '#F59E0B' }} />
      )}
    </button>
  );
}
