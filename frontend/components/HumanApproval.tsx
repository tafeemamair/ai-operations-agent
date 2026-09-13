'use client';

import React, { useState } from 'react';
import { WorkflowState } from '../lib/types';
import { approveWorkflow, rejectWorkflow } from '../lib/api';

interface HumanApprovalProps {
  workflow: WorkflowState;
  onDecisionSubmitted: (updatedWorkflow: WorkflowState) => void;
}

export default function HumanApproval({
  workflow,
  onDecisionSubmitted,
}: HumanApprovalProps) {
  const [reason, setReason] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Strictly show approval panel only when waiting for approval
  if (workflow.status !== 'WAITING_FOR_APPROVAL') {
    return null;
  }

  // Extract email preview information from tool results or artifacts
  const emailToolResult = workflow.tool_results.find(
    (tr) => tr.tool_name === 'draft_welcome_email' && tr.data
  );
  const emailArtifact = workflow.artifacts.find(
    (art) => art.artifact_type === 'welcome_email_draft'
  );

  const recipient =
    emailToolResult?.data?.recipient ||
    (workflow.approvals.length > 0 && workflow.approvals[0].action.includes(' to ')
      ? workflow.approvals[0].action.split(' to ')[1]
      : 'operations-team@acme-corp.demo');

  const subject =
    emailToolResult?.data?.subject ||
    'Welcome to AI Operations Agent Partnership';

  const body =
    emailToolResult?.data?.body ||
    emailArtifact?.content ||
    'Email draft body unavailable.';

  const handleApprove = async () => {
    setLoading(true);
    setError(null);
    try {
      const updated = await approveWorkflow(
        workflow.workflow_id,
        reason.trim() || undefined
      );
      onDecisionSubmitted(updated);
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Failed to approve workflow.');
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    setLoading(true);
    setError(null);
    try {
      const updated = await rejectWorkflow(
        workflow.workflow_id,
        reason.trim() || 'Rejected by human operator'
      );
      onDecisionSubmitted(updated);
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Failed to reject workflow.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="approval-boundary"
      data-testid="human-approval-panel"
      role="region"
      aria-label="Human-in-the-loop Approval Gate"
    >
      <div className="approval-gate-banner">
        <div className="approval-gate-icon">!</div>
        <div className="approval-gate-text">
          <h3>HUMAN-IN-THE-LOOP APPROVAL REQUIRED</h3>
          <p>
            Autonomous execution is suspended. The agent has prepared the communication draft below.
            A human operator must inspect and approve or reject before the workflow can proceed.
          </p>
        </div>
      </div>

      {error && (
        <div className="alert-error" role="alert" data-testid="approval-error-banner">
          <strong>Decision Error:</strong> {error}
        </div>
      )}

      {/* Email Draft Preview */}
      <div className="email-preview-container" data-testid="email-preview-card">
        <div className="email-preview-header">
          <div className="email-header-row">
            <span className="email-header-label">To:</span>
            <span className="email-header-value mono" data-testid="email-recipient">
              {recipient}
            </span>
          </div>
          <div className="email-header-row">
            <span className="email-header-label">Subject:</span>
            <span className="email-header-value" data-testid="email-subject">
              {subject}
            </span>
          </div>
        </div>
        <div className="email-preview-body mono" data-testid="email-body">
          {body}
        </div>
      </div>

      {/* Decision Controls */}
      <div className="approval-actions">
        <div className="form-group" style={{ marginBottom: '0.5rem' }}>
          <label htmlFor="approval-reason-input" className="form-label">
            Operator Note / Rejection Reason (Optional for approval, recorded in audit trail):
          </label>
          <input
            id="approval-reason-input"
            type="text"
            placeholder="e.g. Verified client facts and onboarding checklist..."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={loading}
          />
        </div>

        <div className="approval-buttons">
          <button
            type="button"
            className="btn-approve"
            onClick={handleApprove}
            disabled={loading}
            data-testid="approve-workflow-button"
          >
            {loading ? 'Submitting...' : 'Approve Workflow'}
          </button>
          <button
            type="button"
            className="btn-reject"
            onClick={handleReject}
            disabled={loading}
            data-testid="reject-workflow-button"
          >
            {loading ? 'Submitting...' : 'Reject Workflow'}
          </button>
        </div>
      </div>
    </div>
  );
}
