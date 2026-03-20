"""
TestGPT — FastAPI Endpoint (Step 1)
Accepts a user query, calls TestGPTAgent, returns narrative + Vega specs + issues.

Run:  uvicorn api.main:app --reload --port 8000
Test: curl -X POST http://localhost:8000/chat -H 'Content-Type: application/json' \
        -d '{"user_id": "USR-001", "message": "How is my business?"}'
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from api.auth import api_key_middleware
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional

from config.settings import DB_URL, SYNTHETIC_DATA_MODE
from agents.testgpt_agent import TestGPTAgent
from tools.kpi_tools import search_memory

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TestGPT API",
    description="AI analyst agent for CPG retail analytics — powered by Claude",
    version="0.1.0-prototype",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(api_key_middleware)

# Serve chat UI
_public = Path(__file__).parent.parent / "public"
if _public.exists():
    app.mount("/static", StaticFiles(directory=str(_public)), name="static")

@app.get("/")
def root():
    return FileResponse(str(_public / "index.html"))

# ─── DB Session Dependency ────────────────────────────────────────────────────
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── In-memory session store (prototype only) ─────────────────────────────────
# TODO: Replace with Redis or DB-backed session store
_agent_sessions: dict[str, TestGPTAgent] = {}


# ─── Request / Response Models ────────────────────────────────────────────────
class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: Optional[str] = None   # Omit for new session; provide to continue


class ApprovalRequest(BaseModel):
    user_id: str
    approval_id: str
    outcome: str   # "approved" | "edited" | "rejected"
    edited_payload: Optional[dict] = None
    rejection_reason: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    narrative: str
    charts: list          # List of Vega-Lite specs
    issues: list          # Flagged issues for issue queue
    pending_approval: Optional[dict]
    has_approval_gate: bool
    synthetic_data: bool


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "prototype": SYNTHETIC_DATA_MODE}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    """
    Main chat endpoint. Accepts a user query, returns analyst response.

    Steps:
    1. Resolve or create agent session for this user
    2. Load user preferences from DB (shapes narrative mode and default summary)
    3. Run TestGPTAgent.chat()
    4. Return narrative + charts + issues + any pending HITL gate
    """
    # TODO: Validate user_id against auth system (JWT/session token)
    # TODO: Enforce user data scope — reject if user_id not authorized

    session_key = req.session_id or req.user_id

    # Resolve or create agent session
    if session_key not in _agent_sessions:
        user_ctx = _resolve_user_context(db, req.user_id)
        _agent_sessions[session_key] = TestGPTAgent(session=db, user_context=user_ctx)

    agent = _agent_sessions[session_key]
    # Always refresh the DB session — FastAPI creates a new one per request
    # and the cached agent holds a stale session from the prior request
    agent.session = db

    try:
        import traceback
        response = agent.chat(req.message)
    except Exception as e:
        # Log full traceback for debugging
        print(f"[ERROR] Agent error for session {session_key}:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    return ChatResponse(
        session_id=session_key,
        **response.to_dict(),
        synthetic_data=SYNTHETIC_DATA_MODE,
    )


@app.post("/approve")
def approve(req: ApprovalRequest, db: Session = Depends(get_db)):
    """
    HITL approval endpoint. User approves, edits, or rejects a pending action.

    On approval: execute the action
    On edit: re-surface with changes for secondary approval (if action type warrants)
    On rejection: log reason, discard action

    TODO: Implement actual action execution per action_type
    TODO: Persist outcome as training signal for model improvement
    """
    # TODO: Look up pending approval by approval_id
    # TODO: Execute action or discard based on outcome
    # TODO: Log outcome with diff (if edited)

    return {
        "approval_id": req.approval_id,
        "outcome": req.outcome,
        "status": "logged",
        "message": f"Approval '{req.outcome}' recorded. Full execution not yet implemented.",
    }


@app.get("/issues")
def get_issues(user_id: str, db: Session = Depends(get_db)):
    """
    Return open/acknowledged issues for the user's scope.
    TODO: Filter by user's retailer_scope and region_scope.
    """
    from models.queries import open_alerts_for_user
    user_ctx = _resolve_user_context(db, user_id)
    retailers = [r.strip() for r in (user_ctx.get("retailer_scope") or "").split(",") if r.strip()]
    alerts = open_alerts_for_user(db, user_retailers=retailers)
    return {"user_id": user_id, "issues": alerts, "count": len(alerts)}


@app.delete("/sessions/{session_id}")
def clear_session(session_id: str):
    """Clear conversation history for a session (start fresh)."""
    if session_id in _agent_sessions:
        del _agent_sessions[session_id]
    return {"cleared": True}


@app.get("/users")
def list_users(db: Session = Depends(get_db)):
    """List all users in the prototype DB (for testing / demo setup)."""
    from models.schema import UserPreferences
    users = db.query(UserPreferences).all()
    return [
        {
            "user_id":    u.user_id,
            "user_name":  u.user_name,
            "user_role":  u.user_role,
            "retailer_scope": u.retailer_scope,
            "brand_scope": u.brand_scope,
            "default_period": u.preferred_time_period,
        }
        for u in users
    ]


@app.get("/summary/{user_id}")
def quick_summary(user_id: str, period_weeks: int = 4, db: Session = Depends(get_db)):
    """
    Quick KPI summary without going through the agent loop.
    Useful for testing data layer independently of Claude.
    GET /summary/USR-001?period_weeks=4
    """
    from tools.kpi_tools import get_business_summary, search_memory
    from models.queries import get_latest_date

    mem   = search_memory(db, user_id=user_id)
    prefs = mem.get("preferences") or {}

    retailers = prefs.get("retailer_scope", [])
    regions   = prefs.get("region_scope",   [])
    brand     = (prefs.get("brand_scope") or [None])[0] if prefs.get("brand_scope") else None
    metrics   = prefs.get("priority_metrics", ["Revenue", "Velocity", "OOS Rate"])

    summary = get_business_summary(
        db,
        priority_metrics=metrics,
        retailers=retailers if retailers else None,
        regions=regions     if regions   else None,
        brand_name=brand,
        period_weeks=period_weeks,
    )
    summary["user_id"]    = user_id
    summary["user_name"]  = prefs.get("user_name", user_id)
    summary["synthetic"]  = SYNTHETIC_DATA_MODE
    return summary


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_user_context(db: Session, user_id: str) -> dict:
    """
    Load user preferences from DB and return as user_context dict for the agent.
    Falls back to sensible defaults if user not found.
    """
    mem   = search_memory(db, user_id=user_id)
    prefs = mem.get("preferences") or {}

    # priority_metrics comes back as a list; system prompt wants CSV string
    pm = prefs.get("priority_metrics", ["Revenue", "Velocity", "OOS Rate"])
    priority_metrics_str = ", ".join(pm) if isinstance(pm, list) else pm

    retailer_scope = prefs.get("retailer_scope", [])
    retailer_str   = ", ".join(retailer_scope) if isinstance(retailer_scope, list) else retailer_scope or "All retailers"

    region_scope = prefs.get("region_scope", [])
    region_str   = ", ".join(region_scope) if isinstance(region_scope, list) else region_scope or "National"

    return {
        "user_id":          user_id,
        "user_name":        prefs.get("user_name", user_id),
        "user_role":        prefs.get("role", "Brand Manager"),
        "priority_metrics": priority_metrics_str,
        "retailer_scope":   retailer_str,
        "region_scope":     region_str,
        "default_period":   prefs.get("default_period", "L4W"),
        "narrative_mode":   prefs.get("narrative_mode", "Merchant"),
        # keep raw lists for agent use
        "_retailer_list":   retailer_scope if isinstance(retailer_scope, list) else [],
        "_region_list":     region_scope   if isinstance(region_scope,   list) else [],
        "_brand_list":      prefs.get("brand_scope", []),
    }
