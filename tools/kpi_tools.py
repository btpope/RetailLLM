"""
RetailGPT Tools: get_kpi_card, get_promo_calendar, get_retailer_account
Thin wrappers around query functions — one tool per Claude tool_use call.
"""

from __future__ import annotations
from models.queries import (
    top_kpi_summary_for_user,
    promo_lift_vs_baseline,
    retailer_account_scorecard,
)


# ── get_kpi_card ──────────────────────────────────────────────────────────────
KPI_CARD_TOOL = {
    "name": "get_kpi_card",
    "description": "Return current + prior period value for a specific KPI metric, filtered by retailer/region/SKU.",
    "input_schema": {
        "type": "object",
        "properties": {
            "metric": {"type": "string", "description": "KPI name: Revenue, Units, Velocity, OOS Rate, ACV, Promo Lift"},
            "filters": {
                "type": "object",
                "properties": {
                    "retailers": {"type": "array", "items": {"type": "string"}},
                    "regions": {"type": "array", "items": {"type": "string"}},
                    "sku_id": {"type": "string"},
                    "period_weeks": {"type": "integer", "default": 4},
                },
            },
        },
        "required": ["metric"],
    },
}

def get_kpi_card(session, metric: str, filters: dict = None) -> dict:
    """
    Returns a KPI card: current value, prior period value, delta %, trend direction.
    TODO: Implement metric-specific aggregation logic.
    TODO: Map metric names to actual column names in sales_kpi_weekly.
    """
    filters = filters or {}
    # TODO: Route to correct column based on metric name
    # e.g., "Velocity" → avg(velocity_per_store), "Revenue" → sum(dollar_sales)
    rows = top_kpi_summary_for_user(
        session,
        user_retailers=filters.get("retailers", []),
        user_regions=filters.get("regions", []),
        period_weeks=filters.get("period_weeks", 4),
    )
    # TODO: Calculate prior period and delta
    return {
        "metric": metric,
        "current_value": None,   # TODO: extract from rows
        "prior_value": None,     # TODO: query prior period
        "delta_pct": None,       # TODO: compute (current - prior) / prior * 100
        "trend": "unknown",      # TODO: "up" | "down" | "flat"
        "rows": rows,
    }


# ── get_promo_calendar ────────────────────────────────────────────────────────
PROMO_CALENDAR_TOOL = {
    "name": "get_promo_calendar",
    "description": "Return the promotion schedule and lift data for a retailer and optional date range.",
    "input_schema": {
        "type": "object",
        "properties": {
            "retailer": {"type": "string"},
            "sku_id": {"type": "string"},
            "date_range": {"type": "string", "description": "e.g. '2026-Q1' or '2026-01-01:2026-03-31'"},
        },
        "required": ["retailer"],
    },
}

def get_promo_calendar(session, retailer: str, sku_id: str = None, date_range: str = None) -> dict:
    """
    Returns promo schedule + lift metrics for the specified retailer.
    TODO: Parse date_range string into start/end dates.
    """
    rows = promo_lift_vs_baseline(session, retailer_name=retailer, sku_id=sku_id)
    # TODO: Filter by date_range when parsed
    return {"retailer": retailer, "promos": rows, "count": len(rows)}


# ── get_retailer_account ──────────────────────────────────────────────────────
RETAILER_ACCOUNT_TOOL = {
    "name": "get_retailer_account",
    "description": "Return the account scorecard for a specific retailer (quarterly). Use for JBP prep and account-level intelligence.",
    "input_schema": {
        "type": "object",
        "properties": {
            "retailer": {"type": "string", "description": "Retailer name e.g. Walmart, Target, Kroger"},
            "period": {"type": "string", "description": "Scorecard period e.g. '2026-Q1'. Omit for latest."},
        },
        "required": ["retailer"],
    },
}

def get_retailer_account(session, retailer: str, period: str = None) -> dict:
    """
    Returns retailer account scorecard: sales, share, distribution, JBP targets.
    """
    rows = retailer_account_scorecard(session, retailer_name=retailer, period=period)
    return {"retailer": retailer, "period": period, "scorecard": rows}


# ── search_memory ─────────────────────────────────────────────────────────────
SEARCH_MEMORY_TOOL = {
    "name": "search_memory",
    "description": "Retrieve prior session context, user preferences, or past analyses for this user.",
    "input_schema": {
        "type": "object",
        "properties": {
            "user_id": {"type": "string"},
            "query": {"type": "string", "description": "Natural language memory search query."},
        },
        "required": ["user_id"],
    },
}

def search_memory(session, user_id: str, query: str = None) -> dict:
    """
    TODO: Implement vector search over user preference store + session history.
    For prototype: returns user_preferences record from DB.
    """
    from models.schema import UserPreferences
    prefs = session.get(UserPreferences, user_id)
    if not prefs:
        return {"user_id": user_id, "preferences": None, "memory": []}
    return {
        "user_id": user_id,
        "preferences": {
            "role": prefs.user_role,
            "narrative_mode": prefs.default_narrative_mode,
            "priority_metrics": prefs.priority_metrics,
            "retailer_scope": prefs.retailer_scope,
            "region_scope": prefs.region_scope,
            "oos_threshold": float(prefs.oos_alert_threshold_pct or 5.0),
            "velocity_decline_threshold": float(prefs.velocity_decline_threshold_pct or 10.0),
            "promo_roi_floor": float(prefs.promo_roi_floor or 0.80),
            "default_period": prefs.preferred_time_period,
        },
        "memory": [],  # TODO: vector search results
    }
