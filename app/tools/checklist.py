"""Checklist tool for generating deterministic onboarding procedures."""

import hashlib
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator
from app.tools.documents import CompanyBriefOutput
from app.workflow.state import ToolResult


class ChecklistItem(BaseModel):
    """An individual item within an operational onboarding checklist."""

    item_id: str
    title: str
    description: str
    status: str = "PENDING"


class OnboardingChecklistInput(BaseModel):
    """Input contract for creating an onboarding checklist."""

    company_name: str
    brief: Optional[CompanyBriefOutput] = None

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Company name must be a non-empty string.")
        return v.strip()


class OnboardingChecklistOutput(BaseModel):
    """Output contract for onboarding checklist."""

    checklist_id: str
    items: list[ChecklistItem]
    status: str = "created"

    def to_tool_result(self) -> ToolResult:
        """Convert output contract to a workflow ToolResult."""
        return ToolResult(
            tool_name="create_onboarding_checklist",
            success=True,
            data=self.model_dump(mode="json"),
        )


def _generate_checklist_id(company_name: str) -> str:
    """Generate a deterministic checklist identifier."""
    clean_name = company_name.strip().lower()
    digest = hashlib.sha256(clean_name.encode("utf-8")).hexdigest()[:8]
    return f"chk_{digest}"


def create_onboarding_checklist(
    company_name: str,
    brief: Optional[CompanyBriefOutput | dict[str, Any]] = None,
) -> OnboardingChecklistOutput:
    """Generate a deterministic onboarding checklist for a client organization.

    Args:
        company_name: Name of target organization.
        brief: Optional CompanyBriefOutput or dictionary with brief context.

    Returns:
        OnboardingChecklistOutput with initial PENDING checklist items.

    Raises:
        ValueError: If company_name is missing, empty, or invalid.
    """
    if not company_name or not isinstance(company_name, str) or not company_name.strip():
        raise ValueError("Company name must be a non-empty string.")

    clean_name = company_name.strip()

    # Validate brief if provided
    industry = "Enterprise Operations"
    key_fact_reference = "standard compliance controls"
    if brief is not None:
        if isinstance(brief, dict):
            try:
                validated_brief = CompanyBriefOutput(**brief)
            except Exception as e:
                raise ValueError(f"Invalid brief dictionary: {e}") from e
        elif isinstance(brief, CompanyBriefOutput):
            validated_brief = brief
        else:
            raise ValueError(f"Invalid brief type: expected CompanyBriefOutput or dict, got {type(brief).__name__}")

        industry = validated_brief.industry or industry
        if validated_brief.key_facts:
            key_fact_reference = validated_brief.key_facts[0]

    items = [
        ChecklistItem(
            item_id="chk_1",
            title="Verify Security & Compliance Posture",
            description=f"Validate SOC 2 / compliance baseline requirements for {clean_name} ({industry}).",
            status="PENDING",
        ),
        ChecklistItem(
            item_id="chk_2",
            title="Provision Enterprise Workspace & Roles",
            description=f"Configure initial administrative tenant and role-based access for {clean_name}.",
            status="PENDING",
        ),
        ChecklistItem(
            item_id="chk_3",
            title="Coordinate Technical Integration Kickoff",
            description=f"Align technical architecture and API integration points based on: {key_fact_reference}.",
            status="PENDING",
        ),
        ChecklistItem(
            item_id="chk_4",
            title="Human Sign-off & Welcome Package Dispatch",
            description=f"Obtain operational sign-off before releasing finalized deliverables to {clean_name}.",
            status="PENDING",
        ),
    ]

    checklist_id = _generate_checklist_id(clean_name)
    return OnboardingChecklistOutput(
        checklist_id=checklist_id,
        items=items,
        status="created",
    )


# Backward compatibility alias
manage_checklist = create_onboarding_checklist
