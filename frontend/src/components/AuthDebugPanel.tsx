import React from 'react';
import { useMe } from "@/context/MeContext";

export function AuthDebugPanel() {
  const { me, loading, error } = useMe();

  // Only show in dev mode
  if (import.meta.env.PROD) {
    return null;
  }

  return (
    <div className="auth-debug-panel" style={{
      position: 'fixed',
      bottom: '1rem',
      right: '1rem',
      maxWidth: '400px',
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      color: '#fff',
      padding: '1rem',
      borderRadius: '8px',
      fontSize: '12px',
      fontFamily: 'monospace',
      zIndex: 9999,
      border: '1px solid rgba(255, 255, 255, 0.2)',
    }}>
      <div style={{ marginBottom: '0.5rem', fontWeight: 'bold', color: '#2AE5B8' }}>
        Auth Debug (Dev Only)
      </div>
      {loading && <div>Loading...</div>}
      {error && <div style={{ color: '#ff6b6b' }}>Error: {error}</div>}
      {me && (
        <pre style={{
          margin: 0,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontSize: '11px',
          lineHeight: '1.4',
        }}>
          {JSON.stringify(me, null, 2)}
        </pre>
      )}
      {!loading && !error && !me && (
        <div style={{ color: '#ffa500' }}>Not signed in</div>
      )}
    </div>
  );
}

