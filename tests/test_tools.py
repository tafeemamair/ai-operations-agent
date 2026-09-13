"""Comprehensive tests for Stage 3 - Tool contracts and deterministic tool implementations."""

import pytest
from app.tools import (
    CompanyBriefInput,
    CompanyBriefOutput,
    CompanyResearchInput,
    CompanyResearchOutput,
    create_company_brief,
    create_onboarding_checklist,
    draft_welcome_email,
    record_audit_event,
    research_company,
)
from app.workflow.state import ToolResult
from app.workflow.validation import validate_tool_result


# ============================================================================
# Research Tool Tests
# ============================================================================

def test_research_company_valid_acme() -> None:
    """Verify research_company produces expected profile for Acme Corporation."""
    result = research_company("Acme Corporation")
    assert result.company_name == "Acme Corporation"
    assert result.website == "https://acme-corp.demo"
    assert "logistics and operational automation" in result.description
    assert result.industry == "Enterprise Software & Logistics"
    assert result.location == "Austin, TX, USA"
    assert len(result.key_facts) >= 3
    assert result.source_status == "controlled_demo_fixture"


def test_research_company_empty_name_rejected() -> None:
    """Verify research_company rejects empty or whitespace-only company names."""
    with pytest.raises(ValueError, match="non-empty string"):
        research_company("")

    with pytest.raises(ValueError, match="non-empty string"):
        research_company("   ")

    with pytest.raises(ValueError):
        CompanyResearchInput(company_name="")


def test_research_company_unknown_deterministic() -> None:
    """Verify unknown companies produce deterministic fallback profiles."""
    res1 = research_company("Globex International")
    res2 = research_company("Globex International")

    assert res1.company_name == "Globex International"
    assert res1.website == "https://globex-international.demo"
    assert res1.source_status == "controlled_demo_fallback"
    assert res1.industry == "General Business Operations"
    # Determinism check
    assert res1.model_dump() == res2.model_dump()


def test_research_company_contains_required_fields_and_valid_tool_result() -> None:
    """Verify research output contains all required fields and converts to valid ToolResult."""
    result = research_company("Acme Corporation")
    data = result.model_dump()

    required_fields = [
        "company_name",
        "website",
        "description",
        "industry",
        "location",
        "key_facts",
        "source_status",
    ]
    for field in required_fields:
        assert field in data
        assert data[field] is not None

    # Verify compatibility with workflow ToolResult
    tool_res = result.to_tool_result()
    assert tool_res.tool_name == "research_company"
    assert tool_res.success is True
    assert validate_tool_result(tool_res).is_valid is True


def test_research_company_source_status_indicator() -> None:
    """Verify source_status explicitly marks results as demo/controlled fixtures."""
    acme_res = research_company("Acme Corporation")
    assert "demo" in acme_res.source_status or "controlled" in acme_res.source_status

    other_res = research_company("Wayne Enterprises")
    assert "demo" in other_res.source_status or "controlled" in other_res.source_status


# ============================================================================
# Brief Tool Tests
# ============================================================================

def test_create_company_brief_valid_research() -> None:
    """Verify valid research produces a deterministic brief with stable identifier."""
    research = research_company("Acme Corporation")
    brief1 = create_company_brief(research)
    brief2 = create_company_brief(research)

    assert brief1.company_name == "Acme Corporation"
    assert brief1.brief_id.startswith("brief_")
    # Stable identifier check across runs
    assert brief1.brief_id == brief2.brief_id
    assert "Acme Corporation" in brief1.summary
    assert brief1.industry == "Enterprise Software & Logistics"
    assert len(brief1.key_facts) >= 3

    # Verify ToolResult compatibility
    tool_res = brief1.to_tool_result()
    assert tool_res.tool_name == "create_company_brief"
    assert validate_tool_result(tool_res).is_valid is True


def test_create_company_brief_missing_data_rejected() -> None:
    """Verify create_company_brief rejects incomplete research payloads."""
    with pytest.raises(ValueError):
        create_company_brief({})

    with pytest.raises(ValueError, match="company_name"):
        create_company_brief({
            "company_name": "",
            "website": "https://test.demo",
            "description": "Test description",
            "industry": "Tech",
            "location": "Remote",
            "source_status": "demo",
        })

    with pytest.raises(ValueError, match="description"):
        create_company_brief({
            "company_name": "Test Co",
            "website": "https://test.demo",
            "description": "",
            "industry": "Tech",
            "location": "Remote",
            "source_status": "demo",
        })


def test_create_company_brief_contains_required_fields() -> None:
    """Verify generated brief contains all mandatory contract fields."""
    research = research_company("Acme Corporation")
    brief = create_company_brief(research)
    data = brief.model_dump()

    for field in ["brief_id", "company_name", "summary", "industry", "key_facts", "created_at"]:
        assert field in data
        assert data[field] is not None


# ============================================================================
# Checklist Tool Tests
# ============================================================================

def test_create_onboarding_checklist_valid() -> None:
    """Verify checklist generation from company name and brief."""
    research = research_company("Acme Corporation")
    brief = create_company_brief(research)

    checklist = create_onboarding_checklist(company_name="Acme Corporation", brief=brief)
    assert checklist.checklist_id.startswith("chk_")
    assert checklist.status == "created"
    assert len(checklist.items) == 4

    # Verify ToolResult compatibility
    tool_res = checklist.to_tool_result()
    assert tool_res.tool_name == "create_onboarding_checklist"
    assert validate_tool_result(tool_res).is_valid is True


def test_create_onboarding_checklist_items_pending() -> None:
    """Verify all checklist items are initialized with PENDING status."""
    research = research_company("Acme Corporation")
    brief = create_company_brief(research)

    checklist = create_onboarding_checklist(company_name="Acme Corporation", brief=brief)
    for item in checklist.items:
        assert item.status == "PENDING"
        assert item.item_id.startswith("chk_")
        assert len(item.title) > 0
        assert len(item.description) > 0


def test_create_onboarding_checklist_invalid_input_rejected() -> None:
    """Verify checklist generation rejects invalid company name or corrupted brief."""
    with pytest.raises(ValueError, match="non-empty string"):
        create_onboarding_checklist(company_name="")

    with pytest.raises(ValueError, match="non-empty string"):
        create_onboarding_checklist(company_name="   ")

    with pytest.raises(ValueError, match="Invalid brief"):
        create_onboarding_checklist(company_name="Acme", brief={"corrupted": True})


# ============================================================================
# Email Tool Tests
# ============================================================================

def test_draft_welcome_email_valid() -> None:
    """Verify drafting a welcome email produces structured draft for Acme."""
    research = research_company("Acme Corporation")
    brief = create_company_brief(research)

    draft = draft_welcome_email(company_name="Acme Corporation", brief=brief)
    assert draft.draft_id.startswith("draft_")
    assert draft.recipient == "operations-team@acme-corp.demo"
    assert "Acme Corporation" in draft.subject
    assert "Acme Corporation" in draft.body
    assert "Enterprise Software & Logistics" in draft.body


def test_draft_welcome_email_requires_approval_always_true() -> None:
    """Verify draft_welcome_email explicitly enforces requires_approval=True."""
    research = research_company("Acme Corporation")
    brief = create_company_brief(research)

    draft = draft_welcome_email(company_name="Acme Corporation", brief=brief)
    assert draft.requires_approval is True

    # ToolResult also encapsulates requires_approval in data
    tool_res = draft.to_tool_result()
    assert tool_res.data["requires_approval"] is True


def test_draft_welcome_email_is_strictly_draft() -> None:
    """Verify the email tool is strictly a drafting mechanism with no sending side-effects."""
    draft = draft_welcome_email(company_name="Acme Corporation")
    assert "[NOTE: This draft requires human operator approval prior to final transmission.]" in draft.body
    # Ensure no network or transmission attributes exist
    assert not hasattr(draft, "send")
    assert not hasattr(draft, "sent_at")


def test_draft_welcome_email_invalid_input_rejected() -> None:
    """Verify email tool rejects invalid company names or briefs."""
    with pytest.raises(ValueError, match="non-empty string"):
        draft_welcome_email(company_name="")

    with pytest.raises(ValueError, match="Invalid brief"):
        draft_welcome_email(company_name="Acme", brief={"bad": 123})


# ============================================================================
# Audit Tool Tests
# ============================================================================

def test_record_audit_event_valid() -> None:
    """Verify recording structured audit events."""
    event = record_audit_event(
        workflow_id="wf-100",
        event_type="tool_execution",
        actor="operations_agent",
        details={"tool_name": "research_company", "status": "completed"},
    )
    assert event.audit_event_id.startswith("audit_")
    assert event.workflow_id == "wf-100"
    assert event.event_type == "tool_execution"
    assert event.actor == "operations_agent"
    assert event.status == "recorded"
    assert event.details["tool_name"] == "research_company"
    assert len(event.timestamp) > 0

    # Verify ToolResult compatibility
    tool_res = event.to_tool_result()
    assert tool_res.tool_name == "record_audit_event"
    assert validate_tool_result(tool_res).is_valid is True


def test_record_audit_event_required_fields_validated() -> None:
    """Verify record_audit_event rejects empty required fields."""
    with pytest.raises(ValueError, match="workflow_id"):
        record_audit_event(workflow_id="", event_type="test", actor="agent")

    with pytest.raises(ValueError, match="event_type"):
        record_audit_event(workflow_id="wf-1", event_type="", actor="agent")

    with pytest.raises(ValueError, match="actor"):
        record_audit_event(workflow_id="wf-1", event_type="test", actor="")


def test_record_audit_event_deterministic_structure() -> None:
    """Verify structured fields are present and correctly typed."""
    event = record_audit_event(
        workflow_id="wf-200",
        event_type="approval_requested",
        actor="system",
        details={"item": "email_draft"},
    )
    dumped = event.model_dump()
    for field in ["audit_event_id", "workflow_id", "event_type", "actor", "details", "timestamp", "status"]:
        assert field in dumped


# ============================================================================
# Integration-Style Tool Tests
# ============================================================================

def test_tool_chain_research_to_brief_to_checklist() -> None:
    """Verify sequential tool execution: research -> brief -> checklist."""
    # 1. Research
    research_out = research_company("Acme Corporation")
    assert research_out.source_status == "controlled_demo_fixture"

    # 2. Brief
    brief_out = create_company_brief(research_out)
    assert brief_out.company_name == "Acme Corporation"
    assert "Enterprise Software & Logistics" in brief_out.summary

    # 3. Checklist
    checklist_out = create_onboarding_checklist(
        company_name=brief_out.company_name,
        brief=brief_out,
    )
    assert len(checklist_out.items) == 4
    assert all(item.status == "PENDING" for item in checklist_out.items)
    assert "Enterprise Software & Logistics" in checklist_out.items[0].description


def test_tool_chain_research_to_brief_to_email_draft() -> None:
    """Verify sequential tool execution: research -> brief -> email draft."""
    # 1. Research
    research_out = research_company("Acme Corporation")

    # 2. Brief
    brief_out = create_company_brief(research_out)

    # 3. Email Draft
    email_out = draft_welcome_email(
        company_name=brief_out.company_name,
        brief=brief_out,
    )
    assert email_out.requires_approval is True
    assert email_out.recipient == "operations-team@acme-corp.demo"
    assert "Enterprise Software & Logistics" in email_out.body
