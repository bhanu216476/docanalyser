import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Database, CheckCircle, Eye, EyeOff } from 'lucide-react';

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    name:'', email:'', password:'', confirmPassword:'',
    profileType:'Student', degree:'', branch:'', studyYear:''
  });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleRegister = async (e) => {
    e.preventDefault();
    if (formData.password !== formData.confirmPassword) { setError("Passwords do not match."); return; }
    setError(''); setIsSubmitting(true);
    try {
      await register(formData);
      setSuccess(true);
      setTimeout(() => navigate('/login'), 2000);
    } catch (err) {
      setError(err.message || "Registration failed.");
      setIsSubmitting(false);
    }
  };

  const inputStyle = {
    width:'100%', padding:'0.75rem 1rem', background:'rgba(11,14,24,0.9)',
    border:'1px solid var(--border-subtle)', borderRadius:'var(--radius-md)',
    color:'var(--text-primary)', outline:'none', fontSize:'0.875rem', fontFamily:'inherit'
  };

  return (
    <div className="auth-layout">
      {/* ─── LEFT BRANDING ─── */}
      <div className="auth-branding">
        <div style={{ position:'absolute', top:'-5%', left:'-10%', width:'55%', height:'55%',
          background:'radial-gradient(ellipse, rgba(124,92,255,0.09) 0%, transparent 65%)',
          pointerEvents:'none', borderRadius:'50%' }} />
        <div style={{ position:'absolute', bottom:'10%', right:'-5%', width:'40%', height:'40%',
          background:'radial-gradient(ellipse, rgba(34,211,238,0.06) 0%, transparent 65%)',
          pointerEvents:'none', borderRadius:'50%' }} />

        <div style={{ position:'relative', zIndex:1, maxWidth:'460px' }}>
          <div style={{ display:'flex', alignItems:'center', gap:'0.875rem', marginBottom:'3rem' }}>
            <div style={{ width:'44px', height:'44px', borderRadius:'12px',
              background:'var(--gradient-primary)', display:'flex', alignItems:'center', justifyContent:'center',
              boxShadow:'0 0 24px rgba(124,92,255,0.4)' }}>
              <Database size={22} color="#fff" />
            </div>
            <span style={{ fontSize:'1.25rem', fontWeight:700, letterSpacing:'-0.02em', color:'var(--text-primary)' }}>DocAnalyser</span>
          </div>

          <h2 style={{ fontSize:'2.75rem', fontWeight:800, lineHeight:1.15, color:'var(--text-primary)', marginBottom:'1.25rem' }}>
            Join the future of{' '}
            <span style={{ background:'linear-gradient(135deg, var(--secondary) 0%, var(--primary) 100%)',
              WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent', backgroundClip:'text' }}>
              document intelligence.
            </span>
          </h2>
          <p style={{ fontSize:'1rem', color:'var(--text-muted)', lineHeight:1.65 }}>
            Create your account and start extracting grounded, verified answers from your data instantly.
          </p>

          <div style={{ marginTop:'3rem', display:'flex', flexDirection:'column', gap:'1rem' }}>
            {[
              { emoji:'✦', text:'Hybrid BM25 + Dense Retrieval' },
              { emoji:'✦', text:'NLI Citation Verification' },
              { emoji:'✦', text:'Reciprocal Rank Fusion' },
            ].map(item => (
              <div key={item.text} style={{ display:'flex', alignItems:'center', gap:'0.75rem' }}>
                <span style={{ color:'var(--primary)', fontSize:'0.75rem' }}>{item.emoji}</span>
                <span style={{ fontSize:'0.875rem', color:'var(--text-muted)' }}>{item.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ─── RIGHT: FORM ─── */}
      <div className="auth-form-side" style={{ background:'rgba(7,8,18,0.6)', overflowY:'auto', alignItems:'center', justifyContent:'flex-start', paddingTop:'3rem', paddingBottom:'3rem' }}>
        <AnimatePresence mode="wait">
          {success ? (
            <motion.div key="success"
              initial={{ scale:0.9, opacity:0 }} animate={{ scale:1, opacity:1 }}
              transition={{ type:'spring', stiffness:200 }}
              style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:'1.5rem', marginTop:'8vh' }}
            >
              <div style={{ position:'relative' }}>
                <motion.div animate={{ scale:[1, 1.4, 1], opacity:[0.5, 0, 0.5] }}
                  transition={{ duration:1.4, repeat:Infinity }}
                  style={{ position:'absolute', inset:'-16px', borderRadius:'50%',
                    background:'radial-gradient(circle, rgba(34,197,94,0.25) 0%, transparent 70%)' }} />
                <div style={{ width:'72px', height:'72px', borderRadius:'50%',
                  background:'var(--success-light)', border:'1px solid rgba(34,197,94,0.3)',
                  display:'flex', alignItems:'center', justifyContent:'center' }}>
                  <CheckCircle size={38} color="var(--success)" />
                </div>
              </div>
              <div style={{ textAlign:'center' }}>
                <h3 style={{ fontSize:'1.5rem', fontWeight:700, color:'var(--text-primary)', marginBottom:'0.5rem' }}>Account Created!</h3>
                <p style={{ color:'var(--text-muted)' }}>Redirecting to login...</p>
              </div>
            </motion.div>
          ) : (
            <motion.div key="form"
              initial={{ opacity:0, y:16 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0, scale:0.97 }}
              style={{ width:'100%', maxWidth:'460px' }}
            >
              <div style={{ marginBottom:'2rem' }}>
                <h2 style={{ fontSize:'1.75rem', fontWeight:700, color:'var(--text-primary)', marginBottom:'0.375rem' }}>Create your account</h2>
                <p style={{ color:'var(--text-muted)', fontSize:'0.9rem' }}>Fill in your details below to get started.</p>
              </div>

              {error && (
                <div style={{ padding:'0.75rem 1rem', background:'rgba(244,63,94,0.08)',
                  borderLeft:'3px solid var(--error)', borderRadius:'0 var(--radius-md) var(--radius-md) 0',
                  color:'var(--error)', marginBottom:'1.25rem', fontSize:'0.875rem' }}>
                  {error}
                </div>
              )}

              <form onSubmit={handleRegister} style={{ display:'flex', flexDirection:'column', gap:'1.125rem' }}>
                <div className="input-group">
                  <label>Full Name</label>
                  <input type="text" name="name" placeholder="John Doe" value={formData.name} onChange={handleChange} required style={inputStyle} />
                </div>

                <div className="input-group">
                  <label>Email address</label>
                  <input type="email" name="email" placeholder="john@example.com" value={formData.email} onChange={handleChange} required style={inputStyle} />
                </div>

                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1rem' }}>
                  <div className="input-group">
                    <label>Password</label>
                    <div style={{ position:'relative' }}>
                      <input type={showPassword ? 'text' : 'password'} name="password" placeholder="••••••••"
                        value={formData.password} onChange={handleChange} required minLength="6"
                        style={{ ...inputStyle, paddingRight:'2.75rem' }} />
                      <button type="button" onClick={() => setShowPassword(v => !v)} tabIndex={-1}
                        style={{ position:'absolute', right:'0.75rem', top:'50%', transform:'translateY(-50%)',
                          background:'none', border:'none', cursor:'pointer', color:'var(--text-muted)', display:'flex', alignItems:'center' }}>
                        {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                  <div className="input-group">
                    <label>Confirm Password</label>
                    <div style={{ position:'relative' }}>
                      <input type={showConfirmPassword ? 'text' : 'password'} name="confirmPassword" placeholder="••••••••"
                        value={formData.confirmPassword} onChange={handleChange} required minLength="6"
                        style={{ ...inputStyle, paddingRight:'2.75rem' }} />
                      <button type="button" onClick={() => setShowConfirmPassword(v => !v)} tabIndex={-1}
                        style={{ position:'absolute', right:'0.75rem', top:'50%', transform:'translateY(-50%)',
                          background:'none', border:'none', cursor:'pointer', color:'var(--text-muted)', display:'flex', alignItems:'center' }}>
                        {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Divider */}
                <div style={{ display:'flex', alignItems:'center', gap:'1rem', margin:'0.25rem 0' }}>
                  <div style={{ flex:1, height:'1px', background:'var(--border-subtle)' }} />
                  <span style={{ fontSize:'0.75rem', color:'var(--text-muted)', whiteSpace:'nowrap' }}>Profile information</span>
                  <div style={{ flex:1, height:'1px', background:'var(--border-subtle)' }} />
                </div>

                <div className="input-group">
                  <label>What best describes you?</label>
                  <select name="profileType" value={formData.profileType} onChange={handleChange}
                    style={{ ...inputStyle, cursor:'pointer' }}>
                    <option value="Student">Student</option>
                    <option value="Graduate">Graduate</option>
                    <option value="Working Professional">Working Professional</option>
                  </select>
                </div>

                <AnimatePresence>
                  {formData.profileType === 'Student' && (
                    <motion.div initial={{ height:0, opacity:0 }} animate={{ height:'auto', opacity:1 }}
                      exit={{ height:0, opacity:0 }} style={{ overflow:'hidden' }}>
                      <div style={{ display:'flex', flexDirection:'column', gap:'1rem', paddingTop:'0.25rem' }}>
                        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1rem' }}>
                          <div className="input-group">
                            <label>Degree (Optional)</label>
                            <input type="text" name="degree" placeholder="B.Tech" value={formData.degree} onChange={handleChange} style={inputStyle} />
                          </div>
                          <div className="input-group">
                            <label>Branch (Optional)</label>
                            <input type="text" name="branch" placeholder="CSIT" value={formData.branch} onChange={handleChange} style={inputStyle} />
                          </div>
                        </div>
                        <div className="input-group">
                          <label>Year of Study (Optional)</label>
                          <select name="studyYear" value={formData.studyYear} onChange={handleChange} style={{ ...inputStyle, cursor:'pointer' }}>
                            <option value="">Select Year...</option>
                            <option value="1st Year">1st Year</option>
                            <option value="2nd Year">2nd Year</option>
                            <option value="3rd Year">3rd Year</option>
                            <option value="4th Year">4th Year</option>
                          </select>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <button type="submit" disabled={isSubmitting} className="btn-auth" style={{ marginTop:'0.5rem' }}>
                  {isSubmitting ? 'Creating account...' : 'Create Account'}
                </button>
              </form>

              <div style={{ height:'1px', background:'var(--border-subtle)', margin:'1.75rem 0' }} />
              <p style={{ textAlign:'center', fontSize:'0.875rem', color:'var(--text-muted)' }}>
                Already have an account?{' '}
                <Link to="/login" style={{ color:'var(--primary)', fontWeight:600 }}>Sign in</Link>
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
