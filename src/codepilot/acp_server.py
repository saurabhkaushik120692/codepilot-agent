"""ACP Server — Agent Communication Protocol HTTP API.

Exposes CodePilot as an ACP-compatible agent with REST endpoints
for task submission, status checking, result retrieval, and HITL
approval. Runs alongside the TUI on a configurable port.

Enabled via ACP_ENABLED=true in config.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="CodePilot ACP Server", version="1.0.0")

_active_tasks: dict[str, dict] = {}
_orchestrator: Any = None
_hitl_manager: Any = None


class TaskSubmit(BaseModel):
    description: str
    issue_number: int | None = None


class HITLApprove(BaseModel):
    action: str  # "approve" | "reject" | "inspect"


class TaskResponse(BaseModel):
    task_id: str
    status: str
    description: str


class TaskResult(BaseModel):
    task_id: str
    status: str
    diff: str | None = None
    pr_url: str | None = None


def set_orchestrator(orchestrator: Any) -> None:
    """Set the global orchestrator reference."""
    global _orchestrator
    _orchestrator = orchestrator


def set_hitl_manager(hitl: Any) -> None:
    """Set the global HITL manager reference."""
    global _hitl_manager
    _hitl_manager = hitl


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "tasks": len(_active_tasks)}


@app.post("/tasks")
async def submit_task(task: TaskSubmit) -> dict:
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not ready")

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    _active_tasks[task_id] = {
        "status": "TRIAGED",
        "description": task.description,
        "issue_number": task.issue_number,
    }

    asyncio.create_task(
        _orchestrator.handle_message(task.description, issue_id=task.issue_number)
    )

    return {
        "task_id": task_id,
        "status": "TRIAGED",
        "message": "Task submitted",
    }


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str) -> dict:
    task = _active_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task_id, **task}


@app.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str) -> dict:
    task = _active_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task_id,
        "status": task["status"],
        "diff": task.get("diff"),
        "pr_url": task.get("pr_url"),
    }


@app.post("/tasks/{task_id}/approve")
async def approve_hitl(task_id: str, body: HITLApprove) -> dict:
    if _hitl_manager is None:
        raise HTTPException(status_code=503, detail="HITL manager not available")

    try:
        action = body.action.lower()
        from codepilot.guardrails.hitl import HITLAction

        valid = action in ("approve", "reject", "inspect")
        hitl_action = HITLAction(action) if valid else HITLAction.APPROVE
        resolved = _hitl_manager.resolve(int(task_id.replace("task-", "")), hitl_action)

        if not resolved:
            raise HTTPException(status_code=404, detail="No pending HITL request")

        return {"task_id": task_id, "action": action, "resolved": True}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action")
