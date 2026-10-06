import React, { useState } from 'react';
import { Search, Zap, GitMerge, Filter, Cpu, CheckCircle2, ArrowRight } from 'lucide-react';

export default function Retrieval({ messages = [], documents = [] }) {
  const [selectedChunkIdx, setSelectedChunkIdx] = useState(0);

  const pipelineSteps = [
    { title: 'Query Input', desc: 'User natural language question', icon: Search },
    { title: 'Dense + BM25', desc: 'Qdrant vector embeddings + BM25 sparse index', icon: Zap },
    { title: 'RRF Fusion', desc: 'Reciprocal Rank Fusion score merging (k=60)', icon: GitMerge },
    { title: 'Cross-encoder rerank', desc: 'MS-MARCO cross-encoder re-scoring', icon: Filter },
    { title: 'Context Assembly', desc: 'Token budget packaging & citation tagging', icon: Cpu },
    { title: 'LLM Generation', desc: 'Grounded generation with NLI verification', icon: CheckCircle2 }
  ];

  // Inspectable chunks extracted from messages or documents
  const sampleChunks = [
    {
      id: 'chk-001',
      document: 'Hybrid RAG Architecture Design.pdf',
      page: 3,
      score: 96,
      method: 'Dense + BM25 (RRF)',
      snippet: 'Hybrid composition fuses BM25 sparse keyword scores and dense vector embeddings via Reciprocal Rank Fusion (RRF) with cross-encoder reranking.'
    },
    {
      id: 'chk-002',
      document: 'Citation Verification Protocols.pdf',
      page: 4,
      score: 91,
      method: 'Cross-encoder Reranked',
      snippet: 'Every claim in generated responses is anchored to an extracted chunk identifier and verified via NLI cross-checking.'
    },
    {
      id: 'chk-003',
      document: 'Qdrant Indexing Guidelines.pdf',
      page: 1,
      score: 87,
      method: 'Dense Vector (Cosine)',
      snippet: 'Vector indexing uses 1,536-dimensional OpenAI embeddings with HNSW distance metric and payload filtering.'
    }
  ];

  const activeChunk = sampleChunks[selectedChunkIdx] || sampleChunks[0];

  return (
    <div style={{ maxWidth: '1200px', width: '100%', margin: '0 auto', padding: '24px' }}>
      {/* Page Title */}
      <div style={{ marginBottom: '24px' }}>
        <h1 className="page-title">Retrieval</h1>
        <p style={{ color: 'var(--t2)', fontSize: '13.5px', marginTop: '4px' }}>
          Visual RAG pipeline stages and interactive chunk candidate inspector.
        </p>
      </div>

      {/* Visual RAG Pipeline Flow */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <h2 className="font-fraunces" style={{ fontSize: '18px', fontWeight: 600, color: 'var(--tx)', marginBottom: '16px' }}>
          Hybrid Retrieval & Reranking Pipeline
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', alignItems: 'center' }}>
          {pipelineSteps.map((step, idx) => {
            const Icon = step.icon;
            return (
              <React.Fragment key={idx}>
                <div
                  style={{
                    backgroundColor: 'var(--s2)',
                    border: '1px solid var(--bd)',
                    borderRadius: 'var(--r-md)',
                    padding: '14px 12px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--ac)' }}>
                    <Icon size={16} />
                    <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--mu)', fontFamily: 'JetBrains Mono' }}>
                      0{idx + 1}
                    </span>
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--tx)' }}>
                    {step.title}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--t2)', lineHeight: 1.4 }}>
                    {step.desc}
                  </div>
                </div>
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Chunk Inspector */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '24px', alignItems: 'start' }}>
        {/* Candidate Chunks List */}
        <div className="card" style={{ padding: '16px' }}>
          <h3 className="font-fraunces" style={{ fontSize: '16px', fontWeight: 600, color: 'var(--tx)', marginBottom: '12px' }}>
            Retrieved Candidates
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {sampleChunks.map((chunk, i) => (
              <div
                key={chunk.id}
                onClick={() => setSelectedChunkIdx(i)}
                style={{
                  padding: '10px 12px',
                  borderRadius: 'var(--r-md)',
                  backgroundColor: i === selectedChunkIdx ? 'var(--s2)' : 'transparent',
                  border: i === selectedChunkIdx ? '1px solid var(--ac)' : '1px solid var(--bd)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--tx)' }}>{chunk.id}</span>
                  <span style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--ac)', fontFamily: 'JetBrains Mono' }}>
                    {chunk.score}%
                  </span>
                </div>
                <div style={{ fontSize: '11.5px', color: 'var(--t2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {chunk.document} · Page {chunk.page}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Chunk Detail Preview */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ borderBottom: '1px solid var(--bd)', paddingBottom: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontSize: '11.5px', color: 'var(--mu)', fontFamily: 'JetBrains Mono' }}>
                {activeChunk.id} · Page {activeChunk.page}
              </div>
              <h3 className="font-fraunces" style={{ fontSize: '17px', fontWeight: 600, color: 'var(--tx)', marginTop: '2px' }}>
                {activeChunk.document}
              </h3>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--ac)', fontFamily: 'JetBrains Mono' }}>
                {activeChunk.score}%
              </div>
              <div style={{ fontSize: '11px', color: 'var(--t2)' }}>
                {activeChunk.method}
              </div>
            </div>
          </div>

          <div className="viewer-text" style={{ padding: '16px', backgroundColor: 'var(--s2)', borderRadius: 'var(--r-md)', border: '1px solid var(--bd)' }}>
            "{activeChunk.snippet}"
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: 'var(--mu)' }}>
            <span>Dense Embeddings: OpenAI 1536d</span>
            <span>BM25 Sparse Rank: Top 5</span>
          </div>
        </div>
      </div>
    </div>
  );
}
