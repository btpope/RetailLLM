"""
TestGPT Tools: get_kpi_card, get_promo_calendar, get_retailer_account, search_memory
All fully implemented for Step 1.
"""

from __future__ import annotations
from models.queries import (
    kpi_aggregate,
    business_summary,
    promo_lift_vs_baseline,
    retailer_account_scorecard,
    METRIC_MAP,
)


# ── get_kpi_card ──────────────────────────────────────────────────────────────
KPI_CARD_TOOL = {
    "name": "get_kpi_card",
    "description": (
        "Return current value, prior period value, delta %, and trend direction for a specific KPI metric. "
        "Use for any question about a single metric: 'What is my velocity at Walmart?', "
        "'How is OOS rate trending?', 'Is promo ROI above target?'"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": list(METRIC_MAP.keys()),
                "description": "KPI name. Options: Revenue, Units, Velocity, OOS Rate, ACV, Price, "
                               "YoY Growth, Distribution Points, Promo Lift, Promo ROI, Trade Spend",
            },
            "filters": {
                "type": "object",
                "description": "Optional filters to scope the metric.",
                "properties": {
                    "retailers":    {"type": "array",  "items": {"type": "string"}, "description": "Filter to specific retailers e.g. ['Walmart']"},
                    "regions":      {"type": "array",  "items": {"type": "string"}, "description": "Filter to specific regions e.g. ['Southeast']"},
                    "sku_id":       {"type": "string", "description": "Filter to a single SKU e.g. 'SKU-A01'"},
                    "brand_name":   {"type": "string", "description": "Filter to a brand e.g. 'Apex'"},
                    "period_weeks": {"type": "integer","description": "Lookback window in weeks (4=L4W, 13=L13W, 52=L52W). Default: 4"},
                },
            },
        },
        "required": ["metric"],
    },
}

def get_kpi_card(session, metric: str, filters: dict = None) -> dict:
    """
    Returns current vs. prior period for a KPI with delta % and trend.

    Current period  = last N weeks ending on the DB's latest date
    Prior period    = the N weeks immediately before current (WoW comparison)

    Trend: "up" if delta > +1%, "down" if < -1%, "flat" otherwise.
    """
    filters      = filters or {}
    period_weeks = int(filters.get("period_weeks", 4))
    retailers    = filters.get("retailers") or []
    regions      = filters.get("regions")   or []
    sku_id       = filters.get("sku_id")
    brand_name   = filters.get("brand_name")

    result = kpi_aggregate(
        session,
        metric=metric,
        period_weeks=period_weeks,
        retailers=retailers if retailers else None,
        regions=regions     if regions   else None,
        sku_id=sku_id,
        brand_name=brand_name,
    )

    # Format for Claude's consumption — add a plain-English summary line
    if "error" not in result and result.get("current_value") is not None:
        cv    = result["current_value"]
        unit  = result["unit"]
        delta = result["delta_pct"]
        trend = result["trend"]
        period = result["period_label"]

        if unit == "$":
            cv_str = f"${cv:,.0f}"
            pv_str = f"${result['prior_value']:,.0f}" if result["prior_value"] else "N/A"
        elif unit == "%":
            cv_str = f"{cv:.1f}%"
            pv_str = f"{result['prior_value']:.1f}%" if result["prior_value"] else "N/A"
        elif unit == "x":
            cv_str = f"{cv:.2f}x"
            pv_str = f"{result['prior_value']:.2f}x" if result["prior_value"] else "N/A"
        elif unit == "U/S/W":
            cv_str = f"{cv:.2f} U/S/W"
            pv_str = f"{result['prior_value']:.2f} U/S/W" if result["prior_value"] else "N/A"
        else:
            cv_str = f"{cv:,.1f}"
            pv_str = f"{result['prior_value']:,.1f}" if result["prior_value"] else "N/A"

        arrow = "▲" if trend == "up" else ("▼" if trend == "down" else "→")
        delta_str = f"{arrow} {abs(delta):.1f}%" if delta is not None else "N/A"

        result["summary"] = (
            f"{metric}: {cv_str} ({delta_str} vs. prior {period})"
        )
        result["formatted"] = {
            "current": cv_str,
            "prior":   pv_str,
            "delta":   delta_str,
        }

    return result


# ── get_business_summary ──────────────────────────────────────────────────────
BUSINESS_SUMMARY_TOOL = {
    "name": "get_business_summary",
    "description": (
        "Pull KPI cards for all of the user's priority metrics at once and rank them by change. "
        "Use this as the FIRST tool call for any variant of 'How is my business?', 'Give me a summary', "
        "'What changed this week?', or similar open-ended business health questions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "priority_metrics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of metric names to pull. Use user's configured priority_metrics.",
            },
            "retailers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Retailer filter — use user's retailer_scope.",
            },
            "regions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Region filter — use user's region_scope.",
            },
            "brand_name": {
                "type": "string",
                "description": "Brand filter — use user's brand_scope if set.",
            },
            "period_weeks": {
                "type": "integer",
                "description": "Lookback weeks. Use user's default_period (L4W=4, L13W=13, L52W=52). Default: 4",
            },
        },
        "required": ["priority_metrics"],
    },
}

def get_business_summary(session, priority_metrics: list[str],
                          retailers: list[str] = None, regions: list[str] = None,
                          brand_name: str = None, period_weeks: int = 4) -> dict:
    """Full business summary: all priority KPIs ranked by change magnitude."""
    return business_summary(
        session,
        priority_metrics=priority_metrics,
        period_weeks=period_weeks,
        retailers=retailers,
        regions=regions,
        brand_name=brand_name,
    )


# ── get_promo_calendar ────────────────────────────────────────────────────────
PROMO_CALENDAR_TOOL = {
    "name": "get_promo_calendar",
    "description": (
        "Return the promotion schedule and lift data for a retailer. "
        "Includes baseline vs promo velocity, lift %, ROI, and trade spend. "
        "Use for: 'What promos ran at Walmart?', 'How did our last Feature+Display perform?', "
        "'Show me promo ROI for Apex'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "retailer":   {"type": "string", "description": "Retailer name e.g. 'Walmart'"},
            "sku_id":     {"type": "string", "description": "Optional: filter to one SKU"},
            "brand_name": {"type": "string", "description": "Optional: filter to one brand"},
        },
        "required": ["retailer"],
    },
}

def get_promo_calendar(session, retailer: str, sku_id: str = None,
                        brand_name: str = None, **kwargs) -> dict:
    """Promo schedule + lift metrics for the specified retailer."""
    rows = promo_lift_vs_baseline(
        session,
        retailer_name=retailer,
        sku_id=sku_id,
        brand_name=brand_name,
    )
    # Compute summary stats
    if rows:
        rois   = [r["promo_roi"]   for r in rows if r.get("promo_roi")   is not None]
        lifts  = [r["promo_lift_pct"] for r in rows if r.get("promo_lift_pct") is not None]
        spends = [r["trade_spend_dollars"] for r in rows if r.get("trade_spend_dollars") is not None]
        summary = {
            "avg_roi":          round(sum(rois)  / len(rois),   2) if rois   else None,
            "avg_lift_pct":     round(sum(lifts) / len(lifts),  1) if lifts  else None,
            "total_trade_spend":round(sum(spends),              0) if spends else None,
            "promo_count":      len(rows),
        }
    else:
        summary = {}

    return {
        "retailer": retailer,
        "promos":   rows,
        "count":    len(rows),
        "summary":  summary,
    }


# ── get_retailer_account ──────────────────────────────────────────────────────
RETAILER_ACCOUNT_TOOL = {
    "name": "get_retailer_account",
    "description": (
        "Return the quarterly account scorecard for a retailer. "
        "Includes sales, category share, distribution, ACV, JBP target vs. actual. "
        "Use for: 'How are we tracking vs JBP at Walmart?', 'Walmart account scorecard', "
        "'What is our distribution score at Kroger?'"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "retailer": {"type": "string", "description": "Retailer name e.g. 'Walmart'"},
            "period":   {"type": "string", "description": "Specific quarter e.g. '2024-Q4'. Omit for all recent quarters."},
        },
        "required": ["retailer"],
    },
}

def get_retailer_account(session, retailer: str, period: str = None, **kwargs) -> dict:
    """Retailer account scorecard — JBP support."""
    rows = retailer_account_scorecard(session, retailer_name=retailer, period=period)
    return {"retailer": retailer, "period": period, "scorecard": rows, "quarters": len(rows)}


# ── search_memory ─────────────────────────────────────────────────────────────
SEARCH_MEMORY_TOOL = {
    "name": "search_memory",
    "description": (
        "Retrieve user preferences, role, priority metrics, retailer scope, "
        "and alert thresholds for a given user. "
        "ALWAYS call this first in a new session to personalize responses."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "User ID e.g. 'USR-001'"},
            "query":   {"type": "string", "description": "Optional: specific preference to look up."},
        },
        "required": ["user_id"],
    },
}

def search_memory(session, user_id: str, query: str = None, **kwargs) -> dict:
    """Load user preferences from DB. Returns structured preferences dict."""
    from models.schema import UserPreferences
    prefs = session.get(UserPreferences, user_id)
    if not prefs:
        return {
            "user_id":     user_id,
            "found":       False,
            "preferences": None,
            "message":     f"No preferences found for user '{user_id}'. Using defaults.",
        }

    retailer_scope = [r.strip() for r in (prefs.retailer_scope or "").split(",") if r.strip()]
    region_scope   = [r.strip() for r in (prefs.region_scope   or "").split(",") if r.strip()]
    brand_scope    = [b.strip() for b in (prefs.brand_scope     or "").split(",") if b.strip()]
    priority_metrics = [m.strip() for m in (prefs.priority_metrics or "Revenue,Velocity,OOS Rate").split(",") if m.strip()]

    return {
        "user_id":   user_id,
        "found":     True,
        "preferences": {
            "user_name":       prefs.user_name,
            "user_email":      prefs.user_email,
            "role":            prefs.user_role,
            "narrative_mode":  prefs.default_narrative_mode,
            "priority_metrics": priority_metrics,
            "retailer_scope":  retailer_scope,
            "region_scope":    region_scope,
            "brand_scope":     brand_scope,
            "excluded_regions":[r.strip() for r in (prefs.excluded_regions or "").split(",") if r.strip()],
            "oos_threshold":   float(prefs.oos_alert_threshold_pct   or 5.0),
            "velocity_decline_threshold": float(prefs.velocity_decline_threshold_pct or 10.0),
            "promo_roi_floor": float(prefs.promo_roi_floor or 0.80),
            "default_period":  prefs.preferred_time_period or "L4W",
        },
    }
