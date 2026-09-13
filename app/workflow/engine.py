"""Workflow execution engine and deterministic state machine.

Enforces valid state and task transitions across the core operational lifecycle:
CREATED → PLANNING → EXECUTING → WAITING_FOR_APPROVAL → COMPLETED / PARTIALLY_COMPLETED / FAILED.
"""

from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from app.workflow.state import (
    Approval,
    ApprovalStatus,
    Artifact,
    ErrorRecord,
    Plan,
    Task,
    TaskStatus,
    ToolResult,
    WorkflowState,
    WorkflowStatus,
)
from app.workflow.validation import (
    ensure_task_completion_valid,
    ensure_task_execution_valid,
    ensure_valid_task_fields,
    ensure_valid_task_transition,
    ensure_valid_tool_result,
    ensure_valid_workflow_transition,
)


class WorkflowEngine:
    """State machine coordinator enforcing deterministic transitions and audit trails."""

    def __init__(self, state: WorkflowState) -> None:
        self.state = state

    def get_state(self) -> WorkflowState:
        """Return the current workflow state."""
        return self.state

    def transition_to(self, next_status: WorkflowStatus) -> WorkflowState:
        """Deterministically transition workflow to a new status.

        Raises:
            InvalidWorkflowTransitionError: If the transition is disallowed.
        """
        ensure_valid_workflow_transition(self.state.status, next_status)
        self.state.status = next_status
        self.state.updated_at = datetime.now(timezone.utc)
        return self.state

    def advance_to(self, next_status: WorkflowStatus) -> WorkflowState:
        """Convenience alias for transition_to."""
        return self.transition_to(next_status)

    def set_plan(self, plan: Plan) -> None:
        """Attach a plan to the workflow and populate its task list."""
        for task in plan.tasks:
            ensure_valid_task_fields(task)
        self.state.plan = plan
        self.state.tasks = list(plan.tasks)
        self.state.updated_at = datetime.now(timezone.utc)

    def add_task(self, task: Task) -> None:
        """Add an individual task to the workflow after field validation."""
        ensure_valid_task_fields(task)
        self.state.tasks.append(task)
        self.state.updated_at = datetime.now(timezone.utc)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by ID."""
        for task in self.state.tasks:
            if task.task_id == task_id:
                return task
        return None

    def transition_task(self, task_id: str, next_status: TaskStatus) -> Task:
        """Deterministically transition a task's status with validation gates.

        Raises:
            KeyError: If task_id is not found in workflow.
            InvalidTaskTransitionError: If the state transition is illegal.
            TaskExecutionValidationError: If an approval-gated task runs without approval.
            TaskCompletionValidationError: If a task completes without a valid result.
        """
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"Task with id '{task_id}' not found in workflow '{self.state.workflow_id}'.")

        # 1. Enforce deterministic state transition
        ensure_valid_task_transition(task.status, next_status)

        # 2. Enforce execution gates (e.g. human approval required)
        if next_status == TaskStatus.RUNNING:
            if task.requires_approval:
                ensure_task_execution_valid(task, self.state.approvals)
            self.state.current_task = task.task_id

        # 3. Enforce completion gates (must have valid successful result)
        if next_status == TaskStatus.COMPLETED:
            ensure_task_completion_valid(task)
            if self.state.current_task == task.task_id:
                self.state.current_task = None

        if next_status in (TaskStatus.FAILED, TaskStatus.BLOCKED):
            if self.state.current_task == task.task_id:
                self.state.current_task = None

        # 4. Handle retry accounting
        if next_status == TaskStatus.RETRYING:
            task.retry_count += 1

        task.status = next_status
        self.state.updated_at = datetime.now(timezone.utc)
        return task

    def can_execute_task(self, task_id: str) -> bool:
        """Check whether all upstream dependencies for task_id are COMPLETED."""
        task = self.get_task(task_id)
        if not task:
            return False
        for dep_id in task.depends_on:
            dep_task = self.get_task(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True

    def block_dependent_tasks(self, failed_task_id: str) -> list[str]:
        """Find all downstream tasks directly or transitively dependent on failed_task_id and mark BLOCKED."""
        blocked_ids: list[str] = []
        to_check = [failed_task_id]

        while to_check:
            current_fail = to_check.pop(0)
            for task in self.state.tasks:
                if current_fail in task.depends_on and task.status in (TaskStatus.PENDING, TaskStatus.REQUIRES_APPROVAL):
                    task.status = TaskStatus.BLOCKED
                    self.add_audit_event(
                        event_type="task_blocked",
                        details={
                            "task_id": task.task_id,
                            "reason": f"Dependency '{current_fail}' failed",
                        },
                    )
                    blocked_ids.append(task.task_id)
                    to_check.append(task.task_id)

        self.state.updated_at = datetime.now(timezone.utc)
        return blocked_ids

    def evaluate_final_status(self) -> WorkflowStatus:
        """Deterministically determine final workflow status from task execution outcomes."""
        if not self.state.tasks:
            return self.state.status

        completed_count = sum(1 for t in self.state.tasks if t.status == TaskStatus.COMPLETED)
        failed_or_blocked_count = sum(
            1 for t in self.state.tasks if t.status in (TaskStatus.FAILED, TaskStatus.BLOCKED)
        )

        # If any approval is pending, wait
        if any(a.status == ApprovalStatus.PENDING for a in self.state.approvals):
            return WorkflowStatus.WAITING_FOR_APPROVAL

        # If all tasks are completed
        if completed_count == len(self.state.tasks):
            return WorkflowStatus.COMPLETED

        # If some tasks completed and some failed/blocked -> PARTIALLY_COMPLETED
        if completed_count > 0 and failed_or_blocked_count > 0:
            return WorkflowStatus.PARTIALLY_COMPLETED

        # If no tasks completed and failures occurred -> FAILED
        if completed_count == 0 and failed_or_blocked_count > 0:
            return WorkflowStatus.FAILED

        return self.state.status

    def record_tool_result(self, task_id: str, result: ToolResult) -> None:
        """Validate and associate a tool execution result with a task."""
        ensure_valid_tool_result(result)
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"Task '{task_id}' not found.")

        task.result = result
        if not result.success and result.error:
            task.error = result.error

        self.state.tool_results.append(result)
        self.state.updated_at = datetime.now(timezone.utc)

    def request_approval(
        self,
        action: str,
        task_id: Optional[str] = None,
        approval_id: Optional[str] = None,
    ) -> Approval:
        """Create a human approval request and update workflow/task status accordingly."""
        appr_id = approval_id or (task_id if task_id else f"appr_{uuid.uuid4().hex[:8]}")
        approval = Approval(
            approval_id=appr_id,
            action=action,
            status=ApprovalStatus.PENDING,
        )
        self.state.approvals.append(approval)

        if task_id:
            task = self.get_task(task_id)
            if task and task.status == TaskStatus.PENDING:
                self.transition_task(task_id, TaskStatus.REQUIRES_APPROVAL)

        if self.state.status == WorkflowStatus.EXECUTING:
            self.transition_to(WorkflowStatus.WAITING_FOR_APPROVAL)

        self.state.updated_at = datetime.now(timezone.utc)
        return approval

    def resolve_approval(
        self,
        approval_id: str,
        approved: bool,
        reason: Optional[str] = None,
    ) -> Approval:
        """Record human approval or rejection decision."""
        target_appr: Optional[Approval] = None
        for appr in self.state.approvals:
            if appr.approval_id == approval_id:
                target_appr = appr
                break

        if target_appr is None:
            raise KeyError(f"Approval request '{approval_id}' not found.")

        target_appr.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        target_appr.resolved_at = datetime.now(timezone.utc)
        target_appr.reason = reason
        self.state.updated_at = datetime.now(timezone.utc)
        return target_appr

    def record_error(self, error: ErrorRecord) -> None:
        """Log an operational error to the workflow record."""
        self.state.errors.append(error)
        self.state.updated_at = datetime.now(timezone.utc)

    def add_artifact(self, artifact: Artifact) -> None:
        """Register an operational artifact generated during execution."""
        self.state.artifacts.append(artifact)
        self.state.updated_at = datetime.now(timezone.utc)

    def add_audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Append an audit trail event."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details,
        }
        self.state.audit_events.append(event)
        self.state.updated_at = datetime.now(timezone.utc)
