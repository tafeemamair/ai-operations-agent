"""Comprehensive tests for Stage 2 - Workflow state and deterministic state machine."""

import pytest
from datetime import datetime, timezone

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
from app.workflow.engine import WorkflowEngine
from app.workflow.validation import (
    InvalidTaskTransitionError,
    InvalidWorkflowTransitionError,
    TaskCompletionValidationError,
    TaskExecutionValidationError,
    ToolResultValidationError,
    validate_task_completion,
    validate_task_execution,
    validate_tool_result,
)


def test_pydantic_model_creation() -> None:
    """Verify creation and serialization of all Stage 2 Pydantic models."""
    tool_res = ToolResult(
        tool_name="research",
        success=True,
        data={"summary": "Market analysis complete"},
    )
    assert tool_res.tool_name == "research"
    assert tool_res.success is True
    assert tool_res.data == {"summary": "Market analysis complete"}

    artifact = Artifact(
        artifact_id="art-1",
        artifact_type="report",
        name="Market Report",
        content="# Market Report Content",
    )
    assert artifact.artifact_id == "art-1"
    assert isinstance(artifact.created_at, datetime)

    approval = Approval(
        approval_id="appr-1",
        action="send_email",
    )
    assert approval.status == ApprovalStatus.PENDING
    assert approval.resolved_at is None

    error = ErrorRecord(
        task_id="task-1",
        error_type="NetworkTimeout",
        message="Failed to connect to API",
        retryable=True,
    )
    assert error.retryable is True

    task = Task(
        task_id="task-1",
        name="Market Research",
        tool_name="research",
        requires_approval=False,
    )
    assert task.status == TaskStatus.PENDING
    assert task.retry_count == 0

    plan = Plan(objective="Analyze market trends", tasks=[task])
    assert plan.objective == "Analyze market trends"
    assert len(plan.tasks) == 1

    state = WorkflowState(
        workflow_id="wf-1",
        request="Perform market research",
        plan=plan,
        tasks=[task],
    )
    assert state.workflow_id == "wf-1"
    assert state.status == WorkflowStatus.CREATED

    # Verify JSON serialization works seamlessly
    json_dump = state.model_dump_json()
    reconstructed = WorkflowState.model_validate_json(json_dump)
    assert reconstructed.workflow_id == "wf-1"
    assert reconstructed.plan.objective == "Analyze market trends"


def test_default_state() -> None:
    """Verify default initial state values for a newly instantiated WorkflowState."""
    state = WorkflowState(workflow_id="wf-default", request="Onboard client")
    assert state.status == WorkflowStatus.CREATED
    assert state.plan is None
    assert state.tasks == []
    assert state.current_task is None
    assert state.tool_results == []
    assert state.artifacts == []
    assert state.approvals == []
    assert state.errors == []
    assert state.audit_events == []
    assert isinstance(state.created_at, datetime)
    assert isinstance(state.updated_at, datetime)


def test_valid_workflow_transitions() -> None:
    """Verify permitted workflow state transitions."""
    state = WorkflowState(workflow_id="wf-transitions", request="Quarterly filing")
    engine = WorkflowEngine(state)

    # CREATED -> PLANNING
    engine.transition_to(WorkflowStatus.PLANNING)
    assert engine.get_state().status == WorkflowStatus.PLANNING

    # PLANNING -> EXECUTING
    engine.transition_to(WorkflowStatus.EXECUTING)
    assert engine.get_state().status == WorkflowStatus.EXECUTING

    # EXECUTING -> EXECUTING (self-loop for step iteration)
    engine.transition_to(WorkflowStatus.EXECUTING)
    assert engine.get_state().status == WorkflowStatus.EXECUTING

    # EXECUTING -> WAITING_FOR_APPROVAL
    engine.transition_to(WorkflowStatus.WAITING_FOR_APPROVAL)
    assert engine.get_state().status == WorkflowStatus.WAITING_FOR_APPROVAL

    # WAITING_FOR_APPROVAL -> EXECUTING
    engine.transition_to(WorkflowStatus.EXECUTING)
    assert engine.get_state().status == WorkflowStatus.EXECUTING

    # EXECUTING -> COMPLETED
    engine.transition_to(WorkflowStatus.COMPLETED)
    assert engine.get_state().status == WorkflowStatus.COMPLETED

    # Also test alternative branches:
    # 1. WAITING_FOR_APPROVAL -> FAILED
    state2 = WorkflowState(workflow_id="wf-fail-appr", request="Test")
    engine2 = WorkflowEngine(state2)
    engine2.transition_to(WorkflowStatus.PLANNING)
    engine2.transition_to(WorkflowStatus.EXECUTING)
    engine2.transition_to(WorkflowStatus.WAITING_FOR_APPROVAL)
    engine2.transition_to(WorkflowStatus.FAILED)
    assert engine2.get_state().status == WorkflowStatus.FAILED

    # 2. EXECUTING -> FAILED
    state3 = WorkflowState(workflow_id="wf-fail-exec", request="Test")
    engine3 = WorkflowEngine(state3)
    engine3.transition_to(WorkflowStatus.PLANNING)
    engine3.transition_to(WorkflowStatus.EXECUTING)
    engine3.transition_to(WorkflowStatus.FAILED)
    assert engine3.get_state().status == WorkflowStatus.FAILED


def test_invalid_workflow_transitions() -> None:
    """Verify disallowed workflow transitions raise InvalidWorkflowTransitionError."""
    state = WorkflowState(workflow_id="wf-invalid", request="Invalid ops")
    engine = WorkflowEngine(state)

    # Cannot skip from CREATED directly to EXECUTING or COMPLETED
    with pytest.raises(InvalidWorkflowTransitionError):
        engine.transition_to(WorkflowStatus.EXECUTING)

    with pytest.raises(InvalidWorkflowTransitionError):
        engine.transition_to(WorkflowStatus.COMPLETED)

    # Transition to PLANNING
    engine.transition_to(WorkflowStatus.PLANNING)

    # Cannot jump from PLANNING directly to COMPLETED or WAITING_FOR_APPROVAL
    with pytest.raises(InvalidWorkflowTransitionError):
        engine.transition_to(WorkflowStatus.COMPLETED)

    with pytest.raises(InvalidWorkflowTransitionError):
        engine.transition_to(WorkflowStatus.WAITING_FOR_APPROVAL)

    # Move to EXECUTING and COMPLETED
    engine.transition_to(WorkflowStatus.EXECUTING)
    engine.transition_to(WorkflowStatus.COMPLETED)

    # COMPLETED is terminal: cannot transition anywhere
    with pytest.raises(InvalidWorkflowTransitionError):
        engine.transition_to(WorkflowStatus.EXECUTING)

    with pytest.raises(InvalidWorkflowTransitionError):
        engine.transition_to(WorkflowStatus.PLANNING)


def test_valid_task_transitions() -> None:
    """Verify permitted task transitions."""
    task = Task(task_id="t-1", name="Task 1")
    state = WorkflowState(workflow_id="wf-task-trans", request="Ops", tasks=[task])
    engine = WorkflowEngine(state)

    # PENDING -> RUNNING
    engine.transition_task("t-1", TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING
    assert engine.get_state().current_task == "t-1"

    # RUNNING -> RETRYING
    engine.transition_task("t-1", TaskStatus.RETRYING)
    assert task.status == TaskStatus.RETRYING
    assert task.retry_count == 1

    # RETRYING -> RUNNING
    engine.transition_task("t-1", TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING

    # RUNNING -> FAILED
    engine.transition_task("t-1", TaskStatus.FAILED)
    assert task.status == TaskStatus.FAILED

    # Test PENDING -> BLOCKED
    task_blocked = Task(task_id="t-blocked", name="Blocked task")
    engine.add_task(task_blocked)
    engine.transition_task("t-blocked", TaskStatus.BLOCKED)
    assert task_blocked.status == TaskStatus.BLOCKED

    # Test PENDING -> REQUIRES_APPROVAL -> BLOCKED
    task_appr = Task(task_id="t-appr", name="Appr task", requires_approval=True)
    engine.add_task(task_appr)
    engine.transition_task("t-appr", TaskStatus.REQUIRES_APPROVAL)
    assert task_appr.status == TaskStatus.REQUIRES_APPROVAL
    engine.transition_task("t-appr", TaskStatus.BLOCKED)
    assert task_appr.status == TaskStatus.BLOCKED


def test_invalid_task_transitions() -> None:
    """Verify disallowed task transitions raise InvalidTaskTransitionError."""
    task = Task(task_id="t-bad", name="Bad Task")
    state = WorkflowState(workflow_id="wf-task-bad", request="Ops", tasks=[task])
    engine = WorkflowEngine(state)

    # PENDING cannot jump directly to COMPLETED
    with pytest.raises(InvalidTaskTransitionError):
        engine.transition_task("t-bad", TaskStatus.COMPLETED)

    # PENDING cannot jump directly to RETRYING
    with pytest.raises(InvalidTaskTransitionError):
        engine.transition_task("t-bad", TaskStatus.RETRYING)

    # Transition to RUNNING
    engine.transition_task("t-bad", TaskStatus.RUNNING)

    # RUNNING cannot jump to BLOCKED or REQUIRES_APPROVAL directly
    with pytest.raises(InvalidTaskTransitionError):
        engine.transition_task("t-bad", TaskStatus.BLOCKED)

    with pytest.raises(InvalidTaskTransitionError):
        engine.transition_task("t-bad", TaskStatus.REQUIRES_APPROVAL)


def test_approval_requirement() -> None:
    """Verify approval-gated tasks cannot execute without approval sign-off."""
    task = Task(
        task_id="t-sensitive",
        name="Dispatch Critical Email",
        requires_approval=True,
    )
    state = WorkflowState(workflow_id="wf-appr", request="Send email", tasks=[task])
    engine = WorkflowEngine(state)

    # 1. Attempting to transition directly to RUNNING without approval must fail
    with pytest.raises(TaskExecutionValidationError):
        engine.transition_task("t-sensitive", TaskStatus.RUNNING)

    # 2. Request approval (moves task to REQUIRES_APPROVAL)
    approval = engine.request_approval(action="Dispatch Critical Email", task_id="t-sensitive")
    assert task.status == TaskStatus.REQUIRES_APPROVAL

    # 3. Attempting to transition from REQUIRES_APPROVAL to RUNNING while still PENDING must fail
    with pytest.raises(TaskExecutionValidationError):
        engine.transition_task("t-sensitive", TaskStatus.RUNNING)

    # 4. Resolve approval to APPROVED
    engine.resolve_approval(approval.approval_id, approved=True, reason="Reviewed and confirmed")

    # 5. Now transitioning to RUNNING succeeds
    engine.transition_task("t-sensitive", TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING


def test_invalid_successful_tool_result() -> None:
    """Verify tool result validation rejects success=True when data is missing."""
    # success=True with data=None is invalid
    bad_result = ToolResult(tool_name="web_search", success=True, data=None)
    validation = validate_tool_result(bad_result)
    assert validation.is_valid is False
    assert "must contain data" in validation.errors[0]

    # Recording invalid tool result in engine raises ToolResultValidationError
    task = Task(task_id="t-tool", name="Search")
    state = WorkflowState(workflow_id="wf-tool-bad", request="Search", tasks=[task])
    engine = WorkflowEngine(state)

    with pytest.raises(ToolResultValidationError):
        engine.record_tool_result("t-tool", bad_result)

    # Valid result with data passes
    good_result = ToolResult(
        tool_name="web_search",
        success=True,
        data={"results": ["Found report 1"]},
    )
    assert validate_tool_result(good_result).is_valid is True
    engine.record_tool_result("t-tool", good_result)
    assert task.result == good_result


def test_completed_task_without_result() -> None:
    """Verify tasks cannot be marked COMPLETED without a valid successful result."""
    task = Task(task_id="t-comp", name="Generate Report")
    state = WorkflowState(workflow_id="wf-comp", request="Report", tasks=[task])
    engine = WorkflowEngine(state)

    engine.transition_task("t-comp", TaskStatus.RUNNING)

    # Attempting completion without any result raises TaskCompletionValidationError
    with pytest.raises(TaskCompletionValidationError):
        engine.transition_task("t-comp", TaskStatus.COMPLETED)

    # Attempting completion with a failed result raises TaskCompletionValidationError
    fail_result = ToolResult(tool_name="reporter", success=False, error="File system full")
    engine.record_tool_result("t-comp", fail_result)
    with pytest.raises(TaskCompletionValidationError):
        engine.transition_task("t-comp", TaskStatus.COMPLETED)

    # Setting a successful result allows completion
    success_result = ToolResult(
        tool_name="reporter",
        success=True,
        data={"file": "report.pdf"},
    )
    engine.record_tool_result("t-comp", success_result)
    engine.transition_task("t-comp", TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED
    assert engine.get_state().current_task is None


def test_retry_transition() -> None:
    """Verify task retry transitions and retry counter accounting."""
    task = Task(task_id="t-retry", name="API Call")
    state = WorkflowState(workflow_id="wf-retry", request="Fetch", tasks=[task])
    engine = WorkflowEngine(state)

    assert task.retry_count == 0

    # Start task
    engine.transition_task("t-retry", TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING

    # Fail to RETRYING -> count should become 1
    engine.transition_task("t-retry", TaskStatus.RETRYING)
    assert task.status == TaskStatus.RETRYING
    assert task.retry_count == 1

    # Rerun
    engine.transition_task("t-retry", TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING

    # Retry again -> count should become 2
    engine.transition_task("t-retry", TaskStatus.RETRYING)
    assert task.status == TaskStatus.RETRYING
    assert task.retry_count == 2


def test_partial_completion_state() -> None:
    """Verify workflow transitioning to PARTIALLY_COMPLETED is supported and terminal."""
    state = WorkflowState(workflow_id="wf-partial", request="Batch operations")
    engine = WorkflowEngine(state)

    engine.transition_to(WorkflowStatus.PLANNING)
    engine.transition_to(WorkflowStatus.EXECUTING)

    # Move to PARTIALLY_COMPLETED
    engine.transition_to(WorkflowStatus.PARTIALLY_COMPLETED)
    assert engine.get_state().status == WorkflowStatus.PARTIALLY_COMPLETED

    # Verify PARTIALLY_COMPLETED is terminal
    with pytest.raises(InvalidWorkflowTransitionError):
        engine.transition_to(WorkflowStatus.EXECUTING)

    with pytest.raises(InvalidWorkflowTransitionError):
        engine.transition_to(WorkflowStatus.COMPLETED)
