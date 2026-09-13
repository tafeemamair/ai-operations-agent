'use client';

import React, { useEffect, useState } from 'react';
import { getHealth } from '../lib/api';
import { HealthResponse } from '../lib/types';

export default function Header() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);

  const checkHealth = async () => {
    try {
      const data = await getHealth();
      setHealth(data);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
    // Simple polling interval: every 15 seconds
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="header">
      <div className="header-brand">
        <div className="logo-badge">OPS</div>
        <div>
          <h1 className="header-title">AI Operations Console</h1>
          <p className="header-subtitle">Deterministic Orchestration, Human Gates & Auditability</p>
        </div>
      </div>

      <div className="health-badge" data-testid="health-badge">
        {loading && <span className="mono" style={{ color: 'var(--text-muted)' }}>Checking API...</span>}
        {!loading && error && (
          <>
            <span className="health-dot error" />
            <span className="mono" style={{ color: 'var(--status-failed)' }}>API Offline</span>
          </>
        )}
        {!loading && !error && health && (
          <>
            <span className="health-dot ok" />
            <span className="mono" style={{ color: 'var(--status-completed)' }}>
              API Online v{health.version}
            </span>
          </>
        )}
      </div>
    </header>
  );
}
