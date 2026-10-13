import React from 'react';
import { CheckCircle2, AlertCircle } from 'lucide-react';

export default function VerifiedPill({ verification }) {
  if (!verification) return null;

  const isVerified = verification.verified === true || verification.status === 'VERIFIED';
  const isPartial = verification.status === 'PARTIAL' || verification.partially_verified === true;
  const verifiedCount = verification.verified_sources || verification.verifiedCount || 2;
  const totalCount = verification.total_sources || verification.totalCount || 2;

  if (isVerified) {
    return (
      <div className="verified-pill">
        <CheckCircle2 size={12} />
        <span>✓ Verified · {verifiedCount} of {totalCount} sources</span>
      </div>
    );
  }

  if (isPartial) {
    return (
      <div className="verified-pill partial">
        <AlertCircle size={12} />
        <span>Partially verified · {verifiedCount} of {totalCount} sources</span>
      </div>
    );
  }

  return null;
}
