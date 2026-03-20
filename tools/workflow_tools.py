"""
TestGPT Tools: flag_issue, send_for_approval, generate_infographic_image
All write-adjacent actions route through HITL approval gates.
No action executes without explicit user confirmation.
"""

from __future__ import annotations
from datetime import datetime
import uuid


# ── flag_issue ────────────────────────────────────────────────────────────────
FLAG_ISSUE_TOOL = {
    "name": "flag_issue",
    "description": (
        "Surface a detected KPI anomaly or threshold breach as a structured issue. "
        "Does NOT assign or route — only creates the flag. "
        "Use send_for_approval to assign."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "severity": {"type": "string", "enum": ["High", "Medium", "Low"]},
            "alert_type": {"type": "string", "description": "e.g. OOS_BREACH, VELOCITY_DECLINE, PROMO_ROI_MISS"},
            "sku_id": {"type": "string"},
            "retailer_name": {"type": "string"},
            "metric_name": {"type": "string"},
            "threshold_value": {"type": "number"},
            "actual_value": {"type": "number"},
            "root_cause_narrative": {"type": "string", "description": "AI-generated explanation of why this happened."},
        },
        "required": ["severity", "alert_type", "root_cause_narrative"],
    },
}

def flag_issue(session, severity: str, alert_type: str, root_cause_narrative: str,
               sku_id: str = None, retailer_name: str = None,
               metric_name: str = None, threshold_value: float = None,
               actual_value: float = None) -> dict:
    """
    Creates a KPI alert record (status=Open) and returns the alert ID.
    Frontend should surface this as an [ISSUE] card with disposition options.

    TODO: Persist to kpi_alert_log table.
    TODO: Trigger push notification if severity=High.
    """
    alert_id = f"ALERT-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"

    # TODO: session.add(KPIAlertLog(...)); session.commit()

    return {
        "alert_id": alert_id,
        "status": "Open",
        "severity": severity,
        "alert_type": alert_type,
        "sku_id": sku_id,
        "retailer_name": retailer_name,
        "metric_name": metric_name,
        "threshold_value": threshold_value,
        "actual_value": actual_value,
        "root_cause_narrative": root_cause_narrative,
        "created_at": datetime.utcnow().isoformat(),
        "disposition_options": ["Acknowledge", "Investigate", "Assign"],
    }


# ── send_for_approval ─────────────────────────────────────────────────────────
SEND_FOR_APPROVAL_TOOL = {
    "name": "send_for_approval",
    "description": (
        "MANDATORY HITL gate. Call this before: sending any email, assigning an issue, "
        "triggering any automated workflow, or publishing to a shared dashboard. "
        "Returns a preview payload the UI will show the user before any action executes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action_type": {
                "type": "string",
                "enum": ["assign_issue", "send_email", "publish_dashboard", "trigger_workflow"],
            },
            "description": {"type": "string", "description": "Plain-language description of what will happen."},
            "payload": {"type": "object", "description": "The full action payload that will execute on approval."},
        },
        "required": ["action_type", "description", "payload"],
    },
}

def send_for_approval(action_type: str, description: str, payload: dict) -> dict:
    """
    Returns a pending approval object. The orchestrator pauses and surfaces this
    to the user as a [PREVIEW] → APPROVE / EDIT / CANCEL prompt.
    No action is taken until the user explicitly approves.

    TODO: Persist pending approval to a queue (Redis, DB table).
    TODO: Set expiry — auto-cancel if not approved within N hours.
    TODO: Capture Approved/Edited/Rejected outcome as training signal.
    """
    approval_id = f"APPROVAL-{str(uuid.uuid4())[:8].upper()}"

    return {
        "approval_id": approval_id,
        "status": "pending",
        "action_type": action_type,
        "description": description,
        "payload": payload,
        "created_at": datetime.utcnow().isoformat(),
        "ui_prompt": f"[PREVIEW]\n{description}\n\n→ APPROVE / EDIT / CANCEL",
    }


# ── generate_infographic_image (P2 — Step 3) ──────────────────────────────────
INFOGRAPHIC_TOOL = {
    "name": "generate_infographic_image",
    "description": (
        "Generate a styled infographic image using the Gemini image API. "
        "P2 feature — only available if INFOGRAPHIC_PROVIDER is configured. "
        "Routes to gemini-2.5-flash-exp with image output enabled. "
        "Always requires send_for_approval before delivering to any shared surface."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "headline_number": {"type": "string", "description": "Primary stat, shown largest (e.g. '+12% Velocity')"},
            "supporting_stats": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-3 supporting data points.",
                "maxItems": 3,
            },
            "narrative": {"type": "string", "description": "Brief narrative text (1-2 sentences)."},
            "source_note": {"type": "string", "description": "Data source attribution."},
            "style": {"type": "string", "enum": ["executive", "buyer_meeting", "internal"], "default": "executive"},
        },
        "required": ["headline_number", "supporting_stats", "narrative"],
    },
}

def generate_infographic_image(headline_number: str, supporting_stats: list[str],
                                narrative: str, source_note: str = None,
                                style: str = "executive") -> dict:
    """
    Calls Gemini image API to generate an infographic.
    Always label output as [SYNTHETIC DATA — DEMO ONLY] in prototype mode.

    TODO: Implement Gemini API call using config.settings.INFOGRAPHIC_ENDPOINT
    TODO: Handle image bytes response and convert to base64 or URL
    TODO: Gate behind send_for_approval before any sharing
    """
    from config.settings import INFOGRAPHIC_ENDPOINT, GOOGLE_API_KEY, SYNTHETIC_DATA_MODE, PROTOTYPE_LABEL

    if not GOOGLE_API_KEY:
        return {"error": "GOOGLE_API_KEY not configured. Infographic generation unavailable."}

    # TODO: Build Gemini API request body
    # TODO: POST to INFOGRAPHIC_ENDPOINT with image generation params
    # TODO: Parse response and extract image URL/base64

    label = f" {PROTOTYPE_LABEL}" if SYNTHETIC_DATA_MODE else ""
    return {
        "status": "not_implemented",
        "message": f"Infographic generation stub — P2 Step 3.{label}",
        "spec": {
            "headline": headline_number,
            "stats": supporting_stats,
            "narrative": narrative,
            "source": source_note or f"Engine TestGPT{label}",
            "style": style,
        },
    }
