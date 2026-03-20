"""
TestGPT — Metric Store Tool
Pre-computed KPI lookups. Always prefer this over execute_sql for standard metrics.
Zero SQL generation risk. Consistent definitions. Fast single-row lookups.
"""

from __future__ import annotations
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session


# ─── Tool Definition ──────────────────────────────────────────────────────────
TOOL_DEFINITION = {
    "name": "get_metric",
    "description": (
        "Look up pre-computed KPI metrics from the metric store. "
        "ALWAYS use this tool first for standard business questions — it is faster and more accurate than execute_sql. "
        "Use execute_sql only for custom questions that cannot be answered by this tool.\n\n"
        "Available metrics: revenue, units_sold, velocity (U/S/W), oos_rate, acv, promo_lift, promo_roi, trade_spend, yoy_growth, all\n"
        "Available periods: L4W (last 4 weeks), L13W (last 13 weeks), L52W (last 52 weeks), YTD\n"
        "Available grains: total (all brands/SKUs), brand (one brand), sku (one SKU)\n\n"
        "Examples:\n"
        "  - 'How is my business?' → grain=total or grain=brand, period=user's default_period, metric=all\n"
        "  - 'How is Apex velocity?' → grain=brand, brand_name=Apex, metric=velocity\n"
        "  - 'Top SKUs by OOS rate' → grain=sku, metric=oos_rate, sort_by=avg_oos_rate_pct, sort_order=desc, limit=10\n"
        "  - 'Revenue YoY' → grain=brand, metric=yoy_growth\n"
        "  - 'Promo ROI for Bolt' → grain=brand, brand_name=Bolt, metric=promo_roi"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "period": {
                "type": "string",
                "enum": ["L4W", "L13W", "L52W", "YTD"],
                "description": "Time period. Use the user's default_period unless they specify otherwise.",
            },
            "grain": {
                "type": "string",
                "enum": ["total", "brand", "sku"],
                "description": (
                    "Aggregation level:\n"
                    "  total → all brands/SKUs rolled up (default for 'how is my business')\n"
                    "  brand → one or all brands broken out\n"
                    "  sku   → individual SKU level (for top-N lists, outlier analysis)"
                ),
            },
            "metric": {
                "type": "string",
                "enum": [
                    "all", "revenue", "units_sold", "velocity",
                    "oos_rate", "acv", "distribution",
                    "promo_lift", "promo_roi", "trade_spend",
                    "yoy_growth",
                ],
                "description": (
                    "Which metric(s) to return. Use 'all' for business summary questions. "
                    "Use specific metric for focused questions (e.g. 'all' for summary, 'oos_rate' for shelf health)."
                ),
            },
            "brand_name": {
                "type": "string",
                "description": "Filter by brand (Apex, Bolt, Silke). Leave empty for all brands.",
            },
            "sku_id": {
                "type": "string",
                "description": "Filter by specific SKU ID (e.g. SKU-001). Only relevant when grain=sku.",
            },
            "sort_by": {
                "type": "string",
                "description": "Column to sort results by. E.g. 'avg_oos_rate_pct', 'velocity_units_per_store_per_week', 'revenue'.",
            },
            "sort_order": {
                "type": "string",
                "enum": ["asc", "desc"],
                "description": "Sort direction. Default: desc.",
            },
            "limit": {
                "type": "integer",
                "description": "Max rows to return. Default 20. Use 10 for top-N lists.",
            },
        },
        "required": ["period", "grain", "metric"],
    },
}


# ─── Column groups by metric ──────────────────────────────────────────────────
_METRIC_COLS = {
    "revenue":      ["revenue", "units_sold", "avg_selling_price"],
    "units_sold":   ["units_sold", "revenue"],
    "velocity":     ["velocity_units_per_store_per_week", "num_stores_selling", "avg_acv_pct"],
    "oos_rate":     ["avg_oos_rate_pct", "oos_above_threshold", "num_stores_selling"],
    "acv":          ["avg_acv_pct", "distribution_points", "num_stores_selling"],
    "distribution": ["distribution_points", "avg_acv_pct", "num_stores_selling"],
    "promo_lift":   ["promo_events", "avg_promo_lift_pct", "avg_promo_roi"],
    "promo_roi":    ["promo_events", "avg_promo_roi", "avg_promo_lift_pct", "total_trade_spend"],
    "trade_spend":  ["total_trade_spend", "promo_events", "avg_promo_roi"],
    "yoy_growth":   ["revenue", "revenue_prior_year", "revenue_yoy_pct",
                     "velocity_units_per_store_per_week", "velocity_prior_year", "velocity_yoy_pct"],
    "all": [
        "revenue", "units_sold", "velocity_units_per_store_per_week",
        "avg_oos_rate_pct", "avg_acv_pct", "distribution_points",
        "avg_promo_lift_pct", "avg_promo_roi",
        "revenue_yoy_pct", "velocity_yoy_pct", "velocity_trend",
        "oos_above_threshold", "promo_events",
    ],
}

_IDENTITY_COLS = {
    "total": ["period_label", "period_start_date", "period_end_date", "num_weeks", "retailer_name"],
    "brand": ["period_label", "period_start_date", "period_end_date", "num_weeks", "retailer_name", "brand_name"],
    "sku":   ["period_label", "period_start_date", "period_end_date", "num_weeks",
               "retailer_name", "brand_name", "sku_id", "sku_description"],
}


# ─── Tool handler ─────────────────────────────────────────────────────────────
def get_metric(
    session: Session,
    period: str,
    grain: str,
    metric: str,
    brand_name: str | None = None,
    sku_id: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
    limit: int = 20,
) -> dict[str, Any]:
    """
    Query the pre-computed metric_store table.
    Returns a list of rows matching the filters.
    """
    metric_cols = _METRIC_COLS.get(metric, _METRIC_COLS["all"])
    id_cols     = _IDENTITY_COLS.get(grain, _IDENTITY_COLS["total"])
    select_cols = id_cols + [c for c in metric_cols if c not in id_cols]

    # Build WHERE clause
    conditions = ["grain = :grain", "period_label = :period", "retailer_name = 'Walmart'"]
    params: dict[str, Any] = {"grain": grain, "period": period}

    if brand_name:
        conditions.append("brand_name = :brand_name")
        params["brand_name"] = brand_name
    if sku_id:
        conditions.append("sku_id = :sku_id")
        params["sku_id"] = sku_id

    # Determine sort column
    if sort_by and sort_by in select_cols:
        order_col = sort_by
    elif metric in ("oos_rate",):
        order_col = "avg_oos_rate_pct"
    elif metric in ("velocity",):
        order_col = "velocity_units_per_store_per_week"
    elif metric in ("revenue", "units_sold"):
        order_col = "revenue"
    elif metric in ("promo_roi", "promo_lift"):
        order_col = "avg_promo_roi"
    elif metric in ("yoy_growth",):
        order_col = "revenue_yoy_pct"
    else:
        order_col = "revenue"

    sort_dir = "DESC" if sort_order.lower() != "asc" else "ASC"
    cols_sql = ", ".join(select_cols)
    where_sql = " AND ".join(conditions)
    query = f"""
        SELECT {cols_sql}
        FROM metric_store
        WHERE {where_sql}
        ORDER BY {order_col} {sort_dir} NULLS LAST
        LIMIT :limit
    """
    params["limit"] = min(limit, 50)

    try:
        rows = session.execute(text(query), params).fetchall()
        keys = select_cols

        results = []
        for row in rows:
            d = dict(zip(keys, row))
            # Add human-readable benchmark context
            if "avg_oos_rate_pct" in d and d["avg_oos_rate_pct"] is not None:
                oos = d["avg_oos_rate_pct"]
                if oos > 10:
                    d["oos_benchmark"] = "CRITICAL — 2x category avg; Walmart may reduce replenishment"
                elif oos > 5:
                    d["oos_benchmark"] = "ELEVATED — above 5% Walmart threshold; buyer visibility risk"
                else:
                    d["oos_benchmark"] = "HEALTHY — within normal range (<5%)"

            if "velocity_units_per_store_per_week" in d and d["velocity_units_per_store_per_week"] is not None:
                vel = d["velocity_units_per_store_per_week"]
                brand = d.get("brand_name", "")
                if brand == "Apex":
                    d["velocity_benchmark"] = f"{'STRONG' if vel > 7 else 'AVERAGE' if vel > 4 else 'WEAK'} vs Apex snacks avg 5–9 U/S/W"
                elif brand == "Bolt":
                    d["velocity_benchmark"] = f"{'STRONG' if vel > 12 else 'AVERAGE' if vel > 7 else 'WEAK'} vs Bolt energy avg 8–15 U/S/W"
                elif brand == "Silke":
                    d["velocity_benchmark"] = f"{'STRONG' if vel > 3 else 'AVERAGE' if vel > 1.5 else 'WEAK'} vs Silke hair care avg 1.5–4 U/S/W"

            if "avg_promo_roi" in d and d["avg_promo_roi"] is not None:
                roi = d["avg_promo_roi"]
                d["promo_roi_benchmark"] = (
                    "EXCELLENT (>2x)" if roi > 2.0 else
                    "GOOD (1.5–2x)" if roi > 1.5 else
                    "BREAKEVEN (1.0–1.5x)" if roi > 1.0 else
                    "BELOW BREAKEVEN (<1.0x) — trade spend not generating incremental profit"
                )

            if "revenue_yoy_pct" in d and d["revenue_yoy_pct"] is not None:
                yoy = d["revenue_yoy_pct"]
                d["yoy_context"] = f"{'GROWTH' if yoy > 0 else 'DECLINE'} — {abs(yoy):.1f}% {'above' if yoy > 0 else 'below'} prior year same period"

            results.append(d)

        return {
            "rows": results,
            "row_count": len(results),
            "period": period,
            "grain": grain,
            "metric": metric,
            "note": "[SYNTHETIC DATA — DEMO ONLY] Pre-computed metric store. Definitions: velocity=U/S/W (units per store per week), OOS=out-of-stock rate %, promo_roi=incremental profit / trade spend.",
        }

    except Exception as e:
        return {"error": str(e), "query": query, "params": params}
