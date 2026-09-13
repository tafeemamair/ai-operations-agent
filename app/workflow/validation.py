"""Deterministic validation logic and quality gates for workflow states, tasks, and tools."""

from typing import Optional
from pydantic import BaseModel, Field
from app.workflow.state import (
    Approval,
    ApprovalStatus,
    Task,
    TaskStatus,
    ToolResult,
    WorkflowStatus,
)


class WorkflowValidationError(Exception):
    """Base application exception for workflow validation errors."""


class InvalidWorkflowTransitionError(WorkflowValidationError):
    """Raised when an illegal workflow state transition is attempted."""


class InvalidTaskTransitionError(WorkflowValidationError):
    """Raised when an illegal task state transition is attempted."""


class TaskExecutionValidationError(WorkflowValidationError):
    """Raised when an approval-gated task attempts execution without approval."""


class TaskCompletionValidationError(WorkflowValidationError):
    """Raised when a task attempts to complete without a valid result."""


class ToolResultValidationError(WorkflowValidationError):
    """Raised when a tool result payload is malformed or missing required data."""


class TaskFieldValidationError(WorkflowValidationError):
    """Raised when a task is missing mandatory fields."""


class ValidationResult(BaseModel):
    """Result of deterministic validation checks."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# Deterministic state transition mapping for workflows
VALID_WORKFLOW_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.CREATED: {
        WorkflowStatus.PLANNING,
    },
    WorkflowStatus.PLANNING: {
        WorkflowStatus.EXECUTING,
    },
    WorkflowStatus.EXECUTING: {
        WorkflowStatus.WAITING_FOR_APPROVAL,
        WorkflowStatus.COMPLETED,
        WorkflowStatus.PARTIALLY_COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.EXECUTING,  # Self-loop for iterative task dispatching
    },
    WorkflowStatus.WAITING_FOR_APPROVAL: {
        WorkflowStatus.EXECUTING,
        WorkflowStatus.FAILED,
    },
    WorkflowStatus.COMPLETED: set(),
    WorkflowStatus.PARTIALLY_COMPLETED: set(),
    WorkflowStatus.FAILED: set(),
}

# Deterministic state transition mapping for tasks
VALID_TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {
        TaskStatus.RUNNING,
        TaskStatus.BLOCKED,
        TaskStatus.REQUIRES_APPROVAL,
    },
    TaskStatus.RUNNING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.RETRYING,
    },
    TaskStatus.RETRYING: {
        TaskStatus.RUNNING,
    },
    TaskStatus.REQUIRES_APPROVAL: {
        TaskStatus.RUNNING,
        TaskStatus.BLOCKED,
    },
    TaskStatus.BLOCKED: set(),
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
}


def validate_workflow_transition(
    current_status: WorkflowStatus,
    next_status: WorkflowStatus,
) -> ValidationResult:
    """Validate whether transitioning from current_status to next_status is permitted."""
    allowed = VALID_WORKFLOW_TRANSITIONS.get(current_status, set())
    if next_status in allowed:
        return ValidationResult(is_valid=True)
    return ValidationResult(
        is_valid=False,
        errors=[
            f"Invalid workflow transition: cannot move from {current_status.value} to {next_status.value}."
        ],
    )


def ensure_valid_workflow_transition(
    current_status: WorkflowStatus,
    next_status: WorkflowStatus,
) -> None:
    """Raise InvalidWorkflowTransitionError if transition is illegal."""
    result = validate_workflow_transition(current_status, next_status)
    if not result.is_valid:
        raise InvalidWorkflowTransitionError(result.errors[0])


def validate_task_transition(
    current_status: TaskStatus,
    next_status: TaskStatus,
) -> ValidationResult:
    """Validate whether transitioning a task from current_status to next_status is permitted."""
    allowed = VALID_TASK_TRANSITIONS.get(current_status, set())
    if next_status in allowed:
        return ValidationResult(is_valid=True)
    return ValidationResult(
        is_valid=False,
        errors=[
            f"Invalid task transition: cannot move from {current_status.value} to {next_status.value}."
        ],
    )


def ensure_valid_task_transition(
    current_status: TaskStatus,
    next_status: TaskStatus,
) -> None:
    """Raise InvalidTaskTransitionError if task transition is illegal."""
    result = validate_task_transition(current_status, next_status)
    if not result.is_valid:
        raise InvalidTaskTransitionError(result.errors[0])


def validate_task_fields(task: Task) -> ValidationResult:
    """Validate that mandatory task fields are populated and valid."""
    errors: list[str] = []
    if not task.task_id or not task.task_id.strip():
        errors.append("Task 'task_id' must be a non-empty string.")
    if not task.name or not task.name.strip():
        errors.append("Task 'name' must be a non-empty string.")
    if task.retry_count < 0:
        errors.append("Task 'retry_count' cannot be negative.")
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def ensure_valid_task_fields(task: Task) -> None:
    """Raise TaskFieldValidationError if required task fields are invalid."""
    result = validate_task_fields(task)
    if not result.is_valid:
        raise TaskFieldValidationError("; ".join(result.errors))


def validate_tool_result(result: ToolResult) -> ValidationResult:
    """Validate that a tool result conforms to deterministic invariants."""
    errors: list[str] = []
    if result.success:
        if result.data is None:
            errors.append(f"Successful result for tool '{result.tool_name}' must contain data.")
        elif not isinstance(result.data, dict):
            errors.append(f"Tool '{result.tool_name}' data must be a dictionary.")
    else:
        if not result.error or not result.error.strip():
            errors.append(f"Failed result for tool '{result.tool_name}' must contain an error description.")
    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def ensure_valid_tool_result(result: ToolResult) -> None:
    """Raise ToolResultValidationError if tool result is malformed."""
    validation = validate_tool_result(result)
    if not validation.is_valid:
        raise ToolResultValidationError("; ".join(validation.errors))


def validate_task_execution(
    task: Task,
    approvals: Optional[list[Approval]] = None,
) -> ValidationResult:
    """Validate that approval-gated tasks have received human sign-off before running."""
    if not task.requires_approval:
        return ValidationResult(is_valid=True)

    approvals = approvals or []
    # Check if there is an approved Approval matching this task
    has_approval = any(
        appr.status == ApprovalStatus.APPROVED
        and (appr.action == task.name or appr.approval_id == task.task_id or appr.action == task.task_id)
        for appr in approvals
    )

    if not has_approval:
        return ValidationResult(
            is_valid=False,
            errors=[
                f"Task '{task.task_id}' ('{task.name}') is approval-gated and cannot execute without an approved sign-off."
            ],
        )
    return ValidationResult(is_valid=True)


def ensure_task_execution_valid(
    task: Task,
    approvals: Optional[list[Approval]] = None,
) -> None:
    """Raise TaskExecutionValidationError if approval requirement is unfulfilled."""
    result = validate_task_execution(task, approvals)
    if not result.is_valid:
        raise TaskExecutionValidationError(result.errors[0])


def validate_task_completion(task: Task) -> ValidationResult:
    """Validate that completed tasks have a successful result containing required data."""
    if task.result is None:
        return ValidationResult(
            is_valid=False,
            errors=[f"Task '{task.task_id}' cannot be marked COMPLETED without a result."],
        )

    if not task.result.success:
        return ValidationResult(
            is_valid=False,
            errors=[f"Task '{task.task_id}' cannot be marked COMPLETED with an unsuccessful result."],
        )

    tool_res_validation = validate_tool_result(task.result)
    if not tool_res_validation.is_valid:
        return ValidationResult(
            is_valid=False,
            errors=tool_res_validation.errors,
        )

    return ValidationResult(is_valid=True)


def ensure_task_completion_valid(task: Task) -> None:
    """Raise TaskCompletionValidationError if task completion requirements are not met."""
    result = validate_task_completion(task)
    if not result.is_valid:
        raise TaskCompletionValidationError(result.errors[0])
