import React, { useEffect, useState } from 'react';
import { Users, UserCheck, UserX, Loader, RefreshCw } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080';

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchUsers = () => {
    setLoading(true);
    const token = localStorage.getItem('token');
    fetch(`${API_BASE}/api/admin/users`, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => { setUsers(Array.isArray(d) ? d : []); setError(''); })
      .catch(e => setError(`Could not load users. The /api/admin/users endpoint may not be running yet.\n${e.message}`))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleToggle = async (id, enabled) => {
    const token = localStorage.getItem('token');
    const action = enabled ? 'disable' : 'enable';
    try {
      const res = await fetch(`${API_BASE}/api/admin/users/${id}/${action}`, {
        method:'POST', headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) fetchUsers();
    } catch (e) { alert('Action failed: ' + e.message); }
  };

  return (
    <div style={{ maxWidth:'1100px', width:'100%' }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-end', marginBottom:'2rem' }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:'0.75rem', marginBottom:'0.375rem' }}>
            <h1 style={{ fontSize:'1.625rem', fontWeight:700, color:'var(--text-primary)' }}>User Management</h1>
            <span className="badge badge-violet">ADMIN</span>
          </div>
          <p style={{ color:'var(--text-muted)', fontSize:'0.9rem' }}>View and manage platform users. All actions are backend-enforced.</p>
        </div>
        <button onClick={fetchUsers} className="btn btn-secondary" style={{ display:'flex', alignItems:'center', gap:'0.5rem' }}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {loading && (
        <div style={{ display:'flex', alignItems:'center', gap:'0.625rem', color:'var(--text-muted)', padding:'2rem' }}>
          <Loader size={16} className="animate-spin" /> Loading users…
        </div>
      )}

      {error && !loading && (
        <div style={{ padding:'1rem 1.25rem', background:'var(--error-light)', borderLeft:'3px solid var(--error)',
          borderRadius:'0 var(--radius-md) var(--radius-md) 0', color:'var(--error)', fontSize:'0.875rem',
          marginBottom:'1.5rem', whiteSpace:'pre-line' }}>
          {error}
        </div>
      )}

      {!loading && (
        <div style={{ background:'var(--bg-card)', border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-lg)', overflow:'hidden' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Profile</th>
                <th>Role</th>
                <th>Status</th>
                <th>Joined</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding:'3.5rem', textAlign:'center', color:'var(--text-muted)' }}>
                    <div className="icon-box icon-box-lg icon-box-violet" style={{ margin:'0 auto 1rem' }}>
                      <Users size={26} />
                    </div>
                    <p>No users found. The backend <code style={{ color:'var(--primary)' }}>/api/admin/users</code> endpoint needs to be running.</p>
                  </td>
                </tr>
              ) : users.map((u, i) => (
                <tr key={u.id || i}>
                  <td>
                    <div style={{ display:'flex', alignItems:'center', gap:'0.75rem' }}>
                      <div style={{ width:'34px', height:'34px', borderRadius:'50%', flexShrink:0,
                        background:'var(--gradient-primary)', display:'flex', alignItems:'center', justifyContent:'center',
                        color:'#fff', fontWeight:700, fontSize:'0.875rem' }}>
                        {u.name?.charAt(0)?.toUpperCase()}
                      </div>
                      <div>
                        <div style={{ fontWeight:500, color:'var(--text-primary)', fontSize:'0.875rem' }}>{u.name}</div>
                        <div style={{ fontSize:'0.75rem', color:'var(--text-muted)' }}>{u.email}</div>
                      </div>
                    </div>
                  </td>
                  <td>{u.profileType ? <span className="badge badge-cyan">{u.profileType}</span> : <span style={{ color:'var(--text-muted)', fontSize:'0.8rem' }}>—</span>}</td>
                  <td><span className={u.role === 'ADMIN' ? 'badge badge-violet' : 'badge badge-cyan'}>{u.role}</span></td>
                  <td>
                    <span className={u.enabled !== false ? 'badge badge-success' : 'badge badge-error'}>
                      {u.enabled !== false ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td style={{ fontSize:'0.78rem', color:'var(--text-muted)' }}>
                    {u.createdAt ? new Date(u.createdAt).toLocaleDateString() : '—'}
                  </td>
                  <td>
                    <button onClick={() => handleToggle(u.id, u.enabled !== false)}
                      className={u.enabled !== false ? 'btn btn-danger' : 'btn btn-secondary'}
                      style={{ fontSize:'0.78rem', padding:'0.3rem 0.75rem' }}>
                      {u.enabled !== false
                        ? <><UserX size={13} /> Disable</>
                        : <><UserCheck size={13} /> Enable</>
                      }
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
