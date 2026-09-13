"""Comprehensive API tests for Stage 5 & 6 - FastAPI API + SQLite Workflow Orchestration."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from agents.testing.model import ScriptedModel, assistant_message, function_call

from app.agent.agent import create_operations_agent
from app.api.routes import get_operations_agent, get_workflow_repository
from app.main import app
from app.storage.repository import WorkflowRepository
from app.workflow.state import ApprovalStatus, WorkflowState, WorkflowStatus


def create_standard_mock_model() -> ScriptedModel:
    """Helper to create a standard ScriptedModel simulating the 4-step onboarding flow."""
    return ScriptedModel(steps=[
        [function_call("research_company", {"company_name": "Acme Corporation"}, call_id="c1")],
        [function_call("create_company_brief", {"company_name": "Acme Corporation"}, call_id="c2")],
        [function_call("create_onboarding_checklist", {"company_name": "Acme Corporation"}, call_id="c3")],
        [function_call("draft_welcome_email", {"company_name": "Acme Corporation"}, call_id="c4")],
        [assistant_message("Onboarding workflow prepared and email drafted for Acme Corporation.")],
    ])


@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """Provide a fresh temporary SQLite database path for isolated API test execution."""
    db_file = tmp_path / "api_workflows.db"
    return str(db_file)


@pytest.fixture
def test_repo(temp_db_path: str) -> WorkflowRepository:
    """Provide a WorkflowRepository bound to the test database."""
    return WorkflowRepository(db_path=temp_db_path)


@pytest.fixture(autouse=True)
def setup_api_test_seam(test_repo: WorkflowRepository):
    """Isolate database repository and inject scripted model seam into FastAPI."""
    mock_model = create_standard_mock_model()
    test_agent = create_operations_agent(model=mock_model)

    app.dependency_overrides[get_operations_agent] = lambda: test_agent
    app.dependency_overrides[get_workflow_repository] = lambda: test_repo
    yield
    app.dependency_overrides.clear()


def test_get_api_health(client: TestClient) -> None:
    """1. Verify GET /api/health returns 200 OK and expected status payload."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ai-operations-agent"
    assert "version" in data


def test_post_api_workflows_creates_and_runs_workflow(
    client: TestClient, test_repo: WorkflowRepository
) -> None:
    """2. Verify POST /api/workflows executes agent via test model seam, persists to SQLite, and returns state."""
    payload = {
        "request": "Onboard Acme Corporation. Research the company, prepare a company brief, create an onboarding checklist, and draft a welcome email."
    }
    response = client.post("/api/workflows", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "workflow_id" in data
    assert data["workflow_id"].startswith("wf_")
    assert data["request"] == payload["request"]
    assert data["status"] == WorkflowStatus.WAITING_FOR_APPROVAL.value

    # Plan and tasks
    assert len(data["tasks"]) == 4
    assert len(data["tool_results"]) == 4
    assert len(data["artifacts"]) == 4

    # Approvals
    assert len(data["approvals"]) == 1
    assert data["approvals"][0]["status"] == ApprovalStatus.PENDING.value
    assert "operations-team@acme-corp.demo" in data["approvals"][0]["action"]

    # Verify state was persisted in SQLite repository
    persisted = test_repo.get_workflow(data["workflow_id"])
    assert persisted is not None
    assert persisted.workflow_id == data["workflow_id"]
    assert persisted.status == WorkflowStatus.WAITING_FOR_APPROVAL


def test_get_workflow_by_id_returns_created_state(client: TestClient) -> None:
    """3. Verify GET /api/workflows/{id} returns the state of an existing workflow from SQLite."""
    post_res = client.post("/api/workflows", json={"request": "Onboard Acme Corporation."})
    assert post_res.status_code == 201
    workflow_id = post_res.json()["workflow_id"]

    get_res = client.get(f"/api/workflows/{workflow_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["workflow_id"] == workflow_id
    assert data["status"] == WorkflowStatus.WAITING_FOR_APPROVAL.value


def test_get_workflow_unknown_id_returns_404(client: TestClient) -> None:
    """4. Verify GET for a nonexistent workflow returns 404 with structured message."""
    response = client.get("/api/workflows/wf_nonexistent_12345")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


def test_approve_rejects_when_no_approval_pending(
    client: TestClient, test_repo: WorkflowRepository
) -> None:
    """5. Verify POST /api/workflows/{id}/approve rejects with 400 when no approval is pending."""
    # Persist completed workflow without pending approvals in SQLite
    state = WorkflowState(workflow_id="wf_completed", request="Finished task", status=WorkflowStatus.COMPLETED)
    test_repo.save_workflow(state)

    response = client.post("/api/workflows/wf_completed/approve")
    assert response.status_code == 400
    data = response.json()
    assert "No pending approval" in data["detail"]


def test_valid_approval_advances_workflow_and_prevents_duplicate(
    client: TestClient, test_repo: WorkflowRepository, temp_db_path: str
) -> None:
    """6. Verify valid approval marks approval resolved, transitions workflow, and persists across reloads."""
    # 1. Create onboarding workflow (halts at WAITING_FOR_APPROVAL)
    post_res = client.post("/api/workflows", json={"request": "Onboard Acme Corporation."})
    workflow_id = post_res.json()["workflow_id"]

    # 2. Approve
    approve_res = client.post(
        f"/api/workflows/{workflow_id}/approve",
        json={"reason": "Welcome email and brief verified."},
    )
    assert approve_res.status_code == 200
    data = approve_res.json()

    # Workflow advanced to COMPLETED
    assert data["status"] == WorkflowStatus.COMPLETED.value
    approval = data["approvals"][0]
    assert approval["status"] == ApprovalStatus.APPROVED.value
    assert approval["reason"] == "Welcome email and brief verified."

    # Verify decision persisted in independent repository instance
    separate_repo = WorkflowRepository(db_path=temp_db_path)
    reloaded = separate_repo.get_workflow(workflow_id)
    assert reloaded is not None
    assert reloaded.status == WorkflowStatus.COMPLETED
    assert reloaded.approvals[0].status == ApprovalStatus.APPROVED

    # 3. Duplicate approval attempt must fail with 400
    dup_res = client.post(f"/api/workflows/{workflow_id}/approve")
    assert dup_res.status_code == 400
    assert "No pending approval" in dup_res.json()["detail"]


def test_rejection_records_reason_and_transitions_workflow(
    client: TestClient, temp_db_path: str
) -> None:
    """7. Verify rejection records decision reason, transitions workflow to FAILED, and persists to DB."""
    post_res = client.post("/api/workflows", json={"request": "Onboard Acme Corporation."})
    workflow_id = post_res.json()["workflow_id"]

    reject_res = client.post(
        f"/api/workflows/{workflow_id}/reject",
        json={"reason": "Please revise the welcome email before approval."},
    )
    assert reject_res.status_code == 200
    data = reject_res.json()

    # Workflow transitioned to FAILED
    assert data["status"] == WorkflowStatus.FAILED.value
    approval = data["approvals"][0]
    assert approval["status"] == ApprovalStatus.REJECTED.value
    assert approval["reason"] == "Please revise the welcome email before approval."

    # Verify persistence across fresh repository instance
    reloaded = WorkflowRepository(db_path=temp_db_path).get_workflow(workflow_id)
    assert reloaded is not None
    assert reloaded.status == WorkflowStatus.FAILED
    assert reloaded.approvals[0].status == ApprovalStatus.REJECTED
    assert reloaded.approvals[0].reason == "Please revise the welcome email before approval."


def test_approval_and_rejection_require_existing_workflow(client: TestClient) -> None:
    """8. Verify approval and rejection on unknown workflow IDs return 404."""
    appr_res = client.post("/api/workflows/wf_unknown/approve")
    assert appr_res.status_code == 404

    rej_res = client.post("/api/workflows/wf_unknown/reject")
    assert rej_res.status_code == 404


def test_get_workflow_audit_returns_events(client: TestClient) -> None:
    """9. Verify GET /api/workflows/{id}/audit returns structured audit telemetry from SQLite."""
    post_res = client.post("/api/workflows", json={"request": "Onboard Acme Corporation."})
    workflow_id = post_res.json()["workflow_id"]

    # Approve to add approval_granted audit event
    client.post(f"/api/workflows/{workflow_id}/approve", json={"reason": "Signed off"})

    audit_res = client.get(f"/api/workflows/{workflow_id}/audit")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()

    assert audit_data["workflow_id"] == workflow_id
    assert "audit_events" in audit_data
    events = audit_data["audit_events"]
    assert len(events) >= 1

    event_types = [e["event_type"] for e in events]
    assert "approval_granted" in event_types

    # Unknown ID returns 404
    assert client.get("/api/workflows/wf_missing/audit").status_code == 404


def test_api_errors_are_structured_no_stack_traces(client: TestClient) -> None:
    """10. Verify validation errors and 404s return clean JSON without exposing stack traces."""
    # Validation error on empty request
    empty_res = client.post("/api/workflows", json={"request": ""})
    assert empty_res.status_code in (400, 422)
    empty_data = empty_res.json()
    assert "detail" in empty_data
    assert "traceback" not in str(empty_data).lower()

    # 404 error
    not_found = client.get("/api/workflows/missing")
    assert not_found.status_code == 404
    not_found_data = not_found.json()
    assert "detail" in not_found_data
    assert "traceback" not in str(not_found_data).lower()
