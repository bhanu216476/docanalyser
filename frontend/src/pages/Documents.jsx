import React from 'react';
import { FileText, Upload, CheckCircle, Clock, XCircle, Plus } from 'lucide-react';

function StatusBadge({ status }) {
  if (status === 'PROCESSED')  return <span className="badge badge-success"><CheckCircle size={10} /> Processed</span>;
  if (status === 'PROCESSING') return <span className="badge badge-amber"><Clock size={10} /> Processing</span>;
  if (status === 'FAILED')     return <span className="badge badge-error"><XCircle size={10} /> Failed</span>;
  return <span className="badge badge-cyan">{status}</span>;
}

export default function Documents({
  documents, handleUpload, isUploading, uploadMessage,
  uploadTitle, setUploadTitle, uploadCategory, setUploadCategory,
  uploadContent, setUploadContent
}) {
  const inputStyle = {
    width:'100%', padding:'0.75rem 1rem', background:'var(--bg-surface)',
    border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-md)',
    color:'var(--text-primary)', fontSize:'0.875rem', fontFamily:'inherit', outline:'none'
  };

  return (
    <div style={{ maxWidth:'1100px', width:'100%' }}>
      <div style={{ marginBottom:'2rem' }}>
        <h1 style={{ fontSize:'1.625rem', fontWeight:700, color:'var(--text-primary)', marginBottom:'0.375rem' }}>Document Library</h1>
        <p style={{ color:'var(--text-muted)', fontSize:'0.9rem' }}>Manage indexed documents in your knowledge base.</p>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 380px', gap:'1.5rem', alignItems:'start' }}>
        {/* Document Table */}
        <div style={{ background:'var(--bg-card)', border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-lg)', overflow:'hidden' }}>
          <div style={{ padding:'1.125rem 1.5rem', borderBottom:'1px solid var(--border-subtle)',
            display:'flex', alignItems:'center', justifyContent:'space-between' }}>
            <div style={{ display:'flex', alignItems:'center', gap:'0.625rem' }}>
              <div className="icon-box icon-box-sm icon-box-cyan"><FileText size={15} /></div>
              <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>
                Indexed Documents
                <span style={{ marginLeft:'0.5rem', fontSize:'0.75rem', color:'var(--text-muted)', fontWeight:400 }}>
                  ({documents.length})
                </span>
              </h3>
            </div>
          </div>

          {documents.length === 0 ? (
            <div style={{ padding:'4rem', textAlign:'center' }}>
              <div className="icon-box icon-box-lg icon-box-cyan" style={{ margin:'0 auto 1rem' }}><FileText size={24} /></div>
              <h3 style={{ color:'var(--text-primary)', marginBottom:'0.5rem' }}>No documents yet</h3>
              <p style={{ color:'var(--text-muted)', fontSize:'0.875rem' }}>Use the panel on the right to ingest your first document.</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Category</th>
                  <th>Chunks</th>
                  <th>Uploaded</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc, i) => (
                  <tr key={doc.id || i}>
                    <td>
                      <div style={{ display:'flex', alignItems:'center', gap:'0.75rem' }}>
                        <div className="icon-box icon-box-sm icon-box-cyan"><FileText size={14} /></div>
                        <span style={{ fontWeight:500, color:'var(--text-primary)' }}>{doc.title}</span>
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-violet">{doc.category}</span>
                    </td>
                    <td>
                      <span style={{ fontFamily:'var(--font-mono, monospace)', fontSize:'0.8rem', color:'var(--secondary)' }}>
                        {doc.chunks}
                      </span>
                    </td>
                    <td>{doc.uploadedAt}</td>
                    <td><StatusBadge status={doc.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Upload Panel */}
        <div style={{ background:'linear-gradient(145deg, rgba(124,92,255,0.06) 0%, var(--bg-card) 60%)', border:'1px solid var(--border-violet)', borderRadius:'var(--radius-lg)' }}>
          <div style={{ padding:'1.125rem 1.5rem', borderBottom:'1px solid var(--border-subtle)',
            display:'flex', alignItems:'center', gap:'0.625rem' }}>
            <div className="icon-box icon-box-sm icon-box-violet"><Upload size={15} /></div>
            <h3 style={{ fontSize:'0.9375rem', fontWeight:600, color:'var(--text-primary)' }}>Ingest Document</h3>
          </div>
          <div style={{ padding:'1.5rem' }}>
            {uploadMessage && (
              <div style={{ padding:'0.75rem 1rem', marginBottom:'1rem', borderRadius:'var(--radius-md)',
                background: uploadMessage.type === 'success' ? 'var(--success-light)' : 'var(--error-light)',
                border: `1px solid ${uploadMessage.type === 'success' ? 'rgba(34,197,94,0.25)' : 'rgba(244,63,94,0.25)'}`,
                color: uploadMessage.type === 'success' ? 'var(--success)' : 'var(--error)',
                fontSize:'0.8rem' }}>
                {uploadMessage.text}
              </div>
            )}

            <form onSubmit={handleUpload} style={{ display:'flex', flexDirection:'column', gap:'1rem' }}>
              <div className="input-group">
                <label>Document Title</label>
                <input type="text" placeholder="My Research Paper" value={uploadTitle}
                  onChange={e => setUploadTitle(e.target.value)} required style={inputStyle} />
              </div>

              <div className="input-group">
                <label>Category</label>
                <select value={uploadCategory} onChange={e => setUploadCategory(e.target.value)} style={{ ...inputStyle, cursor:'pointer' }}>
                  {['Engineering','Research','Architecture','Operations','Security','Finance'].map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              <div className="input-group">
                <label>Content / Text</label>
                <textarea placeholder="Paste your document content here to index it into the Qdrant vector store…"
                  value={uploadContent} onChange={e => setUploadContent(e.target.value)}
                  rows={6} required
                  style={{ ...inputStyle, resize:'vertical', lineHeight:1.6 }} />
              </div>

              <button type="submit" disabled={isUploading} className="btn btn-primary" style={{ width:'100%', justifyContent:'center' }}>
                {isUploading
                  ? <><Clock size={15} /> Ingesting…</>
                  : <><Plus size={15} /> Ingest Document</>
                }
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
