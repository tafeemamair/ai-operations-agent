"""Document generation tool for assembling operational company briefs."""

from datetime import datetime, timezone
import hashlib
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator
from app.tools.research import CompanyResearchOutput, research_company
from app.workflow.state import ToolResult


class CompanyBriefInput(BaseModel):
    """Input contract for company brief generation."""

    research_data: CompanyResearchOutput


class CompanyBriefOutput(BaseModel):
    """Output contract for company operational brief."""

    brief_id: str
    company_name: str
    summary: str
    industry: str
    key_facts: list[str] = Field(default_factory=list)
    created_at: str

    def to_tool_result(self) -> ToolResult:
        """Convert output contract to a workflow ToolResult."""
        return ToolResult(
            tool_name="create_company_brief",
            success=True,
            data=self.model_dump(mode="json"),
        )


def _generate_brief_id(company_name: str) -> str:
    """Generate a stable, deterministic brief identifier based on company name."""
    clean_name = company_name.strip().lower()
    digest = hashlib.sha256(clean_name.encode("utf-8")).hexdigest()[:8]
    return f"brief_{digest}"


def create_company_brief(
    research_data: Optional[CompanyResearchOutput | CompanyBriefInput | dict[str, Any]] = None,
    company_name: Optional[str] = None,
) -> CompanyBriefOutput:
    """Deterministically synthesize an operational company brief from research data.

    Args:
        research_data: Validated research output model or dictionary.
        company_name: Target company name if research_data is not directly provided.

    Returns:
        CompanyBriefOutput with structured brief and stable identifier.

    Raises:
        ValueError: If research data is missing, empty, or invalid.
    """
    if research_data is None and company_name is not None:
        research_data = research_company(company_name)

    if research_data is None:
        raise ValueError("Research data or company_name is required to create a company brief.")

    # Normalize input
    if isinstance(research_data, CompanyBriefInput):
        data = research_data.research_data
    elif isinstance(research_data, CompanyResearchOutput):
        data = research_data
    elif isinstance(research_data, dict):
        try:
            data = CompanyResearchOutput(**research_data)
        except Exception as e:
            raise ValueError(f"Invalid research data dictionary: {e}") from e
    else:
        raise ValueError(
            f"Invalid input type: expected CompanyResearchOutput, CompanyBriefInput, or dict, got {type(research_data).__name__}"
        )

    # Validate essential fields
    if not data.company_name or not data.company_name.strip():
        raise ValueError("Research data missing required 'company_name'.")
    if not data.description or not data.description.strip():
        raise ValueError("Research data missing required 'description'.")
    if not data.industry or not data.industry.strip():
        raise ValueError("Research data missing required 'industry'.")

    # Generate deterministic summary without LLM
    facts_overview = "; ".join(data.key_facts[:2]) if data.key_facts else "Standard operational profile."
    summary = (
        f"{data.company_name} operates in the {data.industry} sector. "
        f"{data.description} Core highlights include: {facts_overview}"
    )

    brief_id = _generate_brief_id(data.company_name)
    timestamp = datetime.now(timezone.utc).isoformat()

    return CompanyBriefOutput(
        brief_id=brief_id,
        company_name=data.company_name,
        summary=summary,
        industry=data.industry,
        key_facts=list(data.key_facts),
        created_at=timestamp,
    )


# Backward compatibility alias
generate_document = create_company_brief
