import React, { useState, useEffect, useRef } from 'react';
import { Palette, Check, Sun, Moon, Sparkles } from 'lucide-react';

const THEMES = [
  { id: 'mint', name: 'Mint Emerald', color: '#0D9488', description: 'Clean document intelligence aesthetic (Default)' },
  { id: 'indigo', name: 'Cyber Indigo', color: '#4F46E5', description: 'Deep purple & violet' },
  { id: 'ocean', name: 'Ocean Cyan', color: '#0284C7', description: 'Vibrant clean cyan' },
  { id: 'amber', name: 'Sunset Amber', color: '#D97706', description: 'Warm energetic amber' },
  { id: 'paper', name: 'Classic Paper', color: '#2F5BFF', description: 'Minimalist paper' },
  { id: 'midnight', name: 'Obsidian OLED', color: '#14B8A6', description: 'Deep night mode' },
];

export default function ThemeSelector() {
  const [currentTheme, setCurrentTheme] = useState(() => {
    return localStorage.getItem('docanalyser_theme') || 'mint';
  });
  const [isDarkMode, setIsDarkMode] = useState(() => {
    return localStorage.getItem('docanalyser_mode') === 'dark';
  });
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);

  // Synchronize color theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('docanalyser_theme', currentTheme);
  }, [currentTheme]);

  // Synchronize Day / Night mode
  useEffect(() => {
    document.documentElement.setAttribute('data-mode', isDarkMode ? 'dark' : 'light');
    localStorage.setItem('docanalyser_mode', isDarkMode ? 'dark' : 'light');
  }, [isDarkMode]);

  // Close popup when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggleDayNight = () => {
    setIsDarkMode(prev => !prev);
  };

  const activeThemeObj = THEMES.find(t => t.id === currentTheme) || THEMES[0];

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      {/* Day / Night Theme Toggle Button */}
      <button
        type="button"
        onClick={toggleDayNight}
        className="btn-day-night-toggle"
        title={isDarkMode ? "Switch to Day Mode (Sun)" : "Switch to Night Mode (Moon)"}
        aria-label="Toggle Day and Night Theme"
      >
        <span className="day-night-icon-wrapper">
          {isDarkMode ? (
            <Moon size={14} style={{ color: '#38BDF8' }} />
          ) : (
            <Sun size={14} style={{ color: '#F59E0B' }} />
          )}
        </span>
        <span>{isDarkMode ? 'Night' : 'Day'}</span>
      </button>

      {/* Palette Color Picker */}
      <div ref={containerRef} style={{ position: 'relative' }}>
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="icon-button"
          title={`Color Palette (${activeThemeObj.name})`}
          aria-label="Color Palette Selector"
          style={{ display: 'flex', alignItems: 'center', gap: '6px', width: 'auto', padding: '0 8px' }}
        >
          <span
            className="theme-color-swatch"
            style={{ backgroundColor: activeThemeObj.color }}
          />
          <Palette size={14} />
        </button>

        {isOpen && (
          <div className="theme-picker-popup">
            <div style={{ padding: '4px 6px 8px', borderBottom: '1px solid var(--bd)', marginBottom: '4px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--mu)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Color Palettes
              </span>
              <span style={{ fontSize: '10.5px', color: 'var(--ac)', fontWeight: 600 }}>
                {isDarkMode ? '🌙 Night Mode' : '☀️ Day Mode'}
              </span>
            </div>

            {THEMES.map((theme) => {
              const isSelected = currentTheme === theme.id;
              return (
                <button
                  key={theme.id}
                  type="button"
                  onClick={() => {
                    setCurrentTheme(theme.id);
                    setIsOpen(false);
                  }}
                  className={`theme-picker-option ${isSelected ? 'active' : ''}`}
                >
                  <span
                    className="theme-color-swatch"
                    style={{ backgroundColor: theme.color }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '12.5px', fontWeight: isSelected ? 600 : 500 }}>
                      {theme.name}
                    </div>
                  </div>
                  {isSelected && <Check size={14} style={{ color: 'var(--ac)' }} />}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
