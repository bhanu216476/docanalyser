import React from 'react';
import { Database, Layers, Hash, Activity } from 'lucide-react';

export default function KnowledgeBase({ documents = [] }) {
  const totalChunks = documents.reduce((acc, doc) => acc + (doc.chunks || 0), 0);

  // Group documents by collection / category
  const collectionsMap = documents.reduce((acc, doc) => {
    const cat = doc.category || 'Engineering';
    if (!acc[cat]) acc[cat] = { name: cat, docCount: 0, chunkCount: 0 };
    acc[cat].docCount += 1;
    acc[cat].chunkCount += (doc.chunks || 0);
    return acc;
  }, {});

  const collections = Object.values(collectionsMap);

  return (
    <div style={{ maxWidth: '1200px', width: '100%', margin: '0 auto', padding: '24px' }}>
      {/* Page Title */}
      <div style={{ marginBottom: '24px' }}>
        <h1 className="page-title">Knowledge</h1>
        <p style={{ color: 'var(--t2)', fontSize: '13.5px', marginTop: '4px' }}>
          Vector storage, embeddings, and active document collection metrics.
        </p>
      </div>

      {/* Headline Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--mu)', fontWeight: 500 }}>Documents</span>
            <Database size={16} style={{ color: 'var(--ac)' }} />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--tx)' }}>
            {documents.length}
          </div>
          <div style={{ fontSize: '11.5px', color: 'var(--t2)', marginTop: '4px' }}>
            Active indexed files
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--mu)', fontWeight: 500 }}>Chunks</span>
            <Layers size={16} style={{ color: 'var(--ac)' }} />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--tx)', fontFamily: 'JetBrains Mono' }}>
            {totalChunks}
          </div>
          <div style={{ fontSize: '11.5px', color: 'var(--t2)', marginTop: '4px' }}>
            Tokenized context blocks
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--mu)', fontWeight: 500 }}>Vector Index</span>
            <Hash size={16} style={{ color: 'var(--ac)' }} />
          </div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--tx)' }}>
            1,536 Dim
          </div>
          <div style={{ fontSize: '11.5px', color: 'var(--ok)', marginTop: '4px' }}>
            Qdrant Cosine HNSW
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--mu)', fontWeight: 500 }}>Last Sync</span>
            <Activity size={16} style={{ color: 'var(--ok)' }} />
          </div>
          <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--tx)' }}>
            Real-time
          </div>
          <div style={{ fontSize: '11.5px', color: 'var(--t2)', marginTop: '4px' }}>
            Sync status
          </div>
        </div>
      </div>

      {/* Collections Section */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '24px' }}>
        <h2 className="font-fraunces" style={{ fontSize: '18px', fontWeight: 600, color: 'var(--tx)' }}>
          Document Collections
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
          {collections.length === 0 ? (
            <div className="card" style={{ gridColumn: '1 / -1', padding: '32px', textAlign: 'center', color: 'var(--t2)' }}>
              No collections created yet. Upload a document to build knowledge collections.
            </div>
          ) : (
            collections.map((col) => (
              <div key={col.name} className="card">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--tx)' }}>{col.name}</h3>
                  <span className="badge badge-violet">{col.docCount} docs</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12.5px', color: 'var(--t2)' }}>
                  <span>Indexed Chunks</span>
                  <span style={{ fontFamily: 'JetBrains Mono', fontWeight: 600, color: 'var(--ac)' }}>{col.chunkCount}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Active Knowledge Base Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--bd)' }}>
          <h3 className="font-fraunces" style={{ fontSize: '16px', fontWeight: 600, color: 'var(--tx)' }}>
            Active Knowledge Base Items
          </h3>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Document</th>
              <th>Collection</th>
              <th>Chunks</th>
              <th>Vector Index</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {documents.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: 'var(--mu)' }}>
                  No documents in knowledge base.
                </td>
              </tr>
            ) : (
              documents.map((doc, idx) => (
                <tr key={doc.id || idx}>
                  <td style={{ fontWeight: 600, color: 'var(--tx)' }}>{doc.title || doc.fileName}</td>
                  <td><span className="badge badge-violet">{doc.category || 'Engineering'}</span></td>
                  <td style={{ fontFamily: 'JetBrains Mono', color: 'var(--ac)' }}>{doc.chunks || 0}</td>
                  <td style={{ fontSize: '12px', color: 'var(--t2)' }}>Qdrant · 1536d</td>
                  <td><span className="badge badge-success">Indexed</span></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
