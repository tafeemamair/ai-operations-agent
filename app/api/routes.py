"""API router defining endpoints for the AI Operations Agent service."""

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.agent.agent import OperationsAgent, create_operations_agent
from app.workflow.engine import WorkflowEngine
from app.workflow.state import (
    ApprovalStatus,
    TaskStatus,
    WorkflowState,
    WorkflowStatus,
)

router = APIRouter()

from app.storage.repository import WorkflowRepository

# Default singleton repository instance
_default_repository: Optional[WorkflowRepository] = None


def get_workflow_repository() -> WorkflowRepository:
    """Dependency provider returning the active WorkflowRepository instance."""
    global _default_repository
    if _default_repository is None:
        _default_repository = WorkflowRepository()
    return _default_repository


def get_operations_agent() -> OperationsAgent:
    """Dependency provider for OperationsAgent instance.

    Enables clean test dependency injection via app.dependency_overrides.
    """
    return create_operations_agent()


# --- Request & Response Schemas ---


class WorkflowCreateRequest(BaseModel):
    """Input payload to initiate an operations workflow."""

    request: str = Field(..., description="Natural language operations request")

    @field_validator("request")
    @classmethod
    def validate_request_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Workflow request must be a non-empty string.")
        return v.strip()


class WorkflowApprovalDecisionRequest(BaseModel):
    """Payload for approving or rejecting a pending human approval gate."""

    reason: Optional[str] = Field(default=None, description="Optional justification for decision")


class WorkflowAuditResponse(BaseModel):
    """Structured response containing workflow audit events."""

    workflow_id: str
    audit_events: list[dict[str, Any]]


# --- System Endpoints ---


@router.get("/health", tags=["System"])
@router.get("/api/health", tags=["System"])
async def health_check() -> dict[str, Any]:
    """Health check endpoint providing service status and version."""
    return {
        "status": "ok",
        "service": "ai-operations-agent",
        "version": "0.1.0",
    }


@router.get("/", tags=["System"])
async def root() -> dict[str, str]:
    """Root entry point providing service metadata."""
    return {
        "name": "AI Operations Agent",
        "description": "Agentic business-operations system",
        "docs_url": "/docs",
    }


# --- Workflow Endpoints ---


@router.post(
    "/api/workflows",
    response_model=WorkflowState,
    status_code=status.HTTP_201_CREATED,
    tags=["Workflows"],
)
def create_and_run_workflow(
    payload: WorkflowCreateRequest,
    agent: OperationsAgent = Depends(get_operations_agent),
    repo: WorkflowRepository = Depends(get_workflow_repository),
) -> WorkflowState:
    """Create and run a new operations workflow through the Operations Agent."""
    try:
        state = agent.run(payload.request)
        repo.save_workflow(state)
        return state
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow execution failed: {str(exc)}",
        ) from exc


@router.get(
    "/api/workflows/{workflow_id}",
    response_model=WorkflowState,
    tags=["Workflows"],
)
async def get_workflow(
    workflow_id: str,
    repo: WorkflowRepository = Depends(get_workflow_repository),
) -> WorkflowState:
    """Retrieve the current state of an existing operations workflow."""
    try:
        state = repo.get_workflow(workflow_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workflow from storage.",
        ) from exc

    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )
    return state


@router.post(
    "/api/workflows/{workflow_id}/approve",
    response_model=WorkflowState,
    tags=["Workflows"],
)
async def approve_workflow(
    workflow_id: str,
    payload: Optional[WorkflowApprovalDecisionRequest] = None,
    repo: WorkflowRepository = Depends(get_workflow_repository),
) -> WorkflowState:
    """Approve a pending human approval gate for the specified workflow."""
    try:
        state = repo.get_workflow(workflow_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workflow from storage.",
        ) from exc

    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )

    # Locate the active pending approval
    pending_approval = next(
        (appr for appr in state.approvals if appr.status == ApprovalStatus.PENDING),
        None,
    )

    if pending_approval is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No pending approval request found for workflow '{workflow_id}'.",
        )

    engine = WorkflowEngine(state)
    reason = payload.reason if payload else None

    # Resolve approval record
    engine.resolve_approval(pending_approval.approval_id, approved=True, reason=reason)

    # Resume workflow transitions through the engine
    if state.status == WorkflowStatus.WAITING_FOR_APPROVAL:
        engine.transition_to(WorkflowStatus.EXECUTING)

    # If all tasks are completed, advance to COMPLETED
    if all(t.status == TaskStatus.COMPLETED for t in state.tasks):
        engine.transition_to(WorkflowStatus.COMPLETED)

    engine.add_audit_event(
        event_type="approval_granted",
        details={
            "approval_id": pending_approval.approval_id,
            "action": pending_approval.action,
            "reason": reason,
        },
    )

    try:
        repo.save_workflow(state)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist workflow approval decision.",
        ) from exc

    return state


@router.post(
    "/api/workflows/{workflow_id}/reject",
    response_model=WorkflowState,
    tags=["Workflows"],
)
async def reject_workflow(
    workflow_id: str,
    payload: Optional[WorkflowApprovalDecisionRequest] = None,
    repo: WorkflowRepository = Depends(get_workflow_repository),
) -> WorkflowState:
    """Reject a pending human approval gate for the specified workflow."""
    try:
        state = repo.get_workflow(workflow_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workflow from storage.",
        ) from exc

    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )

    pending_approval = next(
        (appr for appr in state.approvals if appr.status == ApprovalStatus.PENDING),
        None,
    )

    if pending_approval is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No pending approval request found for workflow '{workflow_id}'.",
        )

    engine = WorkflowEngine(state)
    reason = payload.reason if payload else "Rejected by reviewer"

    # Resolve approval as rejected
    engine.resolve_approval(pending_approval.approval_id, approved=False, reason=reason)

    # Transition workflow to FAILED
    if state.status == WorkflowStatus.WAITING_FOR_APPROVAL:
        engine.transition_to(WorkflowStatus.FAILED)

    engine.add_audit_event(
        event_type="approval_rejected",
        details={
            "approval_id": pending_approval.approval_id,
            "action": pending_approval.action,
            "reason": reason,
        },
    )

    try:
        repo.save_workflow(state)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist workflow rejection decision.",
        ) from exc

    return state


@router.get(
    "/api/workflows/{workflow_id}/audit",
    response_model=WorkflowAuditResponse,
    tags=["Workflows"],
)
async def get_workflow_audit(
    workflow_id: str,
    repo: WorkflowRepository = Depends(get_workflow_repository),
) -> WorkflowAuditResponse:
    """Retrieve all audit trail events recorded for the specified workflow."""
    try:
        state = repo.get_workflow(workflow_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workflow audit from storage.",
        ) from exc

    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with ID '{workflow_id}' not found.",
        )

    return WorkflowAuditResponse(
        workflow_id=state.workflow_id,
        audit_events=state.audit_events,
    )
