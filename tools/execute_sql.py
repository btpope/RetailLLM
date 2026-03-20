"""
TestGPT Tool: execute_sql
Wraps the query library for Claude to call via tool use.
Claude sends natural-language intent; this tool resolves it to a safe, pre-built query.
"""

from __future__ import annotations
from typing import Any
from models.queries import (
    velocity_trend_by_sku_retailer,
    promo_lift_vs_baseline,
    oos_threshold_breaches,
    top_kpi_summary_for_user,
    open_alerts_for_user,
    run_raw_sql,
)
from config.settings import READONLY_ENFORCED


# ─── Tool Definition (Claude tool_use schema) ─────────────────────────────────
TOOL_DEFINITION = {
    "name": "execute_sql",
    "description": (
        "Execute a read-only query against the Engine data warehouse. "
        "Use named query patterns when possible. "
        "Raw SQL is accepted but must be strictly SELECT-only. "
        "Returns rows as a list of dicts plus a row_count."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": [
                    "velocity_trend",
                    "promo_lift",
                    "oos_breaches",
                    "kpi_summary",
                    "open_alerts",
                    "raw_sql",
                ],
                "description": "Named query pattern to execute, or 'raw_sql' for a custom query.",
            },
            "params": {
                "type": "object",
                "description": "Parameters for the chosen query pattern (see each pattern's signature).",
            },
            "raw_sql": {
                "type": "string",
                "description": "Raw SQL string — only used when query_type='raw_sql'. Must be SELECT only.",
            },
        },
        "required": ["query_type"],
    },
}


# ─── Tool Handler ─────────────────────────────────────────────────────────────
def execute_sql(session, query_type: str, params: dict = None, raw_sql: str = None) -> dict[str, Any]:
    """
    Routes to the appropriate query function or executes raw SQL (read-only enforced).

    Args:
        session: SQLAlchemy Session
        query_type: Named pattern or 'raw_sql'
        params: Dict of query parameters
        raw_sql: Raw SQL string (only for query_type='raw_sql')

    Returns:
        { "rows": [...], "row_count": int, "query_type": str }
    """
    params = params or {}

    # TODO: Replace with real session from DB connection pool
    # TODO: Add structured logging for every execute_sql call (audit trail)
    # TODO: Add caching layer for repeated identical queries (Redis or in-memory)

    try:
        if query_type == "velocity_trend":
            rows = velocity_trend_by_sku_retailer(
                session,
                sku_id=params.get("sku_id"),
                retailer_name=params.get("retailer_name"),
                weeks=params.get("weeks", 13),
            )
        elif query_type == "promo_lift":
            rows = promo_lift_vs_baseline(
                session,
                retailer_name=params.get("retailer_name"),
                sku_id=params.get("sku_id"),
            )
        elif query_type == "oos_breaches":
            rows = oos_threshold_breaches(
                session,
                threshold_pct=params.get("threshold_pct", 5.0),
                retailer_name=params.get("retailer_name"),
                weeks_back=params.get("weeks_back", 4),
            )
        elif query_type == "kpi_summary":
            rows = top_kpi_summary_for_user(
                session,
                user_retailers=params.get("retailers", []),
                user_regions=params.get("regions", []),
                period_weeks=params.get("period_weeks", 4),
            )
        elif query_type == "open_alerts":
            rows = open_alerts_for_user(
                session,
                user_retailers=params.get("retailers", []),
                severity=params.get("severity"),
            )
        elif query_type == "raw_sql":
            if not raw_sql:
                return _error("raw_sql query_type requires a 'raw_sql' string.")
            rows = run_raw_sql(session, raw_sql, params)
        else:
            return _error(f"Unknown query_type: '{query_type}'")

        return {
            "rows": rows,
            "row_count": len(rows),
            "query_type": query_type,
        }

    except PermissionError as e:
        return _error(str(e))
    except Exception as e:
        # TODO: Log full traceback here
        return _error(f"Query failed: {str(e)}")


def _error(msg: str) -> dict:
    return {"rows": [], "row_count": 0, "error": msg}
