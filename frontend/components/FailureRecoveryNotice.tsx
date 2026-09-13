'use client';

import React from 'react';
import { WorkflowState } from '../lib/types';

interface FailureRecoveryNoticeProps {
  workflow: WorkflowState;
}

export default function FailureRecoveryNotice({ workflow }: FailureRecoveryNoticeProps) {
  const { tasks, errors, status, audit_events } = workflow;

  const retryingTasks = tasks.filter((t) => t.status === 'RETRYING' || t.retry_count > 0);
  const failedTasks = tasks.filter((t) => t.status === 'FAILED');
  const blockedTasks = tasks.filter((t) => t.status === 'BLOCKED');
  const isPartial = status === 'PARTIALLY_COMPLETED';
  const hasErrors = errors && errors.length > 0;

  // If everything succeeded normally with no retries or errors, do not clutter
  if (retryingTasks.length === 0 && failedTasks.length === 0 && blockedTasks.length === 0 && !hasErrors && !isPartial) {
    return null;
  }

  // Find retry success events from audit trail
  const retrySuccessEvents = (audit_events || []).filter(
    (e) => e.event_type === 'task_retry_succeeded'
  );

  return (
    <div
      className="card"
      style={{
        border: '1px solid #7c3aed',
        background: 'linear-gradient(180deg, rgba(124, 58, 237, 0.08) 0%, rgba(17, 24, 39, 1) 100%)',
      }}
      data-testid="failure-recovery-panel"
    >
      <div className="card-header">
        <h3 className="card-title" style={{ color: '#c084fc' }}>
          6. Failure Recovery & Fault Isolation Telemetry
        </h3>
        <span className="badge badge-blocked">Fault Handling Active</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
        {/* Partial Completion Banner */}
        {isPartial && (
          <div className="alert-info" style={{ borderColor: '#eab308', color: '#fef08a' }} data-testid="partial-completion-banner">
            <strong>Partial Completion Achieved:</strong> The agent isolated task failures and successfully completed independent tasks without corrupting deliverables.
          </div>
        )}

        {/* Retries & Transient Failures */}
        {retryingTasks.length > 0 && (
          <div style={{ padding: '0.6rem 0.8rem', backgroundColor: 'var(--bg-main)', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
            <strong style={{ color: '#fbbf24' }}>Transient Failure Recovery:</strong>
            <ul style={{ paddingLeft: '1.2rem', marginTop: '0.35rem' }}>
              {retryingTasks.map((t) => (
                <li key={t.task_id} style={{ color: '#cbd5e1' }}>
                  Task <span className="mono font-bold">{t.name}</span> ({t.task_id}): {t.retry_count} retry attempt(s) triggered.{' '}
                  {t.status === 'COMPLETED' && (
                    <span style={{ color: '#10b981', fontWeight: 600 }}>✓ Recovered successfully on retry.</span>
                  )}
                  {t.status === 'RETRYING' && (
                    <span style={{ color: '#fbbf24', fontWeight: 600 }}>Retrying now...</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Retry Successes */}
        {retrySuccessEvents.length > 0 && (
          <div style={{ padding: '0.6rem 0.8rem', backgroundColor: 'rgba(16, 185, 129, 0.1)', borderRadius: '4px', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
            <strong style={{ color: '#34d399' }}>Retry Success Telemetry:</strong>
            <span style={{ marginLeft: '0.5rem', color: '#d1fae5' }}>
              Automatic backoff/retry succeeded for transient faults.
            </span>
          </div>
        )}

        {/* Blocked Dependencies */}
        {blockedTasks.length > 0 && (
          <div style={{ padding: '0.6rem 0.8rem', backgroundColor: 'var(--bg-main)', borderRadius: '4px', border: '1px solid #8b5cf6' }} data-testid="blocked-dependencies-notice">
            <strong style={{ color: '#c084fc' }}>Dependency Isolation (Blocked Tasks):</strong>
            <p style={{ color: '#cbd5e1', marginTop: '0.2rem' }}>
              Downstream tasks were safely prevented from executing due to upstream failures:
            </p>
            <ul style={{ paddingLeft: '1.2rem', marginTop: '0.35rem' }}>
              {blockedTasks.map((t) => (
                <li key={t.task_id} style={{ color: '#cbd5e1' }}>
                  Task <span className="mono font-bold">{t.name}</span> is <span className="badge badge-blocked">BLOCKED</span> (waiting on:{' '}
                  <span className="mono">{t.depends_on.join(', ')}</span>)
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Permanent / Classified Errors */}
        {errors && errors.length > 0 && (
          <div style={{ padding: '0.6rem 0.8rem', backgroundColor: 'var(--bg-main)', borderRadius: '4px', border: '1px solid rgba(239, 68, 68, 0.4)' }}>
            <strong style={{ color: '#f87171' }}>Classified Error Records:</strong>
            <div style={{ marginTop: '0.35rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              {errors.map((err, idx) => (
                <div key={idx} className="mono" style={{ fontSize: '0.75rem', color: '#fca5a5' }}>
                  [{err.error_type}] {err.message} (retryable: {err.retryable ? 'true' : 'false'})
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
