'use client';

import React, { useState } from 'react';
import { AuditEvent } from '../lib/types';
import { getWorkflowAudit } from '../lib/api';

interface AuditTimelineProps {
  workflowId: string;
  auditEvents: AuditEvent[];
  onAuditRefreshed?: (events: AuditEvent[]) => void;
}

export function getEventTypeBadgeClass(eventType: string): string {
  switch (eventType) {
    case 'workflow_created':
    case 'task_started':
      return 'badge-running';
    case 'task_completed':
    case 'workflow_completed':
    case 'approval_approved':
    case 'approval_granted':
    case 'task_retry_succeeded':
      return 'badge-completed';
    case 'task_retrying':
      return 'badge-retrying';
    case 'workflow_partially_completed':
      return 'badge-partially_completed';
    case 'task_failed':
    case 'task_retry_exhausted':
    case 'workflow_failed':
    case 'approval_rejected':
      return 'badge-failed';
    case 'task_blocked':
      return 'badge-blocked';
    case 'approval_requested':
      return 'badge-waiting_for_approval';
    default:
      return 'badge-pending';
  }
}

export default function AuditTimeline({
  workflowId,
  auditEvents,
  onAuditRefreshed,
}: AuditTimelineProps) {
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const handleRefreshAudit = async () => {
    if (!workflowId) return;
    setRefreshing(true);
    try {
      const data = await getWorkflowAudit(workflowId);
      if (onAuditRefreshed) {
        onAuditRefreshed(data.audit_events);
      }
    } catch (err) {
      console.error('Failed to refresh audit log:', err);
    } finally {
      setRefreshing(false);
    }
  };

  const toggleExpand = (idx: number) => {
    setExpandedIndex(expandedIndex === idx ? null : idx);
  };

  return (
    <div className="card" data-testid="audit-timeline-card">
      <div className="card-header">
        <div>
          <h3 className="card-title">5. Immutable Audit Trail & Telemetry</h3>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Recorded chronologically in SQLite persistence layer
          </p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={handleRefreshAudit}
          disabled={refreshing}
          style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
          data-testid="refresh-audit-button"
        >
          {refreshing ? 'Refreshing...' : 'Refresh Audit'}
        </button>
      </div>

      {(!auditEvents || auditEvents.length === 0) ? (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          No audit events recorded for this workflow yet.
        </p>
      ) : (
        <div className="timeline" data-testid="audit-timeline-list">
          {auditEvents.map((event, idx) => {
            const hasDetails = event.details && Object.keys(event.details).length > 0;
            const isExpanded = expandedIndex === idx;

            return (
              <div key={idx} className="timeline-item" data-testid={`audit-event-${idx}`}>
                <div className="timeline-dot" />
                <div className="timeline-content">
                  <div className="timeline-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span className={`badge ${getEventTypeBadgeClass(event.event_type)}`}>
                        {event.event_type}
                      </span>
                      {event.details?.tool && (
                        <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          {event.details.tool}
                        </span>
                      )}
                      {event.details?.action && (
                        <span style={{ fontSize: '0.8rem', color: '#e2e8f0' }}>
                          {event.details.action}
                        </span>
                      )}
                    </div>
                    <span className="timeline-time mono">
                      {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : ''}
                    </span>
                  </div>

                  {hasDetails && (
                    <div style={{ marginTop: '0.35rem' }}>
                      <button
                        type="button"
                        onClick={() => toggleExpand(idx)}
                        style={{
                          background: 'none',
                          color: 'var(--text-secondary)',
                          fontSize: '0.75rem',
                          padding: 0,
                          textDecoration: 'underline',
                        }}
                      >
                        {isExpanded ? 'Hide Details' : 'View Details'}
                      </button>
                      {isExpanded && (
                        <pre className="timeline-details mono" style={{ marginTop: '0.35rem' }}>
                          {JSON.stringify(event.details, null, 2)}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
