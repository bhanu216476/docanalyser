import React, { useState, useEffect } from 'react';
import RobotMascot from './RobotMascot';

/**
 * Animated Document Upload Scanner with Maddy Mascot.
 * Displays when a document is being uploaded and indexed to keep the user engaged.
 */
export default function DocumentUploadScanner({ fileName = 'Document' }) {
  const [stepIdx, setStepIdx] = useState(0);

  const steps = [
    "Reading file data & structure...",
    "Extracting semantic text chunks...",
    "Generating neural vector embeddings...",
    "Indexing in Qdrant & BM25 knowledge base..."
  ];

  useEffect(() => {
    const timer = setInterval(() => {
      setStepIdx(prev => (prev + 1) % steps.length);
    }, 1500);
    return () => clearInterval(timer);
  }, [steps.length]);

  return (
    <div className="maddy-upload-scanner-box">
      {/* Floating Maddy Mascot in Scanning Mode */}
      <RobotMascot size="md" mode="scanning" />

      {/* Holographic Document Container with Laser Scan */}
      <div
        style={{
          width: '100%',
          maxWidth: '220px',
          height: '64px',
          backgroundColor: 'var(--s1)',
          border: '1px solid var(--bd)',
          borderRadius: '8px',
          margin: '10px 0 8px 0',
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          gap: '6px',
          padding: '8px 14px',
          boxShadow: 'inset 0 0 12px rgba(56, 189, 248, 0.1)'
        }}
      >
        {/* Animated Laser Sweep Line */}
        <div className="maddy-scan-laser" />

        {/* Faux Document Text Lines */}
        <div style={{ height: '5px', width: '85%', background: 'var(--bd)', borderRadius: '3px', opacity: 0.7 }} />
        <div style={{ height: '5px', width: '65%', background: 'var(--ac)', borderRadius: '3px', opacity: 0.8 }} />
        <div style={{ height: '5px', width: '90%', background: 'var(--bd)', borderRadius: '3px', opacity: 0.6 }} />
      </div>

      {/* Current Step Status */}
      <div style={{ fontSize: '11.5px', fontWeight: 600, color: 'var(--tx)', textAlign: 'center', marginTop: '2px' }}>
        {steps[stepIdx]}
      </div>
      <div style={{ fontSize: '10.5px', color: 'var(--mu)', textAlign: 'center', marginTop: '2px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        Indexing: {fileName}
      </div>
    </div>
  );
}
