"""Comprehensive tests for Stage 7 - Failure Recovery + Partial Completion."""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from agents.testing.model import ScriptedModel, assistant_message, function_call

from app.agent.agent import OperationsAgent, create_operations_agent
from app.api.routes import get_operations_agent, get_workflow_repository
from app.main import app
from app.storage.repository import WorkflowRepository
from app.workflow.engine import WorkflowEngine
from app.workflow.recovery import (
    FailureCategory,
    NotFoundFailureError,
    PermissionFailureError,
    RetryPolicy,
    TransientFailureError,
    ValidationFailureError,
    classify_failure,
    failure_injector,
)
from app.workflow.state import (
    ApprovalStatus,
    ErrorRecord,
    Plan,
    Task,
    TaskStatus,
    ToolResult,
    WorkflowState,
    WorkflowStatus,
)


@pytest.fixture(autouse=True)
def clean_failure_injector():
    """Ensure failure injector is cleared before and after every test."""
    failure_injector.clear()
    yield
    failure_injector.clear()


@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """Fixture providing isolated temporary SQLite database path."""
    db_file = tmp_path / "recovery_test.db"
    return str(db_file)


@pytest.fixture
def repo(temp_db_path: str) -> WorkflowRepository:
    """Fixture providing repository wired to temporary SQLite database."""
    return WorkflowRepository(db_path=temp_db_path)


# =========================================================================
# Unit Tests: Failure Classification & Retry Policy
# =========================================================================


def test_classify_failure_transient() -> None:
    """1. Verify transient failures (timeout, service unavailable) are classified as TRANSIENT and retryable."""
    cat1, retry1 = classify_failure(TransientFailureError("Gateway Timeout"))
    assert cat1 == FailureCategory.TRANSIENT
    assert retry1 is True

    cat2, retry2 = classify_failure(TimeoutError("Connection timed out"))
    assert cat2 == FailureCategory.TRANSIENT
    assert retry2 is True

    cat3, retry3 = classify_failure("Simulated rate limit exceeded: temporarily unavailable")
    assert cat3 == FailureCategory.TRANSIENT
    assert retry3 is True


def test_classify_failure_validation() -> None:
    """5. Verify validation errors are classified as VALIDATION and are not retryable."""
    cat1, retry1 = classify_failure(ValidationFailureError("Schema mismatch"))
    assert cat1 == FailureCategory.VALIDATION
    assert retry1 is False

    cat2, retry2 = classify_failure("Invalid input: company_name must be a non-empty string")
    assert cat2 == FailureCategory.VALIDATION
    assert retry2 is False


def test_classify_failure_not_found_and_permission() -> None:
    """Verify NOT_FOUND and PERMISSION categories."""
    cat1, retry1 = classify_failure(NotFoundFailureError("Resource not found"))
    assert cat1 == FailureCategory.NOT_FOUND
    assert retry1 is False

    cat2, retry2 = classify_failure(PermissionFailureError("Unauthorized access"))
    assert cat2 == FailureCategory.PERMISSION
    assert retry2 is False


def test_classify_failure_unknown() -> None:
    """6. Verify unclassified unexpected exceptions fall back to UNKNOWN and are not retryable."""
    cat, retry = classify_failure(ArithmeticError("Zero division"))
    assert cat == FailureCategory.UNKNOWN
    assert retry is False


def test_retry_policy_bounds() -> None:
    """7. Verify retry limit (max 2) strictly prevents unbounded/infinite retry loops."""
    policy = RetryPolicy(max_retries=2)
    assert policy.should_retry(FailureCategory.TRANSIENT, current_retry_count=0) is True
    assert policy.should_retry(FailureCategory.TRANSIENT, current_retry_count=1) is True
    assert policy.should_retry(FailureCategory.TRANSIENT, current_retry_count=2) is False

    # Non-transient should never retry
    assert policy.should_retry(FailureCategory.VALIDATION, current_retry_count=0) is False
    assert policy.should_retry(FailureCategory.UNKNOWN, current_retry_count=0) is False


# =========================================================================
# State Engine & Dependency Unit Tests
# =========================================================================


def test_dependency_checking_and_blocking() -> None:
    """11. Verify can_execute_task and block_dependent_tasks handle dependencies accurately."""
    state = WorkflowState(workflow_id="wf_dep", request="Dep check")
    t1 = Task(task_id="t1", name="Task 1", status=TaskStatus.PENDING)
    t2 = Task(task_id="t2", name="Task 2", status=TaskStatus.PENDING, depends_on=["t1"])
    t3 = Task(task_id="t3", name="Task 3", status=TaskStatus.PENDING, depends_on=["t2"])
    t_ind = Task(task_id="t_ind", name="Independent Task", status=TaskStatus.PENDING, depends_on=[])

    state.tasks = [t1, t2, t3, t_ind]
    engine = WorkflowEngine(state)

    assert engine.can_execute_task("t1") is True
    assert engine.can_execute_task("t_ind") is True
    assert engine.can_execute_task("t2") is False

    # Complete t1
    t1.status = TaskStatus.COMPLETED
    assert engine.can_execute_task("t2") is True

    # Fail t2 and block dependent tasks
    t2.status = TaskStatus.FAILED
    blocked = engine.block_dependent_tasks("t2")

    assert "t3" in blocked
    assert t3.status == TaskStatus.BLOCKED
    assert t_ind.status == TaskStatus.PENDING
    assert engine.can_execute_task("t_ind") is True


def test_evaluate_final_status() -> None:
    """13 & 14. Verify evaluate_final_status computes COMPLETED, PARTIALLY_COMPLETED, and FAILED."""
    # 1. All completed
    s1 = WorkflowState(
        workflow_id="wf1",
        request="test",
        tasks=[
            Task(task_id="t1", name="T1", status=TaskStatus.COMPLETED),
            Task(task_id="t2", name="T2", status=TaskStatus.COMPLETED),
        ],
    )
    assert WorkflowEngine(s1).evaluate_final_status() == WorkflowStatus.COMPLETED

    # 2. Partially completed: 1 completed, 1 failed
    s2 = WorkflowState(
        workflow_id="wf2",
        request="test",
        tasks=[
            Task(task_id="t1", name="T1", status=TaskStatus.COMPLETED),
            Task(task_id="t2", name="T2", status=TaskStatus.FAILED),
            Task(task_id="t3", name="T3", status=TaskStatus.BLOCKED),
        ],
    )
    assert WorkflowEngine(s2).evaluate_final_status() == WorkflowStatus.PARTIALLY_COMPLETED

    # 3. Failed: 0 completed, failures present
    s3 = WorkflowState(
        workflow_id="wf3",
        request="test",
        tasks=[
            Task(task_id="t1", name="T1", status=TaskStatus.FAILED),
            Task(task_id="t2", name="T2", status=TaskStatus.BLOCKED),
        ],
    )
    assert WorkflowEngine(s3).evaluate_final_status() == WorkflowStatus.FAILED


# =========================================================================
# Critical Demo Scenarios & Execution Recovery Tests
# =========================================================================


def test_critical_demo_scenario_transient_recovery() -> None:
    """2, 3, 4, 18. CRITICAL DEMO: Onboard Acme with transient failure recovered -> COMPLETED.

    research_company fails once with a transient timeout, retries, succeeds, and workflow continues.
    """
    failure_injector.inject_transient_failure("research_company", count=1)

    agent = create_operations_agent()
    state = agent.run_deterministic("Onboard Acme Corporation.")

    # 1. First task had transient failure, retried, and succeeded
    research_task = state.tasks[0]
    assert research_task.tool_name == "research_company"
    assert research_task.status == TaskStatus.COMPLETED
    assert research_task.retry_count == 1

    # 2. Check audit trail contains required recovery telemetry
    event_types = [e["event_type"] for e in state.audit_events]
    assert "failure_classified" in event_types
    assert "task_retrying" in event_types
    assert "task_retry_succeeded" in event_types

    # 3. All subsequent tasks ran and final workflow reaches WAITING_FOR_APPROVAL for the welcome email
    brief_task = state.tasks[1]
    checklist_task = state.tasks[2]
    email_task = state.tasks[3]

    assert brief_task.status == TaskStatus.COMPLETED
    assert checklist_task.status == TaskStatus.COMPLETED
    assert email_task.status == TaskStatus.COMPLETED

    assert state.status == WorkflowStatus.WAITING_FOR_APPROVAL
    assert len(state.approvals) == 1
    assert state.approvals[0].status == ApprovalStatus.PENDING

    # 4. Approving finishes the workflow to COMPLETED via EXECUTING
    engine = WorkflowEngine(state)
    engine.resolve_approval(state.approvals[0].approval_id, approved=True)
    engine.transition_to(WorkflowStatus.EXECUTING)
    engine.transition_to(WorkflowStatus.COMPLETED)
    assert state.status == WorkflowStatus.COMPLETED


def test_critical_demo_scenario_permanent_failure_partial_completion() -> None:
    """10, 11, 12, 19. CRITICAL DEMO: Permanent failure in one branch -> PARTIALLY_COMPLETED.

    Hierarchy:
    research_company (succeeds)
        ↓
    create_company_brief (succeeds)
        ↓
    create_onboarding_checklist (fails permanently)
    and independently:
    draft_welcome_email (depends on brief, so still runs!)
    """
    failure_injector.inject_permanent_failure(
        "create_onboarding_checklist",
        category=FailureCategory.VALIDATION,
        message="Simulated checklist schema validation error",
    )

    agent = create_operations_agent()
    state = agent.run_deterministic("Onboard Acme Corporation.")

    # Task 1 & 2 succeeded
    assert state.tasks[0].status == TaskStatus.COMPLETED  # research
    assert state.tasks[1].status == TaskStatus.COMPLETED  # brief

    # Task 3 failed
    assert state.tasks[2].tool_name == "create_onboarding_checklist"
    assert state.tasks[2].status == TaskStatus.FAILED

    # Task 4 (email) depends on brief, NOT checklist, so it still executed!
    assert state.tasks[3].tool_name == "draft_welcome_email"
    assert state.tasks[3].status == TaskStatus.COMPLETED

    # Completed artifacts preserved intact
    artifact_types = [a.artifact_type for a in state.artifacts]
    assert "company_research" in artifact_types
    assert "company_brief" in artifact_types
    assert "welcome_email_draft" in artifact_types

    # ErrorRecord recorded
    assert len(state.errors) >= 1
    assert state.errors[0].task_id == state.tasks[2].task_id
    assert state.errors[0].error_type == FailureCategory.VALIDATION.value

    # Audit events verify failure classification
    event_types = [e["event_type"] for e in state.audit_events]
    assert "failure_classified" in event_types
    assert "task_failed" in event_types

    # When email is approved, workflow resolves to PARTIALLY_COMPLETED
    engine = WorkflowEngine(state)
    engine.resolve_approval(state.approvals[0].approval_id, approved=True)
    final_status = engine.evaluate_final_status()
    assert final_status == WorkflowStatus.PARTIALLY_COMPLETED


def test_retry_exhaustion_on_persistent_transient_failure() -> None:
    """7. Verify persistent transient failure exhausts max 2 retries and transitions to FAILED."""
    # Fails 5 times, but max_retries is 2
    failure_injector.inject_transient_failure("research_company", count=5)

    agent = create_operations_agent()
    state = agent.run_deterministic("Onboard Acme Corporation.")

    research_task = state.tasks[0]
    assert research_task.status == TaskStatus.FAILED
    assert research_task.retry_count == 2  # Bounded at 2 retries!

    # All downstream tasks depending on research_company are BLOCKED
    for task in state.tasks[1:]:
        assert task.status == TaskStatus.BLOCKED

    # Workflow status is FAILED (since 0 tasks completed)
    assert state.status == WorkflowStatus.FAILED

    event_types = [e["event_type"] for e in state.audit_events]
    assert "task_retry_exhausted" in event_types
    assert "workflow_failed" in event_types


def test_normal_successful_workflow_unaffected() -> None:
    """15. Verify that when failure injection is inactive, normal workflows run completely unaffected."""
    agent = create_operations_agent()
    state = agent.run_deterministic("Onboard Acme Corporation.")

    assert all(t.retry_count == 0 for t in state.tasks)
    assert len(state.errors) == 0
    assert state.tasks[0].status == TaskStatus.COMPLETED
    assert state.tasks[1].status == TaskStatus.COMPLETED
    assert state.tasks[2].status == TaskStatus.COMPLETED
    assert state.tasks[3].status == TaskStatus.COMPLETED
    assert state.status == WorkflowStatus.WAITING_FOR_APPROVAL


def test_failure_and_recovery_survive_sqlite_persistence(repo: WorkflowRepository) -> None:
    """16 & 17. Verify that failure states, retry counts, and error records survive SQLite reload."""
    failure_injector.inject_transient_failure("research_company", count=1)

    agent = create_operations_agent()
    state = agent.run_deterministic("Onboard Acme Corporation.")
    repo.save_workflow(state)

    # Reload from fresh repository instance
    reloaded = repo.get_workflow(state.workflow_id)
    assert reloaded is not None
    assert reloaded.tasks[0].retry_count == 1
    assert reloaded.tasks[0].status == TaskStatus.COMPLETED

    # Now simulate a partial failure and verify persistence
    failure_injector.inject_permanent_failure("create_company_brief")
    state2 = agent.run_deterministic("Onboard Beta Corp.")
    repo.save_workflow(state2)

    reloaded2 = repo.get_workflow(state2.workflow_id)
    assert reloaded2 is not None
    assert reloaded2.status == WorkflowStatus.PARTIALLY_COMPLETED
    assert reloaded2.tasks[0].status == TaskStatus.COMPLETED
    assert reloaded2.tasks[1].status == TaskStatus.FAILED
    assert reloaded2.tasks[2].status == TaskStatus.BLOCKED
    assert reloaded2.tasks[3].status == TaskStatus.BLOCKED
    assert len(reloaded2.errors) >= 1


# =========================================================================
# API Integration & Sanitization Tests
# =========================================================================


def test_api_workflow_exposes_truthful_recovery_state(
    client: TestClient, repo: WorkflowRepository
) -> None:
    """18, 19. Verify GET /api/workflows/{id} truthfully exposes tasks, retry counts, errors, and audit events."""
    # Setup scripted model that simulates a recovered workflow
    state = WorkflowState(
        workflow_id="wf_api_recovery",
        request="Onboard Acme Recovery",
        status=WorkflowStatus.PARTIALLY_COMPLETED,
        tasks=[
            Task(task_id="t1", name="Research", tool_name="research_company", status=TaskStatus.COMPLETED, retry_count=1),
            Task(task_id="t2", name="Brief", tool_name="create_company_brief", status=TaskStatus.FAILED, error="Invalid payload"),
            Task(task_id="t3", name="Checklist", tool_name="create_onboarding_checklist", status=TaskStatus.BLOCKED),
        ],
        errors=[
            ErrorRecord(task_id="t2", error_type="VALIDATION", message="Invalid payload", retryable=False)
        ],
        audit_events=[
            {"event_type": "failure_classified", "details": {"category": "VALIDATION"}},
            {"event_type": "workflow_partially_completed", "details": {}},
        ],
    )
    repo.save_workflow(state)

    app.dependency_overrides[get_workflow_repository] = lambda: repo

    response = client.get("/api/workflows/wf_api_recovery")
    assert response.status_code == 200
    data = response.json()

    assert data["workflow_id"] == "wf_api_recovery"
    assert data["status"] == "PARTIALLY_COMPLETED"
    assert data["tasks"][0]["retry_count"] == 1
    assert data["tasks"][1]["status"] == "FAILED"
    assert data["tasks"][2]["status"] == "BLOCKED"
    assert len(data["errors"]) == 1
    assert data["errors"][0]["error_type"] == "VALIDATION"

    # Verify no raw tracebacks are leaked
    assert "traceback" not in str(data).lower()
    app.dependency_overrides.clear()
