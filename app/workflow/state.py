"""Workflow state definitions and schemas."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    """Lifecycle status of an operations workflow."""

    CREATED = "CREATED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"


class TaskStatus(str, Enum):
    """Status of an individual workflow task."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    BLOCKED = "BLOCKED"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"


# Backward compatibility alias
StepStatus = TaskStatus


class ApprovalStatus(str, Enum):
    """Status of a human approval request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ToolResult(BaseModel):
    """Execution output from a discrete operational tool."""

    tool_name: str
    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class Artifact(BaseModel):
    """Generated deliverable or operational artifact."""

    artifact_id: str
    artifact_type: str
    name: str
    content: Optional[str] = None
    reference: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Approval(BaseModel):
    """Human-in-the-loop approval record for high-impact actions."""

    approval_id: str
    action: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    reason: Optional[str] = None


class ErrorRecord(BaseModel):
    """Structured error information capturing failure telemetry."""

    task_id: Optional[str] = None
    error_type: str
    message: str
    retryable: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Task(BaseModel):
    """Represents an actionable operational task inside a plan."""

    task_id: str
    name: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    tool_name: Optional[str] = None
    depends_on: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    result: Optional[ToolResult] = None
    error: Optional[str] = None
    retry_count: int = 0


class Plan(BaseModel):
    """Operational execution plan decomposed from natural-language request."""

    objective: str
    tasks: list[Task] = Field(default_factory=list)


class WorkflowState(BaseModel):
    """Complete state snapshot for a business operations workflow."""

    workflow_id: str
    request: str
    status: WorkflowStatus = WorkflowStatus.CREATED
    plan: Optional[Plan] = None
    tasks: list[Task] = Field(default_factory=list)
    current_task: Optional[str] = None
    tool_results: list[ToolResult] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)
    errors: list[ErrorRecord] = Field(default_factory=list)
    audit_events: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
