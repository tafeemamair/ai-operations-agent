"""Research tool for gathering company operational context."""

import re
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator
from app.workflow.state import ToolResult


# Controlled demo fixture database
CONTROLLED_FIXTURES: dict[str, dict[str, Any]] = {
    "acme corporation": {
        "company_name": "Acme Corporation",
        "website": "https://acme-corp.demo",
        "description": "Acme Corporation is a leading provider of enterprise logistics and operational automation technologies.",
        "industry": "Enterprise Software & Logistics",
        "location": "Austin, TX, USA",
        "key_facts": [
            "Founded in 2018 with over 450 employees globally.",
            "Specializes in real-time supply chain optimization and workflow integration.",
            "SOC 2 Type II certified and compliant with enterprise security standards.",
        ],
        "source_status": "controlled_demo_fixture",
    },
    "acme": {
        "company_name": "Acme Corporation",
        "website": "https://acme-corp.demo",
        "description": "Acme Corporation is a leading provider of enterprise logistics and operational automation technologies.",
        "industry": "Enterprise Software & Logistics",
        "location": "Austin, TX, USA",
        "key_facts": [
            "Founded in 2018 with over 450 employees globally.",
            "Specializes in real-time supply chain optimization and workflow integration.",
            "SOC 2 Type II certified and compliant with enterprise security standards.",
        ],
        "source_status": "controlled_demo_fixture",
    },
}


class CompanyResearchInput(BaseModel):
    """Input contract for company research."""

    company_name: str = Field(..., description="Target company name to research")

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Company name must be a non-empty string.")
        return v.strip()


class CompanyResearchOutput(BaseModel):
    """Output contract for company research."""

    company_name: str
    website: str
    description: str
    industry: str
    location: str
    key_facts: list[str] = Field(default_factory=list)
    source_status: str

    def to_tool_result(self) -> ToolResult:
        """Convert output contract to a workflow ToolResult."""
        return ToolResult(
            tool_name="research_company",
            success=True,
            data=self.model_dump(mode="json"),
        )


def _slugify(name: str) -> str:
    """Generate a simple URL/slug representation of a company name."""
    clean = re.sub(r"[^a-zA-Z0-9\s-]", "", name).strip().lower()
    return re.sub(r"[\s-]+", "-", clean) or "company"


def research_company(
    company_name: Optional[str | CompanyResearchInput] = None,
    input_data: Optional[str | CompanyResearchInput] = None,
) -> CompanyResearchOutput:
    """Execute deterministic company research from controlled demo fixtures.

    Args:
        company_name: Target company name string or CompanyResearchInput model.
        input_data: Alias for company_name for input flexibility.

    Returns:
        CompanyResearchOutput with structured company profile.

    Raises:
        ValueError: If company_name is empty or whitespace only.
    """
    raw_input = company_name if company_name is not None else input_data
    if raw_input is None:
        raise ValueError("Company name must be a non-empty string.")

    if isinstance(raw_input, str):
        validated_input = CompanyResearchInput(company_name=raw_input)
    elif isinstance(raw_input, CompanyResearchInput):
        validated_input = raw_input
    else:
        raise ValueError(f"Invalid input type: expected CompanyResearchInput or str, got {type(raw_input).__name__}")

    lookup_key = validated_input.company_name.lower().strip()

    if lookup_key in CONTROLLED_FIXTURES:
        data = CONTROLLED_FIXTURES[lookup_key]
        return CompanyResearchOutput(**data)

    # Controlled deterministic fallback for unknown companies
    slug = _slugify(validated_input.company_name)
    return CompanyResearchOutput(
        company_name=validated_input.company_name,
        website=f"https://{slug}.demo",
        description=f"Demonstration profile synthesized for {validated_input.company_name} under controlled test conditions.",
        industry="General Business Operations",
        location="Remote / Global",
        key_facts=[
            f"Synthetic operational profile generated for {validated_input.company_name}.",
            "Configured for deterministic testing and automated workflow evaluation.",
        ],
        source_status="controlled_demo_fallback",
    )


# Backward compatibility alias
execute_research = research_company
