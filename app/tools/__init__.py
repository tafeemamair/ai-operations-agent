"""Operational tools package for the AI Operations Agent."""

from app.tools.research import (
    CompanyResearchInput,
    CompanyResearchOutput,
    execute_research,
    research_company,
)
from app.tools.documents import (
    CompanyBriefInput,
    CompanyBriefOutput,
    create_company_brief,
    generate_document,
)
from app.tools.checklist import (
    ChecklistItem,
    OnboardingChecklistInput,
    OnboardingChecklistOutput,
    create_onboarding_checklist,
    manage_checklist,
)
from app.tools.email import (
    WelcomeEmailInput,
    WelcomeEmailOutput,
    draft_email,
    draft_welcome_email,
)
from app.tools.audit import (
    AuditEventInput,
    AuditEventOutput,
    record_audit_entry,
    record_audit_event,
)

__all__ = [
    # Primary Stage 3 Tools
    "research_company",
    "create_company_brief",
    "create_onboarding_checklist",
    "draft_welcome_email",
    "record_audit_event",
    # Contracts & Models
    "CompanyResearchInput",
    "CompanyResearchOutput",
    "CompanyBriefInput",
    "CompanyBriefOutput",
    "ChecklistItem",
    "OnboardingChecklistInput",
    "OnboardingChecklistOutput",
    "WelcomeEmailInput",
    "WelcomeEmailOutput",
    "AuditEventInput",
    "AuditEventOutput",
    # Backward compatibility aliases
    "execute_research",
    "generate_document",
    "manage_checklist",
    "draft_email",
    "record_audit_entry",
]
