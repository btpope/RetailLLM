"""
TestGPT — Benchmark & Trend Analysis Tools (Phase 2)
Structured benchmark comparisons and multi-period trend signals.
"""

from __future__ import annotations
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session


# ─── get_benchmark Tool ───────────────────────────────────────────────────────

BENCHMARK_TOOL_DEFINITION = {
    "name": "get_benchmark",
    "description": (
        "Compare a metric value to category benchmarks and Walmart thresholds. "
        "Use this to answer: 'Is this normal?', 'Is this good?', 'Should I be worried?' "
        "Call AFTER get_metric to contextualize the numbers.\n\n"
        "Examples:\n"
        "  - OOS rate 8.2% for Apex → get_benchmark(metric='oos_rate', value=8.2, brand_name='Apex')\n"
        "  - Velocity 4.5 U/S/W for Bolt → get_benchmark(metric='velocity', value=4.5, brand_name='Bolt')\n"
        "  - Promo ROI 0.85x → get_benchmark(metric='promo_roi', value=0.85)"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": ["velocity", "oos_rate", "promo_roi", "promo_lift", "acv",
                         "otif", "dc_fill_rate", "yoy_growth", "trade_spend_efficiency"],
                "description": "Metric to benchmark.",
            },
            "value": {
                "type": "number",
                "description": "The actual value to compare.",
            },
            "brand_name": {
                "type": "string",
                "description": "Brand name (Apex, Bolt, Silke). Required for velocity benchmarks.",
            },
        },
        "required": ["metric", "value"],
    },
}


def get_benchmark(
    session: Session,
    metric: str,
    value: float,
    brand_name: str | None = None,
) -> dict[str, Any]:
    """Look up benchmark tiers and return structured comparison."""
    query = """
        SELECT metric_name, brand_name, category, tier_weak, tier_avg_low, tier_avg_high,
               tier_strong, tier_elite, unit,
               interpretation_weak, interpretation_avg, interpretation_strong,
               interpretation_action_weak, walmart_threshold, walmart_threshold_note
        FROM benchmark_reference
        WHERE metric_name = :metric
          AND (brand_name = :brand OR brand_name IS NULL)
        ORDER BY brand_name DESC  -- prefer brand-specific row over category-level
        LIMIT 1
    """
    row = session.execute(text(query), {"metric": metric, "brand": brand_name}).fetchone()

    if not row:
        return {"error": f"No benchmark found for metric={metric}, brand={brand_name}"}

    keys = ["metric_name", "brand_name", "category", "tier_weak", "tier_avg_low",
            "tier_avg_high", "tier_strong", "tier_elite", "unit",
            "interpretation_weak", "interpretation_avg", "interpretation_strong",
            "interpretation_action_weak", "walmart_threshold", "walmart_threshold_note"]
    b = dict(zip(keys, row))

    # Determine tier
    if b["tier_elite"] is not None and value >= b["tier_elite"]:
        tier = "ELITE"
        tier_emoji = "🏆"
        interpretation = b["interpretation_strong"]
        action = None
    elif b["tier_strong"] is not None and value >= b["tier_strong"]:
        tier = "STRONG"
        tier_emoji = "✅"
        interpretation = b["interpretation_strong"]
        action = None
    elif b["tier_avg_high"] is not None and value >= b["tier_avg_low"]:
        tier = "AVERAGE"
        tier_emoji = "➡️"
        interpretation = b["interpretation_avg"]
        action = None
    else:
        tier = "WEAK"
        tier_emoji = "⚠️"
        interpretation = b["interpretation_weak"]
        action = b["interpretation_action_weak"]

    # Walmart threshold check
    wmt_status = None
    if b["walmart_threshold"] is not None:
        if metric in ("oos_rate",) and value > b["walmart_threshold"]:
            wmt_status = f"ABOVE Walmart threshold ({b['walmart_threshold']}{b['unit']}): {b['walmart_threshold_note']}"
        elif metric in ("otif", "dc_fill_rate") and value < b["walmart_threshold"]:
            wmt_status = f"BELOW Walmart threshold ({b['walmart_threshold']}{b['unit']}): {b['walmart_threshold_note']}"

    # Gap to average
    avg_mid = (b["tier_avg_low"] + b["tier_avg_high"]) / 2 if b["tier_avg_low"] and b["tier_avg_high"] else None
    gap_to_avg = round(avg_mid - value, 2) if avg_mid else None
    gap_to_strong = round(b["tier_strong"] - value, 2) if b["tier_strong"] else None

    return {
        "metric": metric,
        "value": value,
        "unit": b["unit"],
        "brand": brand_name,
        "category": b["category"],
        "tier": tier,
        "tier_emoji": tier_emoji,
        "interpretation": interpretation,
        "action_recommended": action,
        "walmart_threshold_status": wmt_status,
        "benchmarks": {
            "weak_below": b["tier_weak"],
            "avg_range": f"{b['tier_avg_low']}–{b['tier_avg_high']} {b['unit']}",
            "strong_above": b["tier_strong"],
            "elite_above": b["tier_elite"],
        },
        "gaps": {
            "to_avg_midpoint": gap_to_avg,
            "to_strong": gap_to_strong if tier not in ("STRONG", "ELITE") else None,
        },
    }


# ─── get_trend_analysis Tool ──────────────────────────────────────────────────

TREND_TOOL_DEFINITION = {
    "name": "get_trend_analysis",
    "description": (
        "Multi-period trend analysis for a metric. Returns L4W, L13W, and L52W values side-by-side "
        "with trend direction, acceleration/deceleration signals, and line-review risk assessment. "
        "Use this when asked about trends, momentum, trajectory, or 'is this getting better/worse?'\n\n"
        "Examples:\n"
        "  - 'How is velocity trending?' → get_trend_analysis(metric='velocity', grain='brand', brand_name='Apex')\n"
        "  - 'Is OOS getting worse?' → get_trend_analysis(metric='oos_rate', grain='sku', brand_name='Bolt')\n"
        "  - 'Trend for all brands' → get_trend_analysis(metric='revenue', grain='brand')"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": ["velocity", "revenue", "oos_rate", "promo_roi", "acv", "yoy_growth"],
                "description": "Metric to analyze trend for.",
            },
            "grain": {
                "type": "string",
                "enum": ["total", "brand", "sku"],
                "description": "Aggregation level.",
            },
            "brand_name": {
                "type": "string",
                "description": "Filter by brand. Leave empty for all brands.",
            },
            "sku_id": {
                "type": "string",
                "description": "Filter by SKU ID (only for grain=sku).",
            },
            "limit": {
                "type": "integer",
                "description": "Max rows (relevant for grain=sku). Default 10.",
            },
        },
        "required": ["metric", "grain"],
    },
}

_TREND_METRIC_COL = {
    "velocity":  "velocity_units_per_store_per_week",
    "revenue":   "revenue",
    "oos_rate":  "avg_oos_rate_pct",
    "promo_roi": "avg_promo_roi",
    "acv":       "avg_acv_pct",
    "yoy_growth": "revenue_yoy_pct",
}


def get_trend_analysis(
    session: Session,
    metric: str,
    grain: str,
    brand_name: str | None = None,
    sku_id: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Pull L4W, L13W, L52W metric values and compute trend signals."""

    col = _TREND_METRIC_COL.get(metric, "velocity_units_per_store_per_week")

    # Fetch all three periods in one query
    conditions = ["grain = :grain", "retailer_name = 'Walmart'",
                  "period_label IN ('L4W', 'L13W', 'L52W')"]
    params: dict[str, Any] = {"grain": grain}

    if brand_name:
        conditions.append("brand_name = :brand")
        params["brand"] = brand_name
    if sku_id:
        conditions.append("sku_id = :sku_id")
        params["sku_id"] = sku_id

    id_cols = {"total": "retailer_name",
               "brand": "brand_name",
               "sku":   "sku_id, sku_description, brand_name"}.get(grain, "brand_name")

    query = f"""
        SELECT {id_cols}, period_label, {col} as metric_value,
               velocity_trend, oos_above_threshold
        FROM metric_store
        WHERE {' AND '.join(conditions)}
        ORDER BY {id_cols.split(',')[0].strip()}, period_label
        LIMIT :limit
    """
    params["limit"] = limit * 3  # 3 periods per entity

    rows = session.execute(text(query), params).fetchall()
    if not rows:
        return {"error": "No trend data found", "params": params}

    # Group by entity
    from collections import defaultdict
    by_entity: dict[str, dict] = defaultdict(dict)
    for row in rows:
        if grain == "sku":
            key = row[0]  # sku_id
            label = f"{row[0]} — {row[1]}"  # sku_id — sku_description
            brand = row[2]
        elif grain == "brand":
            key = row[0]
            label = row[0]
            brand = row[0]
        else:
            key = "total"
            label = "All Brands — Walmart Total"
            brand = None

        period = row[-3] if grain == "sku" else row[1]
        val    = row[-3] if grain == "sku" else row[2]
        if grain == "sku":
            period = row[2]
            val    = row[3]
        elif grain == "brand":
            period = row[1]
            val    = row[2]
        else:
            period = row[1]
            val    = row[2]

        by_entity[key]["label"]   = label
        by_entity[key]["brand"]   = brand
        by_entity[key][period]    = round(val, 3) if val is not None else None

    # Compute trend signals per entity
    results = []
    for key, d in list(by_entity.items())[:limit]:
        l4w  = d.get("L4W")
        l13w = d.get("L13W")
        l52w = d.get("L52W")

        # Short-term trend: L4W vs L13W
        if l4w is not None and l13w is not None and l13w != 0:
            st_delta = (l4w - l13w) / abs(l13w) * 100
            st_trend = "ACCELERATING ↑" if st_delta > 5 else "DECELERATING ↓" if st_delta < -5 else "STABLE →"
        else:
            st_delta, st_trend = None, "INSUFFICIENT DATA"

        # Long-term trend: L13W vs L52W
        if l13w is not None and l52w is not None and l52w != 0:
            lt_delta = (l13w - l52w) / abs(l52w) * 100
            lt_trend = "IMPROVING ↑" if lt_delta > 3 else "DECLINING ↓" if lt_delta < -3 else "FLAT →"
        else:
            lt_delta, lt_trend = None, "INSUFFICIENT DATA"

        # Line review risk for velocity
        line_review_risk = None
        if metric == "velocity" and l4w is not None:
            brand_name_val = d.get("brand")
            thresholds = {"Apex": 3.0, "Bolt": 5.0, "Silke": 1.5}
            thresh = thresholds.get(brand_name_val, 3.0)
            if l4w < thresh:
                line_review_risk = f"HIGH — velocity {l4w} U/S/W is below weak threshold ({thresh}); at risk next line review"
            elif st_delta is not None and st_delta < -10 and lt_delta is not None and lt_delta < -10:
                line_review_risk = "MEDIUM — declining trend in both short and long window; monitor closely"
            else:
                line_review_risk = "LOW"

        # OOS escalation signal
        oos_signal = None
        if metric == "oos_rate" and l4w is not None:
            if l4w > 8:
                oos_signal = "CRITICAL — above 8%; Walmart replenishment reduction risk"
            elif l4w > 5:
                oos_signal = "ELEVATED — above 5% Walmart threshold; buyer visibility risk"

        results.append({
            "entity": d["label"],
            "brand": d.get("brand"),
            "metric": metric,
            "unit": "U/S/W" if metric == "velocity" else "%" if "rate" in metric or "yoy" in metric else "$",
            "periods": {"L4W": l4w, "L13W": l13w, "L52W": l52w},
            "short_term_trend": st_trend,
            "short_term_delta_pct": round(st_delta, 1) if st_delta is not None else None,
            "long_term_trend": lt_trend,
            "long_term_delta_pct": round(lt_delta, 1) if lt_delta is not None else None,
            "line_review_risk": line_review_risk,
            "oos_escalation": oos_signal,
        })

    return {
        "results": results,
        "metric": metric,
        "grain": grain,
        "interpretation_note": (
            "Short-term trend = L4W vs L13W (recent momentum). "
            "Long-term trend = L13W vs L52W (structural trajectory). "
            "ACCELERATING + IMPROVING = healthy. DECELERATING + DECLINING = line review risk."
        ),
    }
