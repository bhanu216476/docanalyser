import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './context/AuthContext';

import TopBar from './components/TopBar';
import ProtectedRoute from './components/ProtectedRoute';
import RoleGuard from './components/RoleGuard';

import Login from './pages/Login';
import Register from './pages/Register';
import AskAI from './pages/AskAI';
import Documents from './pages/Documents';
import KnowledgeBase from './pages/KnowledgeBase';
import Retrieval from './pages/Retrieval';
import Verification from './pages/Verification';
import System from './pages/System';
import AdminDashboard from './pages/AdminDashboard';
import AdminUsers from './pages/AdminUsers';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080';
const RAG_BASE = import.meta.env.VITE_RAG_URL || 'http://localhost:8000';

function AppShell() {
  const { user } = useAuth();
  const location = useLocation();

  // Real Health States
  const [backendHealth, setBackendHealth] = useState('checking');
  const [ragHealth, setRagHealth] = useState('checking');

  // Documents state
  const [documents, setDocuments] = useState([
    {
      id: 'doc-001',
      title: 'Hybrid RAG Architecture Design',
      fileName: 'hybrid_rag_architecture.pdf',
      category: 'Architecture',
      status: 'PROCESSED',
      chunks: 24,
      uploadedAt: '2026-09-26 18:30'
    },
    {
      id: 'doc-002',
      title: 'Citation Verification & Faithfulness Protocols',
      fileName: 'citation_verification_protocols.pdf',
      category: 'Research',
      status: 'PROCESSED',
      chunks: 18,
      uploadedAt: '2026-09-26 19:15'
    }
  ]);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadCategory, setUploadCategory] = useState('Engineering');
  const [uploadContent, setUploadContent] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState(null);

  // Chat state
  const [messages, setMessages] = useState([
    {
      id: 'msg-welcome',
      role: 'assistant',
      text: 'Welcome to DocAnalyser! Ask any question grounded in your ingested enterprise documents, or upload new files to expand the knowledge base.',
      meta: null
    }
  ]);
  const [queryInput, setQueryInput] = useState('');
  const [isQuerying, setIsQuerying] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState('all');

  // Periodic real backend health polling
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/health`);
        setBackendHealth(res.ok ? 'healthy' : 'offline');
      } catch {
        setBackendHealth('offline');
      }
      try {
        const res = await fetch(`${RAG_BASE}/health`);
        setRagHealth(res.ok ? 'healthy' : 'offline');
      } catch {
        setRagHealth('offline');
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  // Fetch real document list from Spring API if authenticated
  useEffect(() => {
    const fetchDocuments = async () => {
      const token = localStorage.getItem('token');
      if (!token) return;
      try {
        const res = await fetch(`${API_BASE}/api/documents`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            setDocuments(data.map(doc => ({
              id: doc.id || `doc-${doc.contentHash?.substring(0, 6)}`,
              title: doc.fileName || doc.title || 'Untitled Document',
              fileName: doc.fileName || 'document.pdf',
              category: doc.source || 'Ingested',
              status: doc.status || 'PROCESSED',
              chunks: doc.chunkCount || doc.chunks || 12,
              uploadedAt: doc.createdAt ? new Date(doc.createdAt).toISOString().replace('T', ' ').slice(0, 16) : 'Recently'
            })));
          }
        }
      } catch (err) {
        // Keep initial fallback documents if API not reachable
      }
    };
    fetchDocuments();
  }, []);

  const handleUpload = async (e) => {
    e?.preventDefault();
    if (!uploadTitle.trim() && !uploadContent.trim()) return;
    setIsUploading(true);
    setUploadMessage(null);

    try {
      const token = localStorage.getItem('token');
      const newDocId = `doc-${Date.now().toString().slice(-4)}`;
      const fileName = uploadTitle.endsWith('.pdf') || uploadTitle.endsWith('.txt') ? uploadTitle : `${uploadTitle || 'Document'}.pdf`;

      // Try Spring API ingestion endpoint first
      let apiSuccess = false;
      let apiData = null;
      try {
        const res = await fetch(`${API_BASE}/api/internal/documents/ingest`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Internal-Token': 'docanalyser-n8n-internal-token-secret',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
          },
          body: JSON.stringify({
            documentId: newDocId,
            fileName: fileName,
            source: uploadCategory,
            fileUrl: uploadContent
          })
        });
        if (res.ok || res.status === 202) {
          apiSuccess = true;
          apiData = await res.json();
        } else {
          let errorData = {};
          try {
            errorData = await res.json();
          } catch (jsonErr) {}
          throw new Error(errorData.error || errorData.message || `Ingestion failed (Status: ${res.status})`);
        }
      } catch (e) {
        throw e;
      }

      // Add to document state using real API response
      const finalStatus = apiData?.status === 'INDEXED' ? 'PROCESSED' : (apiData?.status || 'PROCESSING');
      const realDocId = apiData?.documentId || newDocId;
      
      const newDoc = {
        id: realDocId,
        title: uploadTitle || fileName,
        fileName: fileName,
        category: uploadCategory,
        status: finalStatus,
        chunks: apiData?.details?.chunk_count || Math.max(1, Math.ceil((uploadContent.length || 500) / 250)),
        uploadedAt: new Date().toISOString().replace('T', ' ').slice(0, 16)
      };

      setDocuments(prev => [newDoc, ...prev]);
      setUploadTitle('');
      setUploadContent('');
      setUploadMessage({ type: 'success', text: `Document "${newDoc.title}" successfully ingested and indexed!` });
    } catch (err) {
      setUploadMessage({ type: 'error', text: 'Ingestion failed: ' + err.message });
    } finally {
      setIsUploading(false);
    }
  };

  const handleSendQuery = async (e) => {
    e?.preventDefault();
    if (!queryInput.trim() || isQuerying) return;

    const userText = queryInput.trim();
    setQueryInput('');
    setMessages(prev => [...prev, { id: `user-${Date.now()}`, role: 'user', text: userText }]);
    setIsQuerying(true);

    try {
      const token = localStorage.getItem('token');
      let ragResponse = null;

      // Try RAG endpoint
      try {
        const payload = { 
          query: userText, 
          top_k: 5 
        };
        if (selectedDocId !== 'all') {
          payload.filters = { document_id: selectedDocId };
        }

        const res = await fetch(`${RAG_BASE}/api/v1/rag/query`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
          },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          ragResponse = await res.json();
        } else {
          // Fallback legacy endpoint check
          const fallbackRes = await fetch(`${RAG_BASE}/rag/query`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            },
            body: JSON.stringify({ query: userText, top_k: 5 })
          });
          if (fallbackRes.ok) ragResponse = await fallbackRes.json();
        }
      } catch (e) {}

      if (ragResponse && ragResponse.answer) {
        setMessages(prev => [...prev, {
          id: `ai-${Date.now()}`,
          role: 'assistant',
          text: ragResponse.answer,
          meta: {
            confidence: ragResponse.confidence?.score || ragResponse.confidence || 0,
            citations: ragResponse.citations || [],
            verification: ragResponse.verification || null,
            latency: ragResponse.latency_breakdown_ms || {},
            metadata: ragResponse.metadata || {}
          }
        }]);
      } else {
        // Safe fallback if no context or answer is returned
        setMessages(prev => [...prev, {
          id: `ai-${Date.now()}`,
          role: 'assistant',
          text: `I couldn't find enough information in the uploaded documents to answer this question.`,
          meta: null
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        id: `ai-err-${Date.now()}`,
        role: 'assistant',
        text: 'Error contacting RAG backend: ' + err.message,
        meta: null
      }]);
    } finally {
      setIsQuerying(false);
    }
  };

  return (
    <div className="app-container">
      <TopBar
        backendHealth={backendHealth}
        ragHealth={ragHealth}
        documents={documents}
      />
      <main className="main-content">
        <div className="page-content">
          <Routes>
            <Route
              path="/"
              element={<Navigate to="/ask-ai" replace />}
            />
            <Route
              path="/ask-ai"
              element={
                <AskAI
                  messages={messages}
                  queryInput={queryInput}
                  setQueryInput={setQueryInput}
                  isQuerying={isQuerying}
                  handleSendQuery={handleSendQuery}
                  documents={documents}
                  selectedDocId={selectedDocId}
                  setSelectedDocId={setSelectedDocId}
                />
              }
            />
            <Route
              path="/documents"
              element={
                <Documents
                  documents={documents}
                  setDocuments={setDocuments}
                  handleUpload={handleUpload}
                  isUploading={isUploading}
                  uploadMessage={uploadMessage}
                  uploadTitle={uploadTitle}
                  setUploadTitle={setUploadTitle}
                  uploadCategory={uploadCategory}
                  setUploadCategory={setUploadCategory}
                  uploadContent={uploadContent}
                  setUploadContent={setUploadContent}
                />
              }
            />
            <Route
              path="/knowledge"
              element={<KnowledgeBase documents={documents} />}
            />
            <Route
              path="/retrieval"
              element={<Retrieval messages={messages} documents={documents} />}
            />
            <Route
              path="/verification"
              element={<Verification messages={messages} documents={documents} />}
            />
            <Route
              path="/system"
              element={<System backendHealth={backendHealth} ragHealth={ragHealth} />}
            />

            {/* Admin-only routes */}
            <Route element={<RoleGuard allowedRoles={['ADMIN']} />}>
              <Route path="/admin" element={<AdminDashboard />} />
              <Route path="/admin/users" element={<AdminUsers />} />
            </Route>

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/ask-ai" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Protected application shell */}
      <Route element={<ProtectedRoute />}>
        <Route path="/*" element={<AppShell />} />
      </Route>
    </Routes>
  );
}
