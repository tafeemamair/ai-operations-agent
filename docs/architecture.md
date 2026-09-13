# Architecture & Design Overview

## Overview

The AI Operations Agent is an agentic business-operations system designed to convert natural-language operational requests into deterministic, validated, and auditable workflows.

## Principles

1. **Single-Agent with Tool Calling**: Rather than sprawling multi-agent architectures that add nondeterminism, a single well-scoped agent coordinates with tools, structured workflow state, and human oversight.
2. **Isolated Model Configuration**: Model selection, API keys, and parameter tuning reside exclusively in `app/agent/model.py`.
3. **Deterministic Validation**: Tool outputs and workflow state transitions are verified with deterministic Pydantic schemas and programmatic validation gates before human approval or delivery.
4. **Human in the Loop**: High-impact operational actions require human verification and explicit approval before side-effects are committed.
5. **Auditable Storage**: All operations, requests, tool executions, and approval decisions are logged in SQLite.

## Operational Lifecycle

```
[ Natural Language Request ]
            │
            ▼
     1. Understand
 (Parse intent, entities)
            │
            ▼
       2. Plan
 (Generate step sequence)
            │
            ▼
    3. Execute Tools
 (Research, docs, checklists)
            │
            ▼
      4. Validate
(Deterministic sanity checks)
            │
            ▼
   5. Human Approval
  (Review & sign-off gate)
            │
            ▼
      6. Deliver
(Finalize artifacts & notify)
            │
            ▼
       7. Audit
  (Record trail in SQLite)
```

## Modular Boundaries

- **`app/agent/`**: Encapsulates model interactions, system prompts, and agent definitions.
- **`app/tools/`**: Pure tool functions (research, document generation, checklist handling, emailing, and auditing).
- **`app/workflow/`**: State machines, workflow transitions, and deterministic validation gates.
- **`app/storage/`**: Database persistence layer using SQLite.
- **`app/api/`**: RESTful API endpoints exposing health, workflow execution, status inspection, and human approval.

## Tool Layer & Safety Invariants

The tool layer provides five discrete, independently testable business functions without LLM dependencies or unapproved side-effects:

1. **`research_company`**: Deterministic company research utilizing controlled demo fixtures (e.g. Acme Corporation) and structured fallbacks. Clearly tagged with `source_status`.
2. **`create_company_brief`**: Deterministic brief synthesis with stable artifact identifiers derived from input data.
3. **`create_onboarding_checklist`**: Structured operational checklists starting in a `PENDING` state.
4. **`draft_welcome_email`**: Strictly generates email drafts with `requires_approval=True`. It **never** dispatches emails.
5. **`record_audit_event`**: Emits structured telemetry records capturing actor, event type, and details.

## Persistence & Repository Boundary (Stage 6)

State persistence is abstracted behind `WorkflowRepository` in `app/storage/repository.py`, interacting with SQLite via parameterized queries.

### Architecture Separation

```
FastAPI Router
      ↓
Application / Workflow Orchestration
      ↓
WorkflowEngine + Deterministic Validation
      ↓
WorkflowRepository
      ↓
SQLite Database (data/workflows.db)
```

- **Zero Business Logic in Database**: The repository layer handles serialization and storage only. `WorkflowEngine` and `validation.py` remain authoritative for all state transitions, approval checks, and invariants.
- **Full State Serialization**: `WorkflowState` is serialized as a JSON document alongside indexed metadata (`workflow_id`, `request`, `status`, `created_at`, `updated_at`). This guarantees 100% fidelity for nested tasks, tool results, artifacts, approvals, error logs, and audit trails without unnecessary relational complexity.
- **Process Restart Survivability**: Workflows, pending approvals, and audit records survive process restarts and can be resumed safely across independent repository instances.
- **MVP Boundaries**: SQLite with WAL mode is designed for single-node / local operations and portfolio demonstration. No distributed consensus, multi-tenant authentication, or external database infrastructure is introduced at this stage. Real email dispatch remains strictly disabled.

## Failure Recovery & Partial Completion (Stage 7)

Workflow execution incorporates deterministic fault tolerance so that individual task failures do not unnecessarily abort unaffected operations.

### Resilience Flow

```
Tool Execution Failure
         ↓
Deterministic Classification (TRANSIENT / VALIDATION / NOT_FOUND / PERMISSION / UNKNOWN)
         ↓
Evaluate Retry Policy (TRANSIENT: up to 2 retries; Non-transient: fail-fast)
    ├── Retry Permitted → Transition RETRYING → Re-attempt Tool Execution
    └── Exhausted / Disallowed:
         ↓
Record ErrorRecord & Emit Audit Telemetry
         ↓
Transition Task to FAILED
         ↓
Block Dependent Downstream Tasks (Mark BLOCKED)
         ↓
Continue Independent Tasks (where upstream dependencies are COMPLETED)
         ↓
Evaluate Truthful Final Workflow Status (COMPLETED / PARTIALLY_COMPLETED / FAILED)
```

- **Application-Authoritative Retry Logic**: The LLM is never responsible for retry decisions. All retry policies, limits (`max_retries=2`), and state transitions are strictly governed by application logic.
- **Dependency-Aware Isolation**: If Task B fails, any task depending on B is marked `BLOCKED`, but independent tasks continue execution unimpeded.
- **Preservation of Completed Work**: Completed tasks, artifacts, tool results, and approvals are never wiped out by subsequent failures.
- **Truthful Final Status**:
  - `COMPLETED`: All planned tasks executed successfully.
  - `PARTIALLY_COMPLETED`: At least one task succeeded and at least one task failed/blocked.
  - `FAILED`: No meaningful work succeeded or critical prerequisites failed.
- **Controlled Failure Injection**: The test suite uses `FailureInjector` (`app/workflow/recovery.py`) to deterministically simulate transient timeouts and validation errors without delays, sleeps, or network calls.

