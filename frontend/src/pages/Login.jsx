import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { Navigate, Link, useNavigate } from 'react-router-dom';
import { Zap, ShieldCheck, Database, FileText, Eye, EyeOff } from 'lucide-react';

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loginStep, setLoginStep] = useState('idle');

  if (user) return <Navigate to="/" replace />;

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!email || !password) { setError("Please enter both email and password."); return; }
    setError('');
    setIsSubmitting(true);
    setLoginStep('verifying');
    try {
      await login(email, password);
      setLoginStep('success');
      setTimeout(() => navigate('/'), 1000);
    } catch {
      setLoginStep('idle');
      setIsSubmitting(false);
      setError("Email or password is incorrect.");
    }
  };

  const steps = [
    { icon: FileText, label: 'Documents', color: 'var(--secondary)' },
    { icon: Database, label: 'Knowledge', color: 'var(--primary)' },
    { icon: Zap, label: 'AI Core', color: 'var(--amber)' },
    { icon: ShieldCheck, label: 'Verified', color: 'var(--success)' },
  ];

  return (
    <div className="auth-layout">
      {/* ─── LEFT: BRANDING ─── */}
      <div className="auth-branding">
        {/* Ambient glows */}
        <div style={{ position:'absolute', top:'-10%', left:'-10%', width:'60%', height:'60%',
          background:'radial-gradient(ellipse, rgba(124,92,255,0.1) 0%, transparent 65%)',
          pointerEvents:'none', borderRadius:'50%' }} />
        <div style={{ position:'absolute', bottom:'5%', right:'-5%', width:'40%', height:'40%',
          background:'radial-gradient(ellipse, rgba(34,211,238,0.07) 0%, transparent 65%)',
          pointerEvents:'none', borderRadius:'50%' }} />

        <div style={{ position:'relative', zIndex:1, maxWidth:'480px' }}>
          {/* Logo */}
          <div style={{ display:'flex', alignItems:'center', gap:'0.875rem', marginBottom:'3rem' }}>
            <div style={{ width:'44px', height:'44px', borderRadius:'12px',
              background:'var(--gradient-primary)',
              display:'flex', alignItems:'center', justifyContent:'center',
              boxShadow:'0 0 24px rgba(124,92,255,0.4)' }}>
              <Database size={22} color="#fff" />
            </div>
            <span style={{ fontSize:'1.25rem', fontWeight:700, letterSpacing:'-0.02em', color:'var(--text-primary)' }}>DocAnalyser</span>
          </div>

          {/* Headline */}
          <h2 style={{ fontSize:'3rem', fontWeight:800, lineHeight:1.1, color:'var(--text-primary)', marginBottom:'1.5rem' }}>
            Your knowledge.<br />
            Made{' '}
            <span style={{
              background:'var(--gradient-primary)',
              WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent', backgroundClip:'text'
            }}>intelligent.</span>
          </h2>
          <p style={{ fontSize:'1.0625rem', color:'var(--text-muted)', lineHeight:1.65, marginBottom:'3.5rem' }}>
            Ask questions, discover insights, and get grounded, citation-verified answers from your enterprise knowledge base.
          </p>

          {/* RAG Pipeline Visualization */}
          <div style={{ display:'flex', alignItems:'center', gap:'0', flexWrap:'nowrap' }}>
            {steps.map((step, i) => {
              const Icon = step.icon;
              return (
                <React.Fragment key={step.label}>
                  <motion.div
                    initial={{ opacity:0, y:8 }}
                    animate={{ opacity:1, y:0 }}
                    transition={{ delay: 0.3 + i * 0.12 }}
                    style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:'0.5rem' }}
                  >
                    <div style={{ width:'44px', height:'44px', borderRadius:'10px',
                      background:'var(--bg-card)', border:'1px solid var(--border-subtle)',
                      display:'flex', alignItems:'center', justifyContent:'center',
                      boxShadow:`0 0 12px ${step.color}25` }}>
                      <Icon size={20} color={step.color} />
                    </div>
                    <span style={{ fontSize:'0.7rem', color:'var(--text-muted)', fontWeight:500, whiteSpace:'nowrap' }}>{step.label}</span>
                  </motion.div>
                  {i < steps.length - 1 && (
                    <motion.div
                      initial={{ scaleX:0 }} animate={{ scaleX:1 }}
                      transition={{ delay: 0.45 + i * 0.12 }}
                      style={{ flex:1, height:'1px', background:'linear-gradient(90deg, var(--border-strong), var(--border-subtle))', margin:'0 0.5rem', marginBottom:'1.5rem', minWidth:'20px' }}
                    />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>

      {/* ─── RIGHT: AUTH FORM ─── */}
      <div className="auth-form-side" style={{ background:'rgba(7,8,18,0.6)' }}>
        <AnimatePresence mode="wait">
          {loginStep === 'success' ? (
            <motion.div key="success"
              initial={{ scale:0.85, opacity:0 }}
              animate={{ scale:1, opacity:1 }}
              transition={{ type:'spring', stiffness:200 }}
              style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:'1.5rem' }}
            >
              <div style={{ position:'relative' }}>
                <motion.div
                  animate={{ scale:[1, 1.3, 1], opacity:[0.6, 0, 0.6] }}
                  transition={{ duration:1.2, repeat:Infinity }}
                  style={{ position:'absolute', inset:'-16px', borderRadius:'50%',
                    background:'radial-gradient(circle, rgba(124,92,255,0.3) 0%, transparent 70%)' }}
                />
                <div style={{ width:'72px', height:'72px', borderRadius:'50%',
                  background:'linear-gradient(135deg, rgba(124,92,255,0.2) 0%, rgba(34,211,238,0.15) 100%)',
                  border:'1px solid rgba(124,92,255,0.4)',
                  display:'flex', alignItems:'center', justifyContent:'center' }}>
                  <ShieldCheck size={36} color="var(--primary)" />
                </div>
              </div>
              <div style={{ textAlign:'center' }}>
                <h3 style={{ fontSize:'1.5rem', fontWeight:700, color:'var(--text-primary)', marginBottom:'0.5rem' }}>Identity Verified</h3>
                <p style={{ color:'var(--text-muted)' }}>Preparing your knowledge workspace...</p>
              </div>
            </motion.div>
          ) : (
            <motion.div key="form"
              initial={{ opacity:0, y:16 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0, scale:0.97 }}
              style={{ width:'100%', maxWidth:'400px' }}
            >
              {/* Form Header */}
              <div style={{ marginBottom:'2rem', textAlign:'center' }}>
                <div style={{ display:'inline-flex', alignItems:'center', justifyContent:'center',
                  width:'44px', height:'44px', borderRadius:'12px', background:'var(--gradient-primary)',
                  marginBottom:'1.25rem', boxShadow:'0 0 20px rgba(124,92,255,0.3)' }}>
                  <Database size={22} color="#fff" />
                </div>
                <h2 style={{ fontSize:'1.75rem', fontWeight:700, color:'var(--text-primary)', marginBottom:'0.375rem' }}>Welcome back</h2>
                <p style={{ color:'var(--text-muted)', fontSize:'0.9rem' }}>Sign in to your knowledge workspace.</p>
              </div>

              {/* Error */}
              <AnimatePresence>
                {error && (
                  <motion.div initial={{ opacity:0, y:-8 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}
                    style={{ padding:'0.75rem 1rem', background:'rgba(244,63,94,0.08)',
                      borderLeft:'3px solid var(--error)', borderRadius:'0 var(--radius-md) var(--radius-md) 0',
                      color:'var(--error)', marginBottom:'1.25rem', fontSize:'0.875rem' }}>
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              <form onSubmit={handleLogin} style={{ display:'flex', flexDirection:'column', gap:'1.125rem' }}>
                {/* Email */}
                <div className="input-group">
                  <label>Email address</label>
                  <input
                    type="email" placeholder="name@company.com"
                    value={email} onChange={e => setEmail(e.target.value)}
                    required className="auth-input"
                    style={{ width:'100%' }}
                  />
                </div>

                {/* Password */}
                <div className="input-group">
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                    <label>Password</label>
                    <a href="#" style={{ fontSize:'0.75rem', color:'var(--primary)' }}>Forgot password?</a>
                  </div>
                  <div style={{ position:'relative' }}>
                    <input
                      type={showPassword ? 'text' : 'password'}
                      placeholder="••••••••"
                      value={password} onChange={e => setPassword(e.target.value)}
                      required className="auth-input"
                      style={{ width:'100%', paddingRight:'2.75rem' }}
                    />
                    <button type="button" onClick={() => setShowPassword(v => !v)} tabIndex={-1}
                      style={{ position:'absolute', right:'0.75rem', top:'50%', transform:'translateY(-50%)',
                        background:'none', border:'none', cursor:'pointer', color:'var(--text-muted)',
                        display:'flex', alignItems:'center', padding:'0.25rem' }}>
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>

                {/* Remember me */}
                <div style={{ display:'flex', alignItems:'center', gap:'0.5rem' }}>
                  <input type="checkbox" id="remember" style={{ accentColor:'var(--primary)', width:'14px', height:'14px' }} />
                  <label htmlFor="remember" style={{ fontSize:'0.8125rem', color:'var(--text-muted)', cursor:'pointer' }}>
                    Remember me for 30 days
                  </label>
                </div>

                {/* Submit */}
                <button type="submit" disabled={isSubmitting} className="btn-auth" style={{ marginTop:'0.5rem' }}>
                  {loginStep === 'verifying' ? (
                    <>
                      <motion.div animate={{ rotate:360 }} transition={{ repeat:Infinity, duration:0.9, ease:'linear' }}>
                        <Zap size={16} />
                      </motion.div>
                      Signing in...
                    </>
                  ) : 'Sign In'}
                </button>
              </form>

              <div style={{ height:'1px', background:'var(--border-subtle)', margin:'1.75rem 0' }} />

              <p style={{ textAlign:'center', fontSize:'0.875rem', color:'var(--text-muted)' }}>
                Don't have an account?{' '}
                <Link to="/register" style={{ color:'var(--primary)', fontWeight:600 }}>Create account</Link>
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
