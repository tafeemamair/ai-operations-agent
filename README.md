# AI Operations Agent

An agentic business-operations system that converts natural-language requests into planned, tool-driven workflows with deterministic validation, human approval, failure recovery, and auditable execution.

## Locked Technology Stack

- **Runtime & Language**: Python 3.11+
- **API Framework**: FastAPI
- **Agent Framework**: OpenAI Agents SDK for Python (`openai-agents`)
- **Validation & Schemas**: Pydantic v2
- **Persistence**: SQLite
- **Testing**: pytest
- **CI/CD**: GitHub Actions
- **Frontend (planned)**: Next.js / React

## Core Workflow

```
Request → Understand → Plan → Execute Tools → Validate → Human Approval → Deliver → Audit
```

1. **Request**: Ingest natural language business operations request.
2. **Understand**: Parse intent, extract entities, identify objectives and constraints.
3. **Plan**: Formulate structured step-by-step action plan.
4. **Execute Tools**: Run discrete operational tools (research, doc gen, checklist, email, audit).
5. **Validate**: Deterministically check outputs against requirements and quality gates.
6. **Human Approval**: Request human sign-off for critical actions before final execution.
7. **Deliver**: Emit finalized deliverables and notifications.
8. **Audit**: Log complete provenance, telemetry, and decision trails into SQLite.

## Repository Structure

```
ai-operations-agent/
├── app/
│   ├── agent/
│   │   ├── agent.py         # Agent orchestration & workflow binding
│   │   ├── instructions.py  # System prompts & operational instructions
│   │   └── model.py         # Isolated model provider configuration
│   ├── tools/
│   │   ├── research.py      # Market & internal research tools
│   │   ├── documents.py     # Document generation & parsing
│   │   ├── checklist.py     # Task & checklist management
│   │   ├── email.py         # Communication & drafting
│   │   └── audit.py         # Execution trail logging
│   ├── workflow/
│   │   ├── state.py         # Workflow state machine & Pydantic models
│   │   ├── engine.py        # Workflow execution coordinator
│   │   └── validation.py    # Deterministic output verification gates
│   ├── api/
│   │   └── routes.py        # FastAPI route definitions (health & operations)
│   ├── storage/
│   │   └── database.py      # SQLite connection & schema management
│   └── main.py              # Application entrypoint
├── tests/
│   ├── conftest.py          # Pytest fixtures & test clients
│   └── test_health.py       # Health check & smoke tests
├── docs/
│   └── architecture.md      # Architectural design document
├── .github/
│   └── workflows/
│       └── ci.yml           # Automated CI pipeline
├── README.md
├── pyproject.toml
├── .env.example
└── .gitignore
```

## Getting Started

### 1. Setup Environment

```bash
# Create virtual environment with Python 3.11+
python -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install dependencies including development tools
pip install -e ".[dev]"
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Set your `OPENAI_API_KEY` in `.env`.

### 3. Run Tests

```bash
pytest
```

### 4. Run Development Server

```bash
uvicorn app.main:app --reload --port 8000
```

Access the API documentation at `http://localhost:8000/docs` and health check at `http://localhost:8000/api/health`.

## Storage & Persistence (Stage 6)

The system persists workflow executions, pending approval gates, and audit logs using SQLite via `WorkflowRepository` (`app/storage/repository.py`).

- **Configurable Location**: Set via `WORKFLOW_DATABASE_PATH` in `.env` (default: `data/workflows.db`).
- **Process Restart Durability**: Workflows, tasks, artifacts, and approval decisions survive application restarts.
- **Strict Boundary**: Business logic and validation remain in `WorkflowEngine`; SQLite is used purely as an atomic persistence layer.
- **Current Scope**: Optimized for local development and portfolio demonstration using WAL-mode SQLite. Authentication, multi-tenancy, and real email sending remain disabled for safety.

## Failure Recovery & Partial Completion (Stage 7)

- **Deterministic Failure Classification**: Categorizes errors into `TRANSIENT`, `VALIDATION`, `NOT_FOUND`, `PERMISSION`, and `UNKNOWN`.
- **Bounded Retries**: Transient failures automatically retry up to 2 times; permanent/validation errors fail fast.
- **Dependency Isolation**: Upstream task failures block directly and transitively dependent tasks while allowing independent parallel tasks to continue.
- **Truthful Workflow Status**: Produces `COMPLETED`, `PARTIALLY_COMPLETED`, or `FAILED` without discarding successful artifacts or tool outputs.
- **Controlled Test Seam**: Deterministic `FailureInjector` simulates failures without sleeps or random behavior.
