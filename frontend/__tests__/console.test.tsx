import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import WorkflowCreate from '../components/WorkflowCreate';
import WorkflowOverview from '../components/WorkflowOverview';
import HumanApproval from '../components/HumanApproval';
import TaskList from '../components/TaskList';
import FailureRecoveryNotice from '../components/FailureRecoveryNotice';
import AuditTimeline from '../components/AuditTimeline';
import * as api from '../lib/api';
import { WorkflowState } from '../lib/types';

describe('AI Operations Console UI Components', () => {
  const mockWorkflowWaiting: WorkflowState = {
    workflow_id: 'wf_test_001',
    request: 'Onboard Acme Corporation. Research company, generate brief, checklist, and email draft.',
    status: 'WAITING_FOR_APPROVAL',
    tasks: [
      {
        task_id: 'task_1',
        name: 'Research Acme Corporation',
        description: 'Gather operational intelligence',
        status: 'COMPLETED',
        tool_name: 'research_company',
        depends_on: [],
        requires_approval: false,
        retry_count: 0,
      },
      {
        task_id: 'task_2',
        name: 'Draft Welcome Email',
        description: 'Prepare introductory email',
        status: 'REQUIRES_APPROVAL',
        tool_name: 'draft_welcome_email',
        depends_on: ['task_1'],
        requires_approval: true,
        retry_count: 0,
      },
    ],
    tool_results: [
      {
        tool_name: 'draft_welcome_email',
        success: true,
        data: {
          recipient: 'operations-team@acme-corp.demo',
          subject: 'Welcome to AI Operations Agent Partnership - Acme Corporation',
          body: 'Dear Acme Corporation Operations Team,\n\nWelcome aboard!',
        },
      },
    ],
    artifacts: [
      {
        artifact_id: 'art_email_1',
        artifact_type: 'welcome_email_draft',
        name: 'Welcome Email Draft',
        content: 'Dear Acme Corporation Operations Team,\n\nWelcome aboard!',
        created_at: '2026-09-13T12:00:00Z',
      },
    ],
    approvals: [
      {
        approval_id: 'appr_1',
        action: 'Dispatch Welcome Email to operations-team@acme-corp.demo',
        status: 'PENDING',
        requested_at: '2026-09-13T12:00:00Z',
      },
    ],
    errors: [],
    audit_events: [
      {
        timestamp: '2026-09-13T12:00:00Z',
        event_type: 'workflow_created',
        details: { request: 'Onboard Acme Corporation' },
      },
      {
        timestamp: '2026-09-13T12:00:01Z',
        event_type: 'task_started',
        details: { task_id: 'task_1', tool: 'research_company' },
      },
      {
        timestamp: '2026-09-13T12:00:02Z',
        event_type: 'approval_requested',
        details: { action: 'Dispatch Welcome Email to operations-team@acme-corp.demo' },
      },
    ],
    created_at: '2026-09-13T12:00:00Z',
    updated_at: '2026-09-13T12:00:02Z',
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('1. Workflow Creation: fills template and triggers createWorkflow', async () => {
    const createSpy = vi.spyOn(api, 'createWorkflow').mockResolvedValueOnce(mockWorkflowWaiting);
    const onCreated = vi.fn();

    render(<WorkflowCreate onWorkflowCreated={onCreated} />);

    const exampleBtn = screen.getByText('Acme Onboarding Example');
    fireEvent.click(exampleBtn);

    const input = screen.getByLabelText(/Natural Language Operations Request/i) as HTMLTextAreaElement;
    expect(input.value).toContain('Onboard Acme Corporation');

    const submitBtn = screen.getByTestId('create-workflow-button');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(expect.stringContaining('Acme Corporation'));
      expect(onCreated).toHaveBeenCalledWith(mockWorkflowWaiting);
    });
  });

  it('2. Workflow Overview: renders workflow ID and status badge', () => {
    render(
      <WorkflowOverview
        workflow={mockWorkflowWaiting}
        onWorkflowLoaded={vi.fn()}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText('wf_test_001')).toBeInTheDocument();
    const badge = screen.getByTestId('workflow-status-badge');
    expect(badge).toHaveTextContent('WAITING FOR APPROVAL');
  });

  it('3. Human Approval: displays boundary and details when WAITING_FOR_APPROVAL', () => {
    render(
      <HumanApproval
        workflow={mockWorkflowWaiting}
        onDecisionSubmitted={vi.fn()}
      />
    );

    expect(screen.getByTestId('human-approval-panel')).toBeInTheDocument();
    expect(screen.getByText(/HUMAN-IN-THE-LOOP APPROVAL REQUIRED/i)).toBeInTheDocument();
    expect(screen.getByTestId('email-recipient')).toHaveTextContent('operations-team@acme-corp.demo');
    expect(screen.getByTestId('email-subject')).toHaveTextContent('Welcome to AI Operations Agent Partnership');
    expect(screen.getByTestId('approve-workflow-button')).toBeInTheDocument();
    expect(screen.getByTestId('reject-workflow-button')).toBeInTheDocument();
  });

  it('4. Human Approval: hidden when workflow is COMPLETED', () => {
    const completedWorkflow: WorkflowState = {
      ...mockWorkflowWaiting,
      status: 'COMPLETED',
    };

    const { container } = render(
      <HumanApproval
        workflow={completedWorkflow}
        onDecisionSubmitted={vi.fn()}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('5. Approve action: invokes approveWorkflow API and updates state', async () => {
    const updated: WorkflowState = {
      ...mockWorkflowWaiting,
      status: 'COMPLETED',
    };
    const approveSpy = vi.spyOn(api, 'approveWorkflow').mockResolvedValueOnce(updated);
    const onDecision = vi.fn();

    render(
      <HumanApproval
        workflow={mockWorkflowWaiting}
        onDecisionSubmitted={onDecision}
      />
    );

    const approveBtn = screen.getByTestId('approve-workflow-button');
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(approveSpy).toHaveBeenCalledWith('wf_test_001', undefined);
      expect(onDecision).toHaveBeenCalledWith(updated);
    });
  });

  it('6. Reject action: invokes rejectWorkflow API with rejection reason', async () => {
    const updated: WorkflowState = {
      ...mockWorkflowWaiting,
      status: 'FAILED',
    };
    const rejectSpy = vi.spyOn(api, 'rejectWorkflow').mockResolvedValueOnce(updated);
    const onDecision = vi.fn();

    render(
      <HumanApproval
        workflow={mockWorkflowWaiting}
        onDecisionSubmitted={onDecision}
      />
    );

    const reasonInput = screen.getByPlaceholderText(/Verified client facts/i);
    fireEvent.change(reasonInput, { target: { value: 'Revision needed' } });

    const rejectBtn = screen.getByTestId('reject-workflow-button');
    fireEvent.click(rejectBtn);

    await waitFor(() => {
      expect(rejectSpy).toHaveBeenCalledWith('wf_test_001', 'Revision needed');
      expect(onDecision).toHaveBeenCalledWith(updated);
    });
  });

  it('7. Failure Recovery: renders retrying, blocked, and partial completion states', () => {
    const failureWorkflow: WorkflowState = {
      ...mockWorkflowWaiting,
      status: 'PARTIALLY_COMPLETED',
      tasks: [
        {
          task_id: 'task_retry',
          name: 'Transient Step',
          description: 'Step that retried',
          status: 'COMPLETED',
          depends_on: [],
          requires_approval: false,
          retry_count: 2,
        },
        {
          task_id: 'task_failed',
          name: 'Permanent Failure Step',
          description: 'Step that failed permanently',
          status: 'FAILED',
          error: 'Connection permanently refused',
          depends_on: [],
          requires_approval: false,
          retry_count: 0,
        },
        {
          task_id: 'task_blocked',
          name: 'Downstream Dependent Step',
          description: 'Step blocked by failure',
          status: 'BLOCKED',
          depends_on: ['task_failed'],
          requires_approval: false,
          retry_count: 0,
        },
      ],
      errors: [
        {
          task_id: 'task_failed',
          error_type: 'ConnectionError',
          message: 'Connection permanently refused',
          retryable: false,
          timestamp: '2026-09-13T12:00:00Z',
        },
      ],
    };

    render(<FailureRecoveryNotice workflow={failureWorkflow} />);

    expect(screen.getByTestId('failure-recovery-panel')).toBeInTheDocument();
    expect(screen.getByTestId('partial-completion-banner')).toBeInTheDocument();
    expect(screen.getByTestId('blocked-dependencies-notice')).toBeInTheDocument();
    expect(screen.getByText(/2 retry attempt\(s\) triggered/i)).toBeInTheDocument();
  });

  it('8. Task List: renders all status badges including BLOCKED and RETRYING', () => {
    const tasks = [
      {
        task_id: 't1',
        name: 'Task Pending',
        description: 'desc',
        status: 'PENDING' as const,
        depends_on: [],
        requires_approval: false,
        retry_count: 0,
      },
      {
        task_id: 't2',
        name: 'Task Retrying',
        description: 'desc',
        status: 'RETRYING' as const,
        depends_on: [],
        requires_approval: false,
        retry_count: 1,
      },
      {
        task_id: 't3',
        name: 'Task Blocked',
        description: 'desc',
        status: 'BLOCKED' as const,
        depends_on: ['t2'],
        requires_approval: false,
        retry_count: 0,
      },
    ];

    render(<TaskList tasks={tasks} />);

    expect(screen.getByTestId('task-status-t1')).toHaveTextContent('PENDING');
    expect(screen.getByTestId('task-status-t2')).toHaveTextContent('RETRYING');
    expect(screen.getByTestId('task-status-t3')).toHaveTextContent('BLOCKED');
  });

  it('9. Audit Timeline: renders chronological events and event types', () => {
    render(
      <AuditTimeline
        workflowId="wf_test_001"
        auditEvents={mockWorkflowWaiting.audit_events}
      />
    );

    expect(screen.getByTestId('audit-timeline-card')).toBeInTheDocument();
    expect(screen.getByText('workflow_created')).toBeInTheDocument();
    expect(screen.getByText('task_started')).toBeInTheDocument();
    expect(screen.getByText('approval_requested')).toBeInTheDocument();
  });

  it('10. Safe Error Handling: shows error banner upon failed submission', async () => {
    vi.spyOn(api, 'createWorkflow').mockRejectedValueOnce({
      detail: 'Workflow request must be a non-empty string.',
    });

    render(<WorkflowCreate onWorkflowCreated={vi.fn()} />);

    const input = screen.getByLabelText(/Natural Language Operations Request/i);
    fireEvent.change(input, { target: { value: 'Something' } });

    const submitBtn = screen.getByTestId('create-workflow-button');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      const banner = screen.getByTestId('create-error-banner');
      expect(banner).toHaveTextContent('Workflow request must be a non-empty string.');
    });
  });
});
