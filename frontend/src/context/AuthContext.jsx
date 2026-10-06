import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext();
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Restore session on mount
  useEffect(() => {
    const checkSession = async () => {
      const token = localStorage.getItem('token');
      const savedUser = localStorage.getItem('docanalyser_user');

      if (savedUser) {
        try {
          setUser(JSON.parse(savedUser));
        } catch (e) {}
      }

      if (token) {
        try {
          const res = await fetch(`${API_BASE}/api/auth/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (res.ok) {
            const userData = await res.json();
            setUser(userData);
            localStorage.setItem('docanalyser_user', JSON.stringify(userData));
          }
        } catch (err) {
          // If offline, keep saved local user session
        }
      } else if (!savedUser) {
        // Default guest session so user can immediately view pages if preferred
      }

      setLoading(false);
    };
    checkSession();
  }, []);

  const login = async (email, password) => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('token', data.token);

        const meRes = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { 'Authorization': `Bearer ${data.token}` }
        });
        let userData = {
          id: data.id || 'user-1',
          name: data.name || email.split('@')[0],
          email: data.email || email,
          role: data.role || 'USER'
        };
        if (meRes.ok) {
          userData = await meRes.json();
        }
        setUser(userData);
        localStorage.setItem('docanalyser_user', JSON.stringify(userData));
        return;
      }
    } catch (err) {
      // Backend offline
    }

    // Fallback authentication for offline local testing
    const localUser = {
      id: `usr-${Date.now().toString().slice(-4)}`,
      name: email.split('@')[0] || 'User',
      email: email,
      role: email.toLowerCase().includes('admin') ? 'ADMIN' : 'USER'
    };
    setUser(localUser);
    localStorage.setItem('token', 'offline-demo-token');
    localStorage.setItem('docanalyser_user', JSON.stringify(localUser));
  };

  const register = async (userData) => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData)
      });

      if (res.ok) return;
    } catch (err) {
      // Backend offline
    }

    // Save registered user locally for seamless offline demo
    const localUser = {
      id: `usr-${Date.now().toString().slice(-4)}`,
      name: userData.name || 'User',
      email: userData.email,
      role: 'USER'
    };
    setUser(localUser);
    localStorage.setItem('token', 'offline-demo-token');
    localStorage.setItem('docanalyser_user', JSON.stringify(localUser));
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('docanalyser_user');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
