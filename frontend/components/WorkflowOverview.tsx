'use client';

import React, { useState } from 'react';
import { WorkflowState, WorkflowStatus } from '../lib/types';
import { getWorkflow } from '../lib/api';

interface WorkflowOverviewProps {
  workflow: WorkflowState;
  onWorkflowLoaded: (workflow: WorkflowState) => void;
  onRefresh: () => void;
  isRefreshing?: boolean;
}

export function getWorkflowStatusBadgeClass(status: WorkflowStatus): string {
  switch (status) {
    case 'CREATED':
    case 'PLANNING':
      return 'badge-pending';
    case 'EXECUTING':
      return 'badge-running';
    case 'WAITING_FOR_APPROVAL':
      return 'badge-waiting_for_approval';
    case 'COMPLETED':
      return 'badge-completed';
    case 'PARTIALLY_COMPLETED':
      return 'badge-partially_completed';
    case 'FAILED':
      return 'badge-failed';
    default:
      return 'badge-pending';
  }
}

export default function WorkflowOverview({
  workflow,
  onWorkflowLoaded,
  onRefresh,
  isRefreshing = false,
}: WorkflowOverviewProps) {
  const [lookupId, setLookupId] = useState<string>('');
  const [lookupLoading, setLookupLoading] = useState<boolean>(false);
  const [lookupError, setLookupError] = useState<string | null>(null);

  const handleLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = lookupId.trim();
    if (!clean) return;

    setLookupLoading(true);
    setLookupError(null);
    try {
      const data = await getWorkflow(clean);
      onWorkflowLoaded(data);
      setLookupId('');
    } catch (err: any) {
      setLookupError(err?.detail || err?.message || 'Workflow not found.');
    } finally {
      setLookupLoading(false);
    }
  };

  return (
    <div className="card" data-testid="workflow-overview-card">
      <div className="card-header">
        <div>
          <h2 className="card-title">2. Workflow Overview</h2>
          <span className="mono" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            ID: <strong style={{ color: '#93c5fd' }}>{workflow.workflow_id}</strong>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span
            className={`badge ${getWorkflowStatusBadgeClass(workflow.status)}`}
            data-testid="workflow-status-badge"
          >
            {workflow.status.replace(/_/g, ' ')}
          </span>
          <button
            type="button"
            className="btn-secondary"
            onClick={onRefresh}
            disabled={isRefreshing}
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
          >
            {isRefreshing ? 'Refreshing...' : 'Refresh State'}
          </button>
        </div>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <p className="form-label" style={{ marginBottom: '0.25rem' }}>
          Original Operational Request:
        </p>
        <div
          style={{
            backgroundColor: 'var(--bg-subtle)',
            padding: '0.65rem 0.85rem',
            borderRadius: '6px',
            fontSize: '0.85rem',
            color: '#e2e8f0',
            border: '1px solid var(--border-color)',
          }}
        >
          {workflow.request}
        </div>
      </div>

      {/* Lookup Bar */}
      <form onSubmit={handleLookup} className="search-bar" style={{ marginTop: '0.75rem' }}>
        <input
          type="text"
          className="lookup-input mono"
          placeholder="Look up another workflow ID (e.g. wf_...)"
          value={lookupId}
          onChange={(e) => setLookupId(e.target.value)}
          disabled={lookupLoading}
        />
        <button
          type="submit"
          className="btn-secondary"
          disabled={lookupLoading || !lookupId.trim()}
        >
          {lookupLoading ? 'Loading...' : 'Lookup'}
        </button>
      </form>
      {lookupError && (
        <p style={{ color: 'var(--status-failed)', fontSize: '0.75rem', marginTop: '0.35rem' }}>
          {lookupError}
        </p>
      )}
    </div>
  );
}
