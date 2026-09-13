'use client';

import React from 'react';
import { Task, TaskStatus } from '../lib/types';

interface TaskListProps {
  tasks: Task[];
}

export function getTaskStatusBadgeClass(status: TaskStatus): string {
  switch (status) {
    case 'PENDING':
      return 'badge-pending';
    case 'RUNNING':
      return 'badge-running';
    case 'RETRYING':
      return 'badge-retrying';
    case 'COMPLETED':
      return 'badge-completed';
    case 'FAILED':
      return 'badge-failed';
    case 'BLOCKED':
      return 'badge-blocked';
    case 'REQUIRES_APPROVAL':
      return 'badge-requires_approval';
    default:
      return 'badge-pending';
  }
}

export default function TaskList({ tasks }: TaskListProps) {
  if (!tasks || tasks.length === 0) {
    return (
      <div className="card" data-testid="task-list-empty">
        <h3 className="card-title" style={{ marginBottom: '0.5rem' }}>Tasks</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          No tasks recorded for this workflow yet.
        </p>
      </div>
    );
  }

  return (
    <div className="card" data-testid="task-list-card">
      <div className="card-header">
        <h3 className="card-title">Task Orchestration Plan</h3>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {tasks.filter((t) => t.status === 'COMPLETED').length} / {tasks.length} Completed
        </span>
      </div>

      <div className="task-grid">
        {tasks.map((task, idx) => (
          <div
            key={task.task_id}
            className="task-item"
            data-testid={`task-item-${task.task_id}`}
          >
            <div className="task-info">
              <div className="task-title-row">
                <span
                  className="mono"
                  style={{ fontSize: '0.8rem', color: 'var(--text-muted)', minWidth: '24px' }}
                >
                  #{idx + 1}
                </span>
                <span className="task-title">{task.name}</span>
                {task.tool_name && (
                  <span className="task-tool mono">tool: {task.tool_name}</span>
                )}
                {task.requires_approval && (
                  <span
                    className="badge badge-requires_approval"
                    style={{ fontSize: '0.65rem', padding: '0.1rem 0.4rem' }}
                  >
                    Requires Approval
                  </span>
                )}
              </div>

              {task.description && (
                <p className="task-desc">{task.description}</p>
              )}

              {task.depends_on && task.depends_on.length > 0 && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Depends on: <span className="mono">{task.depends_on.join(', ')}</span>
                </div>
              )}

              {task.error && (
                <div className="task-error" data-testid={`task-error-${task.task_id}`}>
                  <strong>Failure:</strong> {task.error}
                </div>
              )}
            </div>

            <div className="task-meta">
              {task.retry_count > 0 && (
                <span
                  className="badge badge-retrying"
                  data-testid={`task-retries-${task.task_id}`}
                >
                  Retries: {task.retry_count}
                </span>
              )}
              <span
                className={`badge ${getTaskStatusBadgeClass(task.status)}`}
                data-testid={`task-status-${task.task_id}`}
              >
                {task.status.replace(/_/g, ' ')}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
