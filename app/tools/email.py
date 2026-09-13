"""Email drafting tool for operational communications.

STRICT INVARIANT: This tool ONLY creates drafts. It never dispatches or sends real emails.
"""

import hashlib
import re
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator
from app.tools.documents import CompanyBriefOutput
from app.workflow.state import ToolResult


class WelcomeEmailInput(BaseModel):
    """Input contract for drafting a welcome email."""

    company_name: str
    brief: Optional[CompanyBriefOutput] = None

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Company name must be a non-empty string.")
        return v.strip()


class WelcomeEmailOutput(BaseModel):
    """Output contract for email draft."""

    draft_id: str
    recipient: str
    subject: str
    body: str
    requires_approval: bool = Field(default=True, frozen=True)

    def to_tool_result(self) -> ToolResult:
        """Convert output contract to a workflow ToolResult."""
        return ToolResult(
            tool_name="draft_welcome_email",
            success=True,
            data=self.model_dump(mode="json"),
        )


def _slugify(name: str) -> str:
    """Generate a sanitized domain-friendly slug."""
    clean = re.sub(r"[^a-zA-Z0-9\s-]", "", name).strip().lower()
    return re.sub(r"[\s-]+", "-", clean) or "company"


def _generate_draft_id(company_name: str) -> str:
    """Generate a deterministic draft identifier."""
    clean_name = company_name.strip().lower()
    digest = hashlib.sha256(clean_name.encode("utf-8")).hexdigest()[:8]
    return f"draft_{digest}"


def draft_welcome_email(
    company_name: str,
    brief: Optional[CompanyBriefOutput | dict[str, Any]] = None,
) -> WelcomeEmailOutput:
    """Draft an operational welcome email for human review.

    CRITICAL: This function NEVER transmits email; it strictly creates a structured draft.

    Args:
        company_name: Name of recipient organization.
        brief: Optional CompanyBriefOutput or dictionary with brief context.

    Returns:
        WelcomeEmailOutput marked explicitly with requires_approval=True.

    Raises:
        ValueError: If company_name is missing or invalid.
    """
    if not company_name or not isinstance(company_name, str) or not company_name.strip():
        raise ValueError("Company name must be a non-empty string.")

    clean_name = company_name.strip()

    # Determine recipient fixture
    lower_name = clean_name.lower()
    if "acme" in lower_name:
        recipient = "operations-team@acme-corp.demo"
    else:
        slug = _slugify(clean_name)
        recipient = f"operations-team@{slug}.demo"

    # Extract brief context if provided
    industry = "Enterprise Operations"
    key_highlights = "tailored automation workflows"
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
            key_highlights = "; ".join(validated_brief.key_facts[:2])

    subject = f"Welcome to AI Operations Agent Partnership - {clean_name}"
    body = (
        f"Dear {clean_name} Operations Team,\n\n"
        f"Welcome to our operational partnership. We have finalized your onboarding profile "
        f"in the {industry} sector.\n\n"
        f"Key engagement points:\n- {key_highlights}\n\n"
        f"Our team has prepared your initial onboarding checklist and technical kickoff schedule. "
        f"Please review the attached documentation and let us know if any adjustments are needed.\n\n"
        f"Best regards,\nAI Operations Management Team\n\n"
        f"[NOTE: This draft requires human operator approval prior to final transmission.]"
    )

    draft_id = _generate_draft_id(clean_name)
    return WelcomeEmailOutput(
        draft_id=draft_id,
        recipient=recipient,
        subject=subject,
        body=body,
        requires_approval=True,
    )


# Backward compatibility alias
draft_email = draft_welcome_email
