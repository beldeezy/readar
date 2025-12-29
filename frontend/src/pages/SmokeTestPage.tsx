import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

function clearReadarStorage() {
  const keysToRemove: string[] = [];
  
  // Find all keys starting with "readar_" or "sb-"
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && (key.startsWith('readar_') || key.startsWith('sb-'))) {
      keysToRemove.push(key);
    }
  }
  
  // Remove them
  keysToRemove.forEach(key => localStorage.removeItem(key));
  
  return keysToRemove.length;
}

export default function SmokeTestPage() {
  const navigate = useNavigate();
  const [clearedCount, setClearedCount] = useState<number>(0);
  
  useEffect(() => {
    const count = clearReadarStorage();
    setClearedCount(count);
  }, []);
  
  const handleClearAgain = () => {
    const count = clearReadarStorage();
    setClearedCount(count);
  };
  
  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      <h1>Smoke Test</h1>
      
      <div style={{ marginBottom: 24 }}>
        <h2>Storage</h2>
        <p>Cleared {clearedCount} localStorage key(s) matching "readar_*" or "sb-*"</p>
        <button 
          onClick={handleClearAgain}
          style={{
            padding: '8px 16px',
            marginTop: 8,
            cursor: 'pointer'
          }}
        >
          Clear Again
        </button>
      </div>
      
      <div style={{ marginBottom: 24 }}>
        <h2>Environment</h2>
        <pre style={{ 
          background: '#f5f5f5', 
          padding: 16, 
          borderRadius: 4,
          overflow: 'auto'
        }}>
          {JSON.stringify({
            origin: window.location.origin,
            pathname: window.location.pathname,
            VITE_SITE_URL: import.meta.env.VITE_SITE_URL || 'undefined',
            VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL || 'undefined',
            MODE: import.meta.env.MODE,
          }, null, 2)}
        </pre>
      </div>
      
      <div style={{ marginBottom: 24 }}>
        <h2>Actions</h2>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <button
            onClick={() => navigate('/')}
            style={{
              padding: '12px 24px',
              cursor: 'pointer',
              fontSize: 16
            }}
          >
            Start Smoke Test
          </button>
          <button
            onClick={() => navigate('/onboarding')}
            style={{
              padding: '12px 24px',
              cursor: 'pointer',
              fontSize: 16
            }}
          >
            Go to Onboarding
          </button>
        </div>
      </div>
      
      <div style={{ 
        marginTop: 32, 
        padding: 16, 
        background: '#fff3cd', 
        borderRadius: 4,
        border: '1px solid #ffc107'
      }}>
        <p style={{ margin: 0 }}>
          <strong>Note:</strong> If auth is acting weird, clear and hard refresh.
        </p>
      </div>
    </div>
  );
}

