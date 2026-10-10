import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { Navigate, Link, useNavigate } from 'react-router-dom';
import { FileText, CheckCircle2, Eye, EyeOff } from 'lucide-react';

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loginStep, setLoginStep] = useState('idle');

  if (user) return <Navigate to="/ask-ai" replace />;

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }
    setError('');
    setIsSubmitting(true);
    setLoginStep('verifying');
    try {
      await login(email, password);
      setLoginStep('success');
      setTimeout(() => navigate('/ask-ai'), 1000);
    } catch {
      setLoginStep('idle');
      setIsSubmitting(false);
      setError("Email or password is incorrect.");
    }
  };

  return (
    <div className="auth-layout">
      {/* LEFT BRANDING */}
      <div className="auth-branding">
        <div style={{ position: 'relative', zIndex: 1, maxWidth: '460px' }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '40px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '8px',
                backgroundColor: 'var(--ac)',
                color: '#FFFFFF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <FileText size={20} />
            </div>
            <span className="font-fraunces" style={{ fontSize: '20px', fontWeight: 600, color: 'var(--tx)' }}>
              DocAnalyser
            </span>
          </div>

          <h2 className="font-fraunces" style={{ fontSize: '38px', fontWeight: 600, lineHeight: 1.2, color: 'var(--tx)', marginBottom: '16px' }}>
            Your knowledge.<br />
            Made <span style={{ color: 'var(--ac)' }}>intelligent.</span>
          </h2>
          <p style={{ fontSize: '14px', color: 'var(--t2)', lineHeight: 1.6 }}>
            Ask questions, discover insights, and get grounded, citation-verified answers from your enterprise knowledge base.
          </p>
        </div>
      </div>

      {/* RIGHT FORM */}
      <div className="auth-form-side">
        <AnimatePresence mode="wait">
          {loginStep === 'success' ? (
            <motion.div
              key="success"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', textAlign: 'center' }}
            >
              <div
                style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(15, 123, 87, 0.1)',
                  color: 'var(--ok)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <CheckCircle2 size={36} />
              </div>
              <div>
                <h3 className="font-fraunces" style={{ fontSize: '22px', fontWeight: 600, color: 'var(--tx)', marginBottom: '6px' }}>
                  Identity Verified
                </h3>
                <p style={{ color: 'var(--t2)', fontSize: '13.5px' }}>
                  Preparing your workspace...
                </p>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="form"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              style={{ width: '100%', maxWidth: '400px' }}
            >
              <div style={{ marginBottom: '24px' }}>
                <h2 className="font-fraunces" style={{ fontSize: '24px', fontWeight: 600, color: 'var(--tx)', marginBottom: '6px' }}>
                  Welcome back
                </h2>
                <p style={{ color: 'var(--t2)', fontSize: '13px' }}>
                  Sign in to your knowledge workspace.
                </p>
              </div>

              {error && (
                <div
                  style={{
                    padding: '10px 14px',
                    backgroundColor: 'rgba(229,72,77,0.1)',
                    border: '1px solid rgba(229,72,77,0.2)',
                    borderRadius: 'var(--r-md)',
                    color: 'var(--err)',
                    marginBottom: '18px',
                    fontSize: '13px'
                  }}
                >
                  {error}
                </div>
              )}

              <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div className="input-group">
                  <label>Email address</label>
                  <input
                    type="email"
                    placeholder="name@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="auth-input"
                    required
                  />
                </div>

                <div className="input-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label>Password</label>
                  </div>
                  <div style={{ position: 'relative' }}>
                    <input
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="auth-input"
                      style={{ paddingRight: '36px' }}
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      tabIndex={-1}
                      style={{
                        position: 'absolute',
                        right: '10px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        color: 'var(--mu)',
                        cursor: 'pointer'
                      }}
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="btn-auth"
                  style={{ marginTop: '8px' }}
                >
                  {loginStep === 'verifying' ? 'Verifying...' : 'Sign In'}
                </button>
              </form>

              <div style={{ height: '1px', backgroundColor: 'var(--bd)', margin: '24px 0' }} />

              <p style={{ textAlign: 'center', fontSize: '13px', color: 'var(--t2)' }}>
                Don't have an account?{' '}
                <Link to="/register" style={{ color: 'var(--ac)', fontWeight: 600, textDecoration: 'none' }}>
                  Create account
                </Link>
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
