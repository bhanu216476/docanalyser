import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext();
const API_BASE = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8080' : 'https://docanalyser-backend.onrender.com');

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
          } else if (res.status === 401 || res.status === 403) {
            localStorage.removeItem('token');
            localStorage.removeItem('docanalyser_user');
            setUser(null);
          }
        } catch (err) {
          // If network unreachable, keep saved local user session
        }
      }

      setLoading(false);
    };
    checkSession();
  }, []);

  const login = async (email, password) => {
    let res;
    try {
      res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
    } catch (err) {
      // Backend completely unreachable: fallback for local demo
      const localUser = {
        id: `usr-${Date.now().toString().slice(-4)}`,
        name: email.split('@')[0] || 'User',
        email: email,
        role: email.toLowerCase().includes('admin') ? 'ADMIN' : 'USER'
      };
      setUser(localUser);
      localStorage.setItem('token', 'offline-demo-token');
      localStorage.setItem('docanalyser_user', JSON.stringify(localUser));
      return;
    }

    if (res.ok) {
      const data = await res.json();
      localStorage.setItem('token', data.token);

      let userData = {
        id: data.id || 'user-1',
        name: data.name || email.split('@')[0],
        email: data.email || email,
        role: data.role || 'USER'
      };

      try {
        const meRes = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { 'Authorization': `Bearer ${data.token}` }
        });
        if (meRes.ok) {
          userData = await meRes.json();
        }
      } catch (e) {}

      setUser(userData);
      localStorage.setItem('docanalyser_user', JSON.stringify(userData));
      return;
    }

    // Backend responded with an error (401, 400, etc.)
    let errMessage = 'Invalid email or password';
    try {
      const errData = await res.json();
      errMessage = errData.message || errData.error || (typeof errData === 'object' ? Object.values(errData)[0] : null) || errMessage;
    } catch (e) {}
    throw new Error(errMessage);
  };

  const register = async (userData) => {
    let res;
    try {
      res = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData)
      });
    } catch (err) {
      // Backend completely unreachable: fallback for local demo
      const localUser = {
        id: `usr-${Date.now().toString().slice(-4)}`,
        name: userData.name || 'User',
        email: userData.email,
        role: 'USER'
      };
      setUser(localUser);
      localStorage.setItem('token', 'offline-demo-token');
      localStorage.setItem('docanalyser_user', JSON.stringify(localUser));
      return;
    }

    if (res.ok) {
      return;
    }

    let errMessage = 'Registration failed';
    try {
      const errData = await res.json();
      errMessage = errData.message || errData.error || (typeof errData === 'object' ? Object.values(errData)[0] : null) || errMessage;
    } catch (e) {}
    throw new Error(errMessage);
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
