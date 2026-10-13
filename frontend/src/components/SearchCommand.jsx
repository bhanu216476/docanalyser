import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, FileText, MessageSquare, Database, Cpu, ShieldCheck, Activity, ArrowRight } from 'lucide-react';

export default function SearchCommand({ isOpen, onClose, documents = [] }) {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (isOpen) onClose();
        else setQuery('');
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const quickPages = [
    { title: 'Ask AI', path: '/ask-ai', icon: MessageSquare, category: 'Navigation' },
    { title: 'Documents', path: '/documents', icon: FileText, category: 'Navigation' },
    { title: 'Knowledge', path: '/knowledge', icon: Database, category: 'Navigation' },
    { title: 'Retrieval', path: '/retrieval', icon: Cpu, category: 'Navigation' },
    { title: 'Verification', path: '/verification', icon: ShieldCheck, category: 'Navigation' },
    { title: 'System', path: '/system', icon: Activity, category: 'Navigation' },
  ];

  const filteredPages = quickPages.filter(p => p.title.toLowerCase().includes(query.toLowerCase()));
  const filteredDocs = documents.filter(d => 
    (d.title || d.fileName || '').toLowerCase().includes(query.toLowerCase())
  );

  const handleSelect = (path) => {
    navigate(path);
    onClose();
  };

  return (
    <div className="cmd-overlay" onClick={onClose}>
      <div className="cmd-dialog" onClick={(e) => e.stopPropagation()}>
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Search size={18} style={{ position: 'absolute', left: '16px', color: 'var(--mu)' }} />
          <input
            type="text"
            className="cmd-input"
            placeholder="Search documents, pages, or commands..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ paddingLeft: '44px' }}
            autoFocus
          />
        </div>
        <div className="cmd-list">
          {filteredPages.length > 0 && (
            <div style={{ marginBottom: '12px' }}>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--mu)', padding: '6px 12px', textTransform: 'uppercase' }}>
                Pages
              </div>
              {filteredPages.map((page) => {
                const Icon = page.icon;
                return (
                  <div
                    key={page.path}
                    className="cmd-item"
                    onClick={() => handleSelect(page.path)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <Icon size={16} style={{ color: 'var(--ac)' }} />
                      <span>{page.title}</span>
                    </div>
                    <ArrowRight size={14} style={{ color: 'var(--mu)' }} />
                  </div>
                );
              })}
            </div>
          )}

          {filteredDocs.length > 0 && (
            <div>
              <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--mu)', padding: '6px 12px', textTransform: 'uppercase' }}>
                Documents ({filteredDocs.length})
              </div>
              {filteredDocs.map((doc) => (
                <div
                  key={doc.id}
                  className="cmd-item"
                  onClick={() => handleSelect('/documents')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <FileText size={16} style={{ color: 'var(--t2)' }} />
                    <span style={{ fontWeight: 500 }}>{doc.title || doc.fileName}</span>
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--mu)', fontFamily: 'JetBrains Mono' }}>
                    {doc.chunks ? `${doc.chunks} chunks` : 'Indexed'}
                  </span>
                </div>
              ))}
            </div>
          )}

          {filteredPages.length === 0 && filteredDocs.length === 0 && (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--mu)', fontSize: '13px' }}>
              No results found for "{query}"
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
