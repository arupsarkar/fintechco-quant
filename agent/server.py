"""FastAPI service for the SDK agent path.

Usage:
    uv run uvicorn agent.server:app --port 8000
    curl -X POST http://localhost:8000/analyze \
         -H 'Content-Type: application/json' \
         -d '{"request": "Perform the Fed policy volatility analysis per the spec.", "role": "analyst"}'
"""

import json
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent.orchestrator import run_analysis_agent
from agent.tools import VALID_ROLES

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="FinTechCo Quant Agent",
    description="Governed quantitative analysis via Claude Agent SDK",
)


class AnalyzeRequest(BaseModel):
    request: str
    role: str = "analyst"
    model: str = "claude-sonnet-4-20250514"


class AnalyzeResponse(BaseModel):
    output: str
    session_id: str
    turns: int
    input_tokens: int
    output_tokens: int
    tool_calls: int
    governance_violations: int


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    if req.role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role. Must be one of: {VALID_ROLES}")

    result = run_analysis_agent(
        request=req.request,
        role=req.role,
        model=req.model,
    )

    return AnalyzeResponse(
        output=result.output,
        session_id=result.session_id,
        turns=result.turns,
        input_tokens=result.usage["input_tokens"],
        output_tokens=result.usage["output_tokens"],
        tool_calls=len(result.tool_calls),
        governance_violations=result.governance_violations,
    )


@app.get("/health")
def health():
    """Gateway selftest + golden verification."""
    golden = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_golden.py")],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return {
        "status": "healthy" if golden.returncode == 0 else "unhealthy",
        "golden_verified": golden.returncode == 0,
        "golden_message": golden.stdout.strip(),
    }


@app.get("/audit")
def audit(n: int = 20):
    """Return the last N audit log entries."""
    audit_path = ROOT / "audit" / "audit_log.jsonl"
    if not audit_path.exists():
        return {"entries": []}
    lines = audit_path.read_text().strip().splitlines()
    recent = lines[-n:] if len(lines) > n else lines
    return {"entries": [json.loads(line) for line in recent]}
