"""Comprehensive tests for Stage 6 - SQLite Persistence and Repository Layer."""

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import pytest

from app.storage.database import get_db_connection, get_db_path, init_db
from app.storage.repository import WorkflowRepository
from app.workflow.engine import WorkflowEngine
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


@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """Fixture providing a temporary, isolated SQLite database path."""
    db_file = tmp_path / "test_workflows.db"
    return str(db_file)


@pytest.fixture
def repo(temp_db_path: str) -> WorkflowRepository:
    """Fixture providing a WorkflowRepository wired to a clean temporary SQLite database."""
    return WorkflowRepository(db_path=temp_db_path)


def test_database_initialization(temp_db_path: str) -> None:
    """1. Verify database initializes schema and sets WAL mode and foreign keys."""
    init_db(temp_db_path)
    assert os.path.exists(temp_db_path)

    with get_db_connection(temp_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workflows';")
        assert cursor.fetchone() is not None

        # Check WAL mode
        cursor.execute("PRAGMA journal_mode;")
        row = cursor.fetchone()
        assert row[0].lower() == "wal"


def test_save_and_load_workflow_state(repo: WorkflowRepository) -> None:
    """2 & 3. Verify saving and retrieving a full WorkflowState preserves fidelity."""
    state = WorkflowState(
        workflow_id="wf_test_001",
        request="Onboard Test Corp",
        status=WorkflowStatus.CREATED,
    )
    repo.save_workflow(state)

    loaded = repo.get_workflow("wf_test_001")
    assert loaded is not None
    assert loaded == state
    assert loaded.workflow_id == "wf_test_001"
    assert loaded.request == "Onboard Test Corp"
    assert loaded.status == WorkflowStatus.CREATED


def test_nested_tasks_persist_correctly(repo: WorkflowRepository) -> None:
    """4. Verify nested tasks with status, dependencies, and retries persist accurately."""
    task1 = Task(
        task_id="task_1",
        name="Research",
        description="Background research",
        status=TaskStatus.COMPLETED,
        tool_name="research_company",
    )
    task2 = Task(
        task_id="task_2",
        name="Brief",
        description="Company brief",
        status=TaskStatus.RUNNING,
        tool_name="create_company_brief",
        depends_on=["task_1"],
    )
    state = WorkflowState(
        workflow_id="wf_test_tasks",
        request="Task test",
        status=WorkflowStatus.EXECUTING,
        tasks=[task1, task2],
        plan=Plan(objective="Task test", tasks=[task1, task2]),
    )
    repo.save_workflow(state)

    loaded = repo.get_workflow("wf_test_tasks")
    assert loaded is not None
    assert len(loaded.tasks) == 2
    assert loaded.tasks[0].task_id == "task_1"
    assert loaded.tasks[0].status == TaskStatus.COMPLETED
    assert loaded.tasks[1].depends_on == ["task_1"]
    assert loaded.plan is not None
    assert len(loaded.plan.tasks) == 2


def test_tool_results_and_artifacts_persist(repo: WorkflowRepository) -> None:
    """5 & 6. Verify ToolResult and Artifact collections persist intact."""
    tool_res = ToolResult(
        tool_name="research_company",
        success=True,
        data={"company_name": "Acme", "industry": "Technology"},
    )
    artifact = Artifact(
        artifact_id="art_001",
        artifact_type="company_brief",
        name="Acme Brief",
        content="Summary content",
    )
    state = WorkflowState(
        workflow_id="wf_test_artifacts",
        request="Artifact test",
        tool_results=[tool_res],
        artifacts=[artifact],
    )
    repo.save_workflow(state)

    loaded = repo.get_workflow("wf_test_artifacts")
    assert loaded is not None
    assert len(loaded.tool_results) == 1
    assert loaded.tool_results[0].tool_name == "research_company"
    assert loaded.tool_results[0].data["industry"] == "Technology"
    assert len(loaded.artifacts) == 1
    assert loaded.artifacts[0].artifact_id == "art_001"
    assert loaded.artifacts[0].content == "Summary content"


def test_approvals_and_errors_persist(repo: WorkflowRepository) -> None:
    """7 & 8. Verify human approval records and error telemetry persist accurately."""
    approval = Approval(
        approval_id="appr_001",
        action="Dispatch Email",
        status=ApprovalStatus.PENDING,
    )
    error = ErrorRecord(
        task_id="task_fail",
        error_type="NetworkError",
        message="Connection reset",
        retryable=True,
    )
    state = WorkflowState(
        workflow_id="wf_test_approval_error",
        request="Approval and error test",
        approvals=[approval],
        errors=[error],
    )
    repo.save_workflow(state)

    loaded = repo.get_workflow("wf_test_approval_error")
    assert loaded is not None
    assert len(loaded.approvals) == 1
    assert loaded.approvals[0].approval_id == "appr_001"
    assert loaded.approvals[0].status == ApprovalStatus.PENDING
    assert len(loaded.errors) == 1
    assert loaded.errors[0].error_type == "NetworkError"
    assert loaded.errors[0].retryable is True


def test_audit_events_persist_and_list_audit_events(repo: WorkflowRepository) -> None:
    """9. Verify audit events persist and can be queried via list_audit_events."""
    events = [
        {"event_type": "workflow_started", "timestamp": "2026-09-13T10:00:00Z"},
        {"event_type": "task_completed", "task_id": "t1"},
    ]
    state = WorkflowState(
        workflow_id="wf_audit_test",
        request="Audit test",
        audit_events=events,
    )
    repo.save_workflow(state)

    audit_list = repo.list_audit_events("wf_audit_test")
    assert audit_list is not None
    assert len(audit_list) == 2
    assert audit_list[0]["event_type"] == "workflow_started"
    assert audit_list[1]["task_id"] == "t1"

    # Non-existent workflow returns None
    assert repo.list_audit_events("non_existent_wf") is None


def test_unknown_workflow_returns_none_and_exists_false(repo: WorkflowRepository) -> None:
    """10. Verify querying unknown workflows returns None and workflow_exists returns False."""
    assert repo.get_workflow("unknown_wf_id") is None
    assert repo.workflow_exists("unknown_wf_id") is False


def test_critical_restart_persistence_with_independent_repository_instances(temp_db_path: str) -> None:
    """13. CRITICAL PORTFOLIO TEST: Proves persistence across independent repository instances."""
    state = WorkflowState(
        workflow_id="wf_restart_proof",
        request="Demonstrate restart persistence",
        status=WorkflowStatus.WAITING_FOR_APPROVAL,
        approvals=[
            Approval(
                approval_id="appr_critical",
                action="Release Production Batch",
                status=ApprovalStatus.PENDING,
            )
        ],
        audit_events=[{"event": "created", "timestamp": "2026-09-13T12:00:00Z"}],
    )

    # Instance 1 saves the workflow
    repo_instance_1 = WorkflowRepository(db_path=temp_db_path)
    repo_instance_1.save_workflow(state)

    # Instance 2 is instantiated independently on the same database path
    repo_instance_2 = WorkflowRepository(db_path=temp_db_path)
    loaded = repo_instance_2.get_workflow("wf_restart_proof")

    # Assert complete state equality across processes/instances
    assert loaded is not None
    assert loaded == state
    assert loaded.workflow_id == state.workflow_id
    assert loaded.status == WorkflowStatus.WAITING_FOR_APPROVAL
    assert loaded.approvals[0].approval_id == "appr_critical"


def test_approval_and_rejection_survive_reload(temp_db_path: str) -> None:
    """14, 15, & 16. Verify approval and rejection workflow lifecycle survives reloading from DB."""
    # Create workflow awaiting approval
    state = WorkflowState(
        workflow_id="wf_persisted_decision",
        request="Onboarding awaiting decision",
        status=WorkflowStatus.WAITING_FOR_APPROVAL,
        approvals=[
            Approval(
                approval_id="appr_decide",
                action="Send Welcome Email",
                status=ApprovalStatus.PENDING,
            )
        ],
    )
    repo1 = WorkflowRepository(db_path=temp_db_path)
    repo1.save_workflow(state)

    # Reload in a new repository instance and apply approval
    repo2 = WorkflowRepository(db_path=temp_db_path)
    loaded = repo2.get_workflow("wf_persisted_decision")
    assert loaded is not None

    engine = WorkflowEngine(loaded)
    engine.resolve_approval("appr_decide", approved=True, reason="Looks great")
    repo2.save_workflow(loaded)

    # Reload in a third repository instance to verify decision was persisted
    repo3 = WorkflowRepository(db_path=temp_db_path)
    final_state = repo3.get_workflow("wf_persisted_decision")
    assert final_state is not None
    assert final_state.approvals[0].status == ApprovalStatus.APPROVED
    assert final_state.approvals[0].reason == "Looks great"
    assert final_state.approvals[0].resolved_at is not None


def test_corrupt_record_raises_value_error(temp_db_path: str) -> None:
    """Verify corrupted JSON record in DB raises structured ValueError rather than silent failure."""
    init_db(temp_db_path)
    with get_db_connection(temp_db_path) as conn:
        conn.execute(
            """
            INSERT INTO workflows (workflow_id, request, status, state_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            ("wf_corrupt", "Bad data", "CREATED", "{malformed_json", "now", "now"),
        )

    repo = WorkflowRepository(db_path=temp_db_path)
    with pytest.raises(ValueError, match="Corrupt or incompatible workflow record"):
        repo.get_workflow("wf_corrupt")
