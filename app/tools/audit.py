"""Audit logging tool for recording structured workflow provenance and decisions."""

from datetime import datetime, timezone
import hashlib
from typing import Any
from pydantic import BaseModel, Field, field_validator
from app.workflow.state import ToolResult


class AuditEventInput(BaseModel):
    """Input contract for recording an operational audit event."""

    workflow_id: str
    event_type: str
    actor: str
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("workflow_id", "event_type", "actor")
    @classmethod
    def validate_non_empty(cls, v: str, info: Any) -> str:
        if not v or not v.strip():
            raise ValueError(f"Field '{info.field_name}' must be a non-empty string.")
        return v.strip()


class AuditEventOutput(BaseModel):
    """Output contract representing a structured, persisted audit event."""

    audit_event_id: str
    workflow_id: str
    event_type: str
    actor: str
    details: dict[str, Any]
    timestamp: str
    status: str = "recorded"

    def to_tool_result(self) -> ToolResult:
        """Convert output contract to a workflow ToolResult."""
        return ToolResult(
            tool_name="record_audit_event",
            success=True,
            data=self.model_dump(mode="json"),
        )


def _generate_audit_event_id(workflow_id: str, event_type: str, timestamp: str) -> str:
    """Generate a deterministic, unique audit event identifier."""
    raw = f"{workflow_id}:{event_type}:{timestamp}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"audit_{digest}"


def record_audit_event(
    workflow_id: str,
    event_type: str,
    actor: str,
    details: dict[str, Any] | None = None,
) -> AuditEventOutput:
    """Record a structured operational audit event.

    Args:
        workflow_id: Identifier of the workflow instance.
        event_type: Classification of the event (e.g. tool_execution, approval_granted).
        actor: Entity performing or authorizing the event (e.g. agent, human_reviewer).
        details: Additional structured telemetry or payload context.

    Returns:
        AuditEventOutput with unique identifier and ISO timestamp.

    Raises:
        ValueError: If any required argument is empty or invalid.
    """
    validated_input = AuditEventInput(
        workflow_id=workflow_id,
        event_type=event_type,
        actor=actor,
        details=details if details is not None else {},
    )

    timestamp = datetime.now(timezone.utc).isoformat()
    audit_id = _generate_audit_event_id(
        validated_input.workflow_id,
        validated_input.event_type,
        timestamp,
    )

    return AuditEventOutput(
        audit_event_id=audit_id,
        workflow_id=validated_input.workflow_id,
        event_type=validated_input.event_type,
        actor=validated_input.actor,
        details=validated_input.details,
        timestamp=timestamp,
        status="recorded",
    )


# Backward compatibility alias
record_audit_entry = record_audit_event
