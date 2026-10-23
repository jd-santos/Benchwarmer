"""Preview, approve, and run one bounded harness workflow from the application.

A plan freezes exactly what will run: the workflow, the input conversations
with their current revisions, the model, the limits, and any operator
instructions. Its digest is the approval token; an approval that quotes a
different digest is refused. Execution is one harness subprocess per approved
plan. The harness still talks to the API like a hand-run one, so bundles and
the run record look the same. A plan that was running when the application
stopped is marked ``interrupted`` and never rerun on its own.

This is the first slice of the bounded model-work service. It does not reserve
budget or retry; the plan's input count is its only limit, and cost is unknown
until the run reports its usage.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import os
import secrets
import subprocess
import threading
from typing import IO, Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from benchwarmer.config import BenchwarmerSettings
from benchwarmer.db import create_engine, create_session_factory
from benchwarmer.models.model_work_plan import ModelWorkPlan
from benchwarmer.services.conversation_library import (
    ConversationNotFound,
    get_conversation,
)

WORKFLOWS: tuple[str, ...] = ("propose-bundles",)
MAX_PLAN_INPUTS = 200
THINKING_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")

PlanStatus = Literal[
    "proposed", "approved", "running", "finished", "failed", "cancelled", "interrupted"
]


class PlanNotFound(LookupError):
    """No plan has the requested id."""


class PlanRequestError(ValueError):
    """The plan request names something that cannot be run."""


class PlanConflict(RuntimeError):
    """The approval did not match the plan, or the plan is not in a state for it."""


@dataclass(frozen=True)
class PlanInput:
    conversation_id: str
    revision: str
    title: str | None


@dataclass(frozen=True)
class PlanModel:
    provider: str
    model_id: str
    thinking_level: str | None


@dataclass(frozen=True)
class PlanView:
    id: str
    workflow: str
    status: str
    digest: str
    inputs: tuple[PlanInput, ...]
    model: PlanModel
    max_inputs: int
    instructions: str | None
    run_id: str | None
    exit_code: int | None
    error_summary: str | None
    created_at: dt.datetime
    approved_at: dt.datetime | None
    started_at: dt.datetime | None
    finished_at: dt.datetime | None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _canonical(plan: Mapping[str, Any]) -> bytes:
    return json.dumps(
        plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def plan_digest(plan: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(plan)).hexdigest()


def _view(row: ModelWorkPlan) -> PlanView:
    plan = row.plan
    return PlanView(
        id=row.id,
        workflow=row.workflow,
        status=row.status,
        digest=row.digest,
        inputs=tuple(
            PlanInput(item["conversation_id"], item["revision"], item.get("title"))
            for item in plan["inputs"]
        ),
        model=PlanModel(
            plan["model"]["provider"],
            plan["model"]["model_id"],
            plan["model"].get("thinking_level"),
        ),
        max_inputs=plan["limits"]["max_inputs"],
        instructions=plan.get("instructions"),
        run_id=row.run_id,
        exit_code=row.exit_code,
        error_summary=row.error_summary,
        created_at=row.created_at,
        approved_at=row.approved_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def create_plan(
    session: Session,
    *,
    workflow: str,
    conversation_ids: list[str],
    provider: str,
    model_id: str,
    thinking_level: str | None,
    instructions: str | None,
) -> PlanView:
    """Freeze a plan over the conversations' current revisions; store it as proposed."""
    if workflow not in WORKFLOWS:
        raise PlanRequestError(f"unknown workflow {workflow!r}")
    ids = list(dict.fromkeys(conversation_ids))
    if not ids:
        raise PlanRequestError("a plan needs at least one conversation")
    if len(ids) > MAX_PLAN_INPUTS:
        raise PlanRequestError(
            f"a plan may hold at most {MAX_PLAN_INPUTS} conversations"
        )
    if not provider.strip() or not model_id.strip() or "/" in provider:
        raise PlanRequestError("model must be given as provider and model id")
    if thinking_level is not None and thinking_level not in THINKING_LEVELS:
        raise PlanRequestError("unknown thinking level")
    inputs: list[dict[str, Any]] = []
    for conversation_id in ids:
        try:
            detail = get_conversation(session, conversation_id)
        except ConversationNotFound:
            raise PlanRequestError(
                f"conversation {conversation_id} is not in the library"
            ) from None
        inputs.append(
            {
                "conversation_id": detail.summary.id,
                "revision": detail.summary.revision,
                "title": detail.summary.title,
            }
        )
    cleaned = instructions.strip() if instructions else ""
    plan = {
        "schema_version": 1,
        "workflow": workflow,
        "inputs": inputs,
        "model": {
            "provider": provider.strip(),
            "model_id": model_id.strip(),
            "thinking_level": thinking_level,
        },
        "limits": {"max_inputs": len(inputs)},
        "instructions": cleaned or None,
    }
    row = ModelWorkPlan(
        id=f"plan-{secrets.token_hex(8)}",
        workflow=workflow,
        status="proposed",
        digest=plan_digest(plan),
        plan=plan,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _view(row)


def list_plans(session: Session) -> tuple[PlanView, ...]:
    rows = session.scalars(
        select(ModelWorkPlan).order_by(
            ModelWorkPlan.created_at.desc(), ModelWorkPlan.id
        )
    )
    return tuple(_view(row) for row in rows)


def get_plan(session: Session, plan_id: str) -> PlanView:
    row = session.get(ModelWorkPlan, plan_id)
    if row is None:
        raise PlanNotFound(plan_id)
    return _view(row)


def mark_interrupted(session: Session) -> int:
    """On startup: nothing is running any more, and nothing restarts on its own."""
    rows = list(
        session.scalars(select(ModelWorkPlan).where(ModelWorkPlan.status == "running"))
    )
    for row in rows:
        row.status = "interrupted"
        row.error_summary = "the application stopped while this plan was running"
        row.finished_at = _now()
        row.updated_at = _now()
    session.commit()
    return len(rows)


def harness_command(
    settings: BenchwarmerSettings, plan: PlanView, api_base_url: str
) -> list[str]:
    """The exact command an operator would have typed for this plan."""
    if settings.harness_dir is None:
        raise PlanRequestError(
            "this application cannot start harness runs; set BENCHWARMER_HARNESS_DIR"
        )
    if not (settings.harness_dir / "package.json").is_file():
        raise PlanRequestError(
            "BENCHWARMER_HARNESS_DIR does not hold the harness package"
        )
    if plan.run_id is None:
        raise PlanConflict("the plan has no run id; approve it first")
    command = [
        "npm",
        "--prefix",
        str(settings.harness_dir),
        "run",
        plan.workflow,
        "--",
        "--api",
        api_base_url,
        "--model",
        f"{plan.model.provider}/{plan.model.model_id}",
        "--run-id",
        plan.run_id,
    ]
    if plan.model.thinking_level is not None:
        command += ["--thinking", plan.model.thinking_level]
    if plan.instructions:
        command += ["--instructions", plan.instructions]
    for item in plan.inputs:
        command += ["--conversation", item.conversation_id]
    return command


class PlanRunner:
    """Runs approved plans as subprocesses and records their outcome."""

    def __init__(
        self,
        settings: BenchwarmerSettings,
        *,
        popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    ) -> None:
        self._settings = settings
        self._popen = popen
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._lock = threading.Lock()

    def _session(self) -> Session:
        engine = create_engine(self._settings)
        return create_session_factory(engine)()

    def approve_and_start(
        self, session: Session, plan_id: str, digest: str, api_base_url: str
    ) -> PlanView:
        """Bind the approval to the digest, then launch one process for the plan."""
        row = session.get(ModelWorkPlan, plan_id)
        if row is None:
            raise PlanNotFound(plan_id)
        if row.status != "proposed":
            raise PlanConflict(f"plan is {row.status}, not proposed")
        if not secrets.compare_digest(row.digest, digest):
            raise PlanConflict("the approval does not quote this plan's digest")
        # The command is checked before anything is written, so a refusal
        # leaves the plan proposed and approvable once the harness is configured.
        approved_at = _now()
        stamp = approved_at.strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3]
        run_id = f"{row.workflow}-{stamp}Z"
        preview = _view(row)
        command = harness_command(
            self._settings,
            PlanView(**{**preview.__dict__, "run_id": run_id}),
            api_base_url,
        )

        row.status = "approved"
        row.approved_at = approved_at
        row.run_id = run_id
        row.updated_at = approved_at
        session.commit()

        self._settings.initialize()
        log_dir = self._settings.logs_dir / "model-work"
        log_dir.mkdir(mode=0o700, exist_ok=True)
        log_path = log_dir / f"{row.id}.log"
        log = log_path.open("ab")
        log.write(("$ " + " ".join(command) + "\n").encode())
        log.flush()
        try:
            process = self._popen(
                command,
                cwd=str(self._settings.harness_dir),
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=dict(os.environ),
            )
        except OSError as error:
            log.close()
            row.status = "failed"
            row.error_summary = f"could not start the harness: {error}"
            row.log_path = str(log_path)
            row.finished_at = _now()
            row.updated_at = _now()
            session.commit()
            session.refresh(row)
            return _view(row)
        with self._lock:
            self._processes[row.id] = process
        started = _now()
        row.status = "running"
        row.pid = process.pid
        row.log_path = str(log_path)
        row.started_at = started
        row.updated_at = started
        session.commit()
        session.refresh(row)
        thread = threading.Thread(
            target=self._wait,
            args=(row.id, process, log),
            name=f"plan-{row.id}",
            daemon=True,
        )
        thread.start()
        return _view(row)

    def _wait(
        self, plan_id: str, process: subprocess.Popen[bytes], log: IO[bytes]
    ) -> None:
        code = process.wait()
        log.close()
        with self._lock:
            self._processes.pop(plan_id, None)
        session = self._session()
        try:
            row = session.get(ModelWorkPlan, plan_id)
            if row is None:
                return
            if row.status == "cancelled":
                pass
            elif code == 0:
                row.status = "finished"
            else:
                row.status = "failed"
                row.error_summary = (
                    f"the harness exited with status {code}; see the log"
                )
            row.exit_code = code
            row.finished_at = _now()
            row.updated_at = _now()
            session.commit()
        finally:
            session.close()

    def cancel(self, session: Session, plan_id: str) -> PlanView:
        row = session.get(ModelWorkPlan, plan_id)
        if row is None:
            raise PlanNotFound(plan_id)
        if row.status != "running":
            raise PlanConflict(f"plan is {row.status}, not running")
        with self._lock:
            process = self._processes.get(plan_id)
        row.status = "cancelled"
        row.error_summary = (
            "cancelled by the operator; work already sent may still be billed"
        )
        row.finished_at = _now()
        row.updated_at = _now()
        session.commit()
        if process is not None:
            process.terminate()
        session.refresh(row)
        return _view(row)

    def terminate_all(self) -> None:
        """Stop every tracked process; used by tests and by a clean shutdown."""
        with self._lock:
            processes = list(self._processes.values())
        for process in processes:
            process.terminate()

    def wait_all(self, timeout: float) -> None:
        """Wait for every tracked process to exit."""
        with self._lock:
            processes = list(self._processes.values())
        for process in processes:
            process.wait(timeout=timeout)
