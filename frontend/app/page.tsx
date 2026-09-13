'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Header from '../components/Header';
import WorkflowCreate from '../components/WorkflowCreate';
import WorkflowOverview from '../components/WorkflowOverview';
import HumanApproval from '../components/HumanApproval';
import TaskList from '../components/TaskList';
import ArtifactsViewer from '../components/ArtifactsViewer';
import FailureRecoveryNotice from '../components/FailureRecoveryNotice';
import AuditTimeline from '../components/AuditTimeline';
import { WorkflowState, AuditEvent } from '../lib/types';
import { getWorkflow } from '../lib/api';

export default function OperationsConsolePage() {
  const [activeWorkflow, setActiveWorkflow] = useState<WorkflowState | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Manual refresh of current workflow
  const handleRefresh = useCallback(async () => {
    if (!activeWorkflow?.workflow_id) return;
    setIsRefreshing(true);
    try {
      const refreshed = await getWorkflow(activeWorkflow.workflow_id);
      setActiveWorkflow(refreshed);
    } catch (err) {
      console.error('Failed to refresh workflow:', err);
    } finally {
      setIsRefreshing(false);
    }
  }, [activeWorkflow?.workflow_id]);

  // Simple polling only when workflow is in an active non-terminal transition
  useEffect(() => {
    if (!activeWorkflow) return;
    const isTransitional =
      activeWorkflow.status === 'CREATED' ||
      activeWorkflow.status === 'PLANNING' ||
      activeWorkflow.status === 'EXECUTING';

    if (!isTransitional) return;

    const timer = setInterval(() => {
      handleRefresh();
    }, 3000);

    return () => clearInterval(timer);
  }, [activeWorkflow, handleRefresh]);

  const handleWorkflowCreated = (workflow: WorkflowState) => {
    setActiveWorkflow(workflow);
  };

  const handleDecisionSubmitted = (updated: WorkflowState) => {
    setActiveWorkflow(updated);
  };

  const handleAuditRefreshed = (events: AuditEvent[]) => {
    if (activeWorkflow) {
      setActiveWorkflow({
        ...activeWorkflow,
        audit_events: events,
      });
    }
  };

  return (
    <main className="container" data-testid="operations-console-main">
      <Header />

      <WorkflowCreate onWorkflowCreated={handleWorkflowCreated} />

      {activeWorkflow ? (
        <>
          <WorkflowOverview
            workflow={activeWorkflow}
            onWorkflowLoaded={setActiveWorkflow}
            onRefresh={handleRefresh}
            isRefreshing={isRefreshing}
          />

          {/* Human Approval Gate - Visually obvious boundary */}
          <HumanApproval
            workflow={activeWorkflow}
            onDecisionSubmitted={handleDecisionSubmitted}
          />

          {/* Failure Recovery / Telemetry Banner */}
          <FailureRecoveryNotice workflow={activeWorkflow} />

          {/* Task Orchestration List */}
          <TaskList tasks={activeWorkflow.tasks} />

          {/* Generated Deliverables & Artifacts */}
          <ArtifactsViewer workflow={activeWorkflow} />

          {/* Chronological Audit Timeline */}
          <AuditTimeline
            workflowId={activeWorkflow.workflow_id}
            auditEvents={activeWorkflow.audit_events}
            onAuditRefreshed={handleAuditRefreshed}
          />
        </>
      ) : (
        <div className="card empty-state" data-testid="empty-console-card">
          <h3>No Active Operations Workflow</h3>
          <p style={{ marginTop: '0.5rem' }}>
            Submit a request above or enter an existing Workflow ID in the lookup bar to inspect
            the agent plan, tool execution, human approval gates, failure recovery, and audit trails.
          </p>
        </div>
      )}
    </main>
  );
}
