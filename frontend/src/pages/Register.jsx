import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { FileText, CheckCircle2, Eye, EyeOff } from 'lucide-react';

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
    profileType: 'Student',
    degree: '',
    branch: '',
    studyYear: ''
  });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleRegister = async (e) => {
    e.preventDefault();
    if (formData.password !== formData.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setError('');
    setIsSubmitting(true);
    try {
      await register(formData);
      setSuccess(true);
      setTimeout(() => navigate('/login'), 1800);
    } catch (err) {
      setError(err.message || "Registration failed.");
      setIsSubmitting(false);
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
            Join the future of{' '}
            <span style={{ color: 'var(--ac)' }}>
              document intelligence.
            </span>
          </h2>
          <p style={{ fontSize: '14px', color: 'var(--t2)', lineHeight: 1.6 }}>
            Create your account and start extracting grounded, verified answers from your data instantly.
          </p>

          <div style={{ marginTop: '40px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {[
              { text: 'Hybrid BM25 + Dense Retrieval' },
              { text: 'NLI Citation Verification' },
              { text: 'Reciprocal Rank Fusion' },
            ].map(item => (
              <div key={item.text} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ color: 'var(--ac)', fontSize: '12px' }}>✦</span>
                <span style={{ fontSize: '13.5px', color: 'var(--t2)' }}>{item.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* RIGHT FORM */}
      <div className="auth-form-side">
        <AnimatePresence mode="wait">
          {success ? (
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
                  Account Created!
                </h3>
                <p style={{ color: 'var(--t2)', fontSize: '13.5px' }}>
                  Redirecting to login...
                </p>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="form"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              style={{ width: '100%', maxWidth: '440px' }}
            >
              <div style={{ marginBottom: '24px' }}>
                <h2 className="font-fraunces" style={{ fontSize: '24px', fontWeight: 600, color: 'var(--tx)', marginBottom: '6px' }}>
                  Create your account
                </h2>
                <p style={{ color: 'var(--t2)', fontSize: '13px' }}>
                  Fill in your details below to get started.
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

              <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div className="input-group">
                  <label>Full Name</label>
                  <input
                    type="text"
                    name="name"
                    placeholder="CHADARAM BHANU VENKATA MANIKANTA"
                    value={formData.name}
                    onChange={handleChange}
                    className="auth-input"
                    required
                  />
                </div>

                <div className="input-group">
                  <label>Email address</label>
                  <input
                    type="email"
                    name="email"
                    placeholder="chbhanuvmanikanta@gmail.com"
                    value={formData.email}
                    onChange={handleChange}
                    className="auth-input"
                    required
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="input-group">
                    <label>Password</label>
                    <div style={{ position: 'relative' }}>
                      <input
                        type={showPassword ? 'text' : 'password'}
                        name="password"
                        placeholder="••••••••"
                        value={formData.password}
                        onChange={handleChange}
                        className="auth-input"
                        style={{ paddingRight: '36px' }}
                        required
                        minLength={6}
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

                  <div className="input-group">
                    <label>Confirm Password</label>
                    <div style={{ position: 'relative' }}>
                      <input
                        type={showConfirmPassword ? 'text' : 'password'}
                        name="confirmPassword"
                        placeholder="••••••••"
                        value={formData.confirmPassword}
                        onChange={handleChange}
                        className="auth-input"
                        style={{ paddingRight: '36px' }}
                        required
                        minLength={6}
                      />
                      <button
                        type="button"
                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
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
                        {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Profile Selector */}
                <div className="input-group">
                  <label>What best describes you?</label>
                  <select
                    name="profileType"
                    value={formData.profileType}
                    onChange={handleChange}
                    className="auth-input"
                    style={{ cursor: 'pointer' }}
                  >
                    <option value="Student">Student</option>
                    <option value="Graduate">Graduate</option>
                    <option value="Working Professional">Working Professional</option>
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="btn-auth"
                  style={{ marginTop: '8px' }}
                >
                  {isSubmitting ? 'Creating account...' : 'Create Account'}
                </button>
              </form>

              <div style={{ height: '1px', backgroundColor: 'var(--bd)', margin: '24px 0' }} />

              <p style={{ textAlign: 'center', fontSize: '13px', color: 'var(--t2)' }}>
                Already have an account?{' '}
                <Link to="/login" style={{ color: 'var(--ac)', fontWeight: 600, textDecoration: 'none' }}>
                  Sign in
                </Link>
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
