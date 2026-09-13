"""SQLite repository implementation for WorkflowState persistence."""

from datetime import datetime, timezone
from typing import Any, Optional

from app.storage.database import get_db_connection, init_db
from app.workflow.state import WorkflowState


class WorkflowRepository:
    """Repository managing SQLite persistence for WorkflowState instances."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path
        init_db(self.db_path)

    def save_workflow(self, state: WorkflowState) -> None:
        """Persist or update a WorkflowState in SQLite.

        Uses an atomic upsert transaction preserving full domain model fidelity.
        """
        state_json = state.model_dump_json()
        now_str = datetime.now(timezone.utc).isoformat()
        created_str = state.created_at.isoformat() if state.created_at else now_str
        updated_str = state.updated_at.isoformat() if state.updated_at else now_str

        status_str = state.status.value if hasattr(state.status, "value") else str(state.status)

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO workflows (workflow_id, request, status, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id) DO UPDATE SET
                    request=excluded.request,
                    status=excluded.status,
                    state_json=excluded.state_json,
                    updated_at=excluded.updated_at;
                """,
                (
                    state.workflow_id,
                    state.request,
                    status_str,
                    state_json,
                    created_str,
                    updated_str,
                ),
            )

    def create_workflow(self, state: WorkflowState) -> None:
        """Create a workflow in SQLite."""
        self.save_workflow(state)

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowState]:
        """Retrieve and deserialize a WorkflowState by workflow_id."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT state_json FROM workflows WHERE workflow_id = ?;",
                (workflow_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            try:
                return WorkflowState.model_validate_json(row["state_json"])
            except Exception as exc:
                raise ValueError(
                    f"Corrupt or incompatible workflow record for '{workflow_id}': {exc}"
                ) from exc

    def workflow_exists(self, workflow_id: str) -> bool:
        """Return True if a workflow exists in SQLite, False otherwise."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM workflows WHERE workflow_id = ?;",
                (workflow_id,),
            )
            return cursor.fetchone() is not None

    def list_audit_events(self, workflow_id: str) -> Optional[list[dict[str, Any]]]:
        """Retrieve audit events associated with the workflow."""
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            return None
        return workflow.audit_events

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow from SQLite."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM workflows WHERE workflow_id = ?;",
                (workflow_id,),
            )
            return cursor.rowcount > 0
