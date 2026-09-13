'use client';

import React, { useState } from 'react';
import { createWorkflow } from '../lib/api';
import { WorkflowState } from '../lib/types';

interface WorkflowCreateProps {
  onWorkflowCreated: (workflow: WorkflowState) => void;
}

const EXAMPLE_REQUEST =
  'Onboard Acme Corporation. Research the company, prepare a company brief, create an onboarding checklist, and draft a welcome email.';

export default function WorkflowCreate({ onWorkflowCreated }: WorkflowCreateProps) {
  const [requestText, setRequestText] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = requestText.trim();
    if (!trimmed) {
      setError('Please provide a business operations request.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const workflow = await createWorkflow(trimmed);
      onWorkflowCreated(workflow);
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Failed to create workflow.');
    } finally {
      setLoading(false);
    }
  };

  const handleUseExample = () => {
    setRequestText(EXAMPLE_REQUEST);
    setError(null);
  };

  return (
    <div className="card" data-testid="workflow-create-card">
      <div className="card-header">
        <h2 className="card-title">1. Create Workflow</h2>
        <div className="example-chips">
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Template:</span>
          <button
            type="button"
            className="chip-btn"
            onClick={handleUseExample}
            disabled={loading}
          >
            Acme Onboarding Example
          </button>
        </div>
      </div>

      {error && (
        <div className="alert-error" role="alert" data-testid="create-error-banner">
          <strong>Error:</strong> {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="workflow-request-input" className="form-label">
            Natural Language Operations Request
          </label>
          <textarea
            id="workflow-request-input"
            className="textarea-request"
            placeholder="Describe operational tasks (e.g. research company, generate brief, create onboarding checklist, draft welcome email)..."
            value={requestText}
            onChange={(e) => setRequestText(e.target.value)}
            disabled={loading}
            rows={3}
          />
        </div>

        <button
          type="submit"
          className="btn-primary"
          disabled={loading || !requestText.trim()}
          data-testid="create-workflow-button"
        >
          {loading ? 'Executing Agent & Planning...' : 'Create Workflow'}
        </button>
      </form>
    </div>
  );
}
