"""
TestGPT — Pre-built Query Library (v2 — SQLite-compatible, anchor-date aware)
All queries are read-only. No INSERT, UPDATE, DELETE, DROP allowed.

Key fix: uses MAX(week_ending_date) as anchor "today" rather than date('now'),
so the demo DB (Jan 2023 – Feb 2025) returns real data regardless of when you run it.
"""

from __future__ import annotations
from datetime import date, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session
from config.settings import MAX_SQL_ROWS

# ─── Safety guard ─────────────────────────────────────────────────────────────
BLOCKED_KEYWORDS = {"INSERT","UPDATE","DELETE","DROP","TRUNCATE","ALTER","CREATE","GRANT","REVOKE"}

def _assert_readonly(sql: str):
    upper = sql.upper()
    for kw in BLOCKED_KEYWORDS:
        if kw in upper:
            raise PermissionError(
                f"TestGPT safety: '{kw}' is not permitted. All queries must be read-only."
            )

def run_raw_sql(session: Session, sql: str, params: dict = None) -> list[dict]:
    """Execute a raw SQL string (read-only enforced). Returns list of dicts."""
    _assert_readonly(sql)
    result = session.execute(text(sql), params or {})
    cols   = list(result.keys())
    rows   = result.fetchmany(MAX_SQL_ROWS)
    return [dict(zip(cols, row)) for row in rows]


# ─── Anchor date helper ───────────────────────────────────────────────────────
_anchor_cache: dict = {}   # simple module-level cache

def get_latest_date(session: Session) -> date:
    """
    Returns the most recent week_ending_date in the DB as a date object.
    Used as the 'today' anchor so all period calculations work against the
    demo dataset regardless of wall-clock date.
    Cached per process after first call.
    """
    if "latest" not in _anchor_cache:
        row = run_raw_sql(session, "SELECT MAX(week_ending_date) AS latest FROM sales_kpi_weekly")
        raw = row[0]["latest"] if row else None
        if raw:
            if isinstance(raw, date):
                _anchor_cache["latest"] = raw
            else:
                _anchor_cache["latest"] = date.fromisoformat(str(raw)[:10])
        else:
            _anchor_cache["latest"] = date.today()
    return _anchor_cache["latest"]


def _period_bounds(session: Session, period_label: str) -> tuple[str, str]:
    """
    Resolve a period label (L4W, L13W, L52W, YTD, or an integer week count)
    to (start_date_str, end_date_str) anchored on the DB's latest date.
    """
    anchor = get_latest_date(session)
    mapping = {"L4W": 4, "L13W": 13, "L26W": 26, "L52W": 52, "YTD": 52}
    weeks   = mapping.get(str(period_label).upper(), 4)
    if isinstance(period_label, int):
        weeks = period_label
    start = anchor - timedelta(weeks=weeks)
    return str(start), str(anchor)


# ─── KPI Aggregation (powers get_kpi_card) ────────────────────────────────────

# Maps user-facing metric name → (aggregation expression, source table column)
METRIC_MAP = {
    "Revenue":              ("SUM(dollar_sales)",           "dollar_sales",           "sales_kpi_weekly"),
    "Units":                ("SUM(unit_sales)",             "unit_sales",             "sales_kpi_weekly"),
    "Velocity":             ("AVG(velocity_per_store)",     "velocity_per_store",     "sales_kpi_weekly"),
    "OOS Rate":             ("AVG(oos_rate_pct)",           "oos_rate_pct",           "sales_kpi_weekly"),
    "ACV":                  ("AVG(acv_distribution_pct)",  "acv_distribution_pct",   "sales_kpi_weekly"),
    "Price":                ("AVG(avg_selling_price)",      "avg_selling_price",      "sales_kpi_weekly"),
    "YoY Growth":           ("AVG(yoy_dollar_growth_pct)", "yoy_dollar_growth_pct",  "sales_kpi_weekly"),
    "Distribution Points":  ("COUNT(DISTINCT sku_id)",     None,                     "sales_kpi_weekly"),
    "Promo Lift":           ("AVG(promo_lift_pct)",        "promo_lift_pct",         "promo_calendar"),
    "Promo ROI":            ("AVG(promo_roi)",             "promo_roi",              "promo_calendar"),
    "Trade Spend":          ("SUM(trade_spend_dollars)",   "trade_spend_dollars",    "promo_calendar"),
}

def kpi_aggregate(
    session: Session,
    metric: str,
    period_weeks: int = 4,
    retailers: list[str] = None,
    regions: list[str] = None,
    sku_id: str = None,
    brand_name: str = None,
) -> dict:
    """
    Return current + prior period aggregate for a single KPI metric.
    Prior period = same number of weeks immediately before the current window.
    Returns: { metric, current_value, prior_value, delta_pct, trend, period_label, unit }
    """
    anchor = get_latest_date(session)
    end_dt   = anchor
    start_dt = end_dt   - timedelta(weeks=period_weeks)
    prior_end = start_dt - timedelta(days=1)
    prior_start = prior_end - timedelta(weeks=period_weeks)

    # Normalize metric name (case-insensitive lookup)
    normalized = None
    for k in METRIC_MAP:
        if k.lower() == metric.lower():
            normalized = k
            break
    if not normalized:
        return {"metric": metric, "error": f"Unknown metric '{metric}'. Valid: {list(METRIC_MAP.keys())}"}

    agg_expr, _, table = METRIC_MAP[normalized]
    unit = _metric_unit(normalized)

    def _query_period(start: date, end: date) -> float | None:
        params: dict = {"start": str(start), "end": str(end)}
        where_parts = ["week_ending_date >= :start", "week_ending_date <= :end"]

        if table == "sales_kpi_weekly":
            if retailers:
                ph = ",".join([f":r{i}" for i in range(len(retailers))])
                where_parts.append(f"retailer_name IN ({ph})")
                for i, r in enumerate(retailers): params[f"r{i}"] = r
            if regions:
                ph = ",".join([f":rg{i}" for i in range(len(regions))])
                where_parts.append(f"region IN ({ph})")
                for i, r in enumerate(regions): params[f"rg{i}"] = r
            if sku_id:
                where_parts.append("sku_id = :sku_id"); params["sku_id"] = sku_id
            if brand_name:
                where_parts.append("brand_name = :brand_name"); params["brand_name"] = brand_name
            sql = f"SELECT {agg_expr} AS val FROM sales_kpi_weekly WHERE {' AND '.join(where_parts)}"

        else:  # promo_calendar — use promo_start_date as the date column
            params = {"start": str(start), "end": str(end)}
            where_parts = ["promo_start_date >= :start", "promo_start_date <= :end"]
            if retailers:
                ph = ",".join([f":r{i}" for i in range(len(retailers))])
                where_parts.append(f"retailer_name IN ({ph})")
                for i, r in enumerate(retailers): params[f"r{i}"] = r
            if sku_id:
                where_parts.append("sku_id = :sku_id"); params["sku_id"] = sku_id
            sql = f"SELECT {agg_expr} AS val FROM promo_calendar WHERE {' AND '.join(where_parts)}"

        rows = run_raw_sql(session, sql, params)
        val  = rows[0]["val"] if rows else None
        return float(val) if val is not None else None

    current = _query_period(start_dt, end_dt)
    prior   = _query_period(prior_start, prior_end)

    delta_pct = None
    trend     = "flat"
    if current is not None and prior and prior != 0:
        delta_pct = round((current - prior) / abs(prior) * 100, 2)
        if delta_pct > 1:
            trend = "up"
        elif delta_pct < -1:
            trend = "down"

    return {
        "metric":          normalized,
        "current_value":   round(current, 4) if current is not None else None,
        "prior_value":     round(prior, 4)   if prior   is not None else None,
        "delta_pct":       delta_pct,
        "trend":           trend,
        "period_label":    f"L{period_weeks}W",
        "period_start":    str(start_dt),
        "period_end":      str(end_dt),
        "prior_start":     str(prior_start),
        "prior_end":       str(prior_end),
        "unit":            unit,
        "filters_applied": {
            "retailers": retailers or [],
            "regions":   regions   or [],
            "sku_id":    sku_id,
            "brand_name": brand_name,
        },
    }


def _metric_unit(metric: str) -> str:
    units = {
        "Revenue": "$", "Trade Spend": "$",
        "Units": "units", "Distribution Points": "SKUs",
        "Velocity": "U/S/W", "OOS Rate": "%", "ACV": "%",
        "Price": "$/unit", "YoY Growth": "%", "Promo Lift": "%", "Promo ROI": "x",
    }
    return units.get(metric, "")


# ─── Business Summary (Req #1 — "How Is My Business?") ────────────────────────

def business_summary(
    session: Session,
    priority_metrics: list[str],
    period_weeks: int = 4,
    retailers: list[str] = None,
    regions: list[str] = None,
    brand_name: str = None,
) -> dict:
    """
    Pull KPI cards for all priority_metrics and rank changes.
    Returns structured summary ready for narrative generation.
    """
    cards = []
    for metric in priority_metrics:
        card = kpi_aggregate(session, metric, period_weeks, retailers, regions, brand_name=brand_name)
        if "error" not in card:
            cards.append(card)

    # Sort by absolute delta descending (biggest moves first)
    cards.sort(key=lambda c: abs(c.get("delta_pct") or 0), reverse=True)

    return {
        "period_label":   f"L{period_weeks}W",
        "anchor_date":    str(get_latest_date(session)),
        "kpi_cards":      cards,
        "top_movers":     cards[:3],
        "retailer_scope": retailers or ["All"],
        "region_scope":   regions   or ["National"],
    }


# ─── Velocity Trend ───────────────────────────────────────────────────────────

def velocity_trend_by_sku_retailer(
    session: Session,
    sku_id: str,
    retailer_name: str,
    weeks: int = 13,
    region: str = None,
) -> list[dict]:
    """Weekly velocity trend for a SKU at a retailer (optionally by region)."""
    params = {"sku_id": sku_id, "retailer": retailer_name, "weeks": weeks}
    region_filter = ""
    if region:
        region_filter = "AND region = :region"
        params["region"] = region
    sql = f"""
        SELECT
            week_ending_date,
            sku_id,
            sku_description,
            retailer_name,
            region,
            ROUND(AVG(velocity_per_store),3)   AS velocity_per_store,
            SUM(dollar_sales)                   AS dollar_sales,
            SUM(unit_sales)                     AS unit_sales,
            ROUND(AVG(oos_rate_pct),2)          AS oos_rate_pct,
            ROUND(AVG(yoy_dollar_growth_pct),2) AS yoy_dollar_growth_pct
        FROM sales_kpi_weekly
        WHERE sku_id        = :sku_id
          AND retailer_name = :retailer
          {region_filter}
        GROUP BY week_ending_date, sku_id, sku_description, retailer_name, region
        ORDER BY week_ending_date DESC
        LIMIT :weeks
    """
    return run_raw_sql(session, sql, params)


# ─── Top SKU ranking ──────────────────────────────────────────────────────────

def top_skus_by_metric(
    session: Session,
    metric: str = "Revenue",
    retailer_name: str = None,
    period_weeks: int = 4,
    limit: int = 10,
    brand_name: str = None,
) -> list[dict]:
    """Rank SKUs by a metric for the current period."""
    anchor = get_latest_date(session)
    start  = anchor - timedelta(weeks=period_weeks)
    metric_col = {
        "Revenue": "SUM(dollar_sales)",
        "Units":   "SUM(unit_sales)",
        "Velocity":"AVG(velocity_per_store)",
        "OOS Rate":"AVG(oos_rate_pct)",
    }.get(metric, "SUM(dollar_sales)")
    params: dict = {"start": str(start), "end": str(anchor), "limit": limit}
    filters = ["week_ending_date >= :start", "week_ending_date <= :end"]
    if retailer_name:
        filters.append("retailer_name = :retailer"); params["retailer"] = retailer_name
    if brand_name:
        filters.append("brand_name = :brand"); params["brand"] = brand_name
    sql = f"""
        SELECT
            sku_id, sku_description, brand_name,
            {metric_col} AS metric_value,
            COUNT(DISTINCT retailer_name) AS retailer_count,
            ROUND(AVG(oos_rate_pct),2) AS avg_oos,
            ROUND(AVG(yoy_dollar_growth_pct),2) AS avg_yoy
        FROM sales_kpi_weekly
        WHERE {" AND ".join(filters)}
        GROUP BY sku_id, sku_description, brand_name
        ORDER BY metric_value DESC
        LIMIT :limit
    """
    return run_raw_sql(session, sql, params)


# ─── Promo analysis ───────────────────────────────────────────────────────────

def promo_lift_vs_baseline(
    session: Session,
    retailer_name: str = None,
    sku_id: str = None,
    brand_name: str = None,
    limit: int = 50,
) -> list[dict]:
    """Promo events with lift vs baseline, ROI, cannibalization."""
    filters  = ["1=1"]
    params: dict = {"limit": limit}
    if retailer_name:
        filters.append("p.retailer_name = :retailer"); params["retailer"] = retailer_name
    if sku_id:
        filters.append("p.sku_id = :sku_id"); params["sku_id"] = sku_id
    if brand_name:
        filters.append("s.brand_name = :brand"); params["brand"] = brand_name
    sql = f"""
        SELECT
            p.promo_id, p.retailer_name, p.sku_id, s.sku_description, s.brand_name,
            p.promo_type, p.promo_start_date, p.promo_end_date,
            p.promo_depth_pct, p.baseline_velocity, p.promo_velocity,
            p.promo_lift_pct, p.incremental_units, p.cannibalization_rate_pct,
            p.promo_roi, p.trade_spend_dollars
        FROM promo_calendar p
        LEFT JOIN (
            SELECT DISTINCT sku_id, sku_description, brand_name FROM sales_kpi_weekly
        ) s ON p.sku_id = s.sku_id
        WHERE {" AND ".join(filters)}
        ORDER BY p.promo_start_date DESC
        LIMIT :limit
    """
    return run_raw_sql(session, sql, params)


# ─── OOS breaches ─────────────────────────────────────────────────────────────

def oos_threshold_breaches(
    session: Session,
    threshold_pct: float = 5.0,
    retailer_name: str = None,
    weeks_back: int = 4,
    brand_name: str = None,
) -> list[dict]:
    """SKUs currently breaching OOS threshold."""
    anchor = get_latest_date(session)
    start  = anchor - timedelta(weeks=weeks_back)
    params: dict = {"threshold": threshold_pct, "start": str(start), "end": str(anchor)}
    filters = ["oos_rate_pct > :threshold", "week_ending_date >= :start", "week_ending_date <= :end"]
    if retailer_name:
        filters.append("retailer_name = :retailer"); params["retailer"] = retailer_name
    if brand_name:
        filters.append("brand_name = :brand"); params["brand"] = brand_name
    sql = f"""
        SELECT
            sku_id, sku_description, brand_name, retailer_name, region,
            week_ending_date,
            ROUND(oos_rate_pct,2) AS oos_rate_pct,
            ROUND(velocity_per_store,3) AS velocity_per_store,
            dollar_sales
        FROM sales_kpi_weekly
        WHERE {" AND ".join(filters)}
        ORDER BY oos_rate_pct DESC
        LIMIT 100
    """
    return run_raw_sql(session, sql, params)


# ─── KPI summary for user scope ───────────────────────────────────────────────

def top_kpi_summary_for_user(
    session: Session,
    user_retailers: list[str],
    user_regions: list[str],
    period_weeks: int = 4,
) -> list[dict]:
    """Aggregate KPI summary by retailer for the user's scope."""
    anchor = get_latest_date(session)
    start  = anchor - timedelta(weeks=period_weeks)
    params: dict = {"start": str(start), "end": str(anchor)}
    filters = ["week_ending_date >= :start", "week_ending_date <= :end"]
    if user_retailers:
        ph = ",".join([f":r{i}" for i in range(len(user_retailers))])
        filters.append(f"retailer_name IN ({ph})")
        for i, r in enumerate(user_retailers): params[f"r{i}"] = r
    if user_regions:
        ph = ",".join([f":rg{i}" for i in range(len(user_regions))])
        filters.append(f"region IN ({ph})")
        for i, r in enumerate(user_regions): params[f"rg{i}"] = r
    sql = f"""
        SELECT
            retailer_name,
            ROUND(SUM(dollar_sales),2)          AS total_dollar_sales,
            SUM(unit_sales)                     AS total_units,
            ROUND(AVG(velocity_per_store),3)    AS avg_velocity,
            ROUND(AVG(oos_rate_pct),2)          AS avg_oos_rate,
            ROUND(AVG(acv_distribution_pct),2)  AS avg_acv,
            ROUND(AVG(yoy_dollar_growth_pct),2) AS avg_yoy_growth,
            COUNT(DISTINCT sku_id)              AS active_skus
        FROM sales_kpi_weekly
        WHERE {" AND ".join(filters)}
        GROUP BY retailer_name
        ORDER BY total_dollar_sales DESC
    """
    return run_raw_sql(session, sql, params)


# ─── Retailer scorecard ───────────────────────────────────────────────────────

def retailer_account_scorecard(session: Session, retailer_name: str, period: str = None) -> list[dict]:
    """Quarterly account scorecard — JBP support."""
    params: dict = {"retailer": retailer_name}
    filters = ["retailer_name = :retailer"]
    if period:
        filters.append("scorecard_period = :period"); params["period"] = period
    sql = f"""
        SELECT * FROM retailer_account_scorecard
        WHERE {" AND ".join(filters)}
        ORDER BY scorecard_period DESC
        LIMIT 4
    """
    return run_raw_sql(session, sql, params)


# ─── Open alerts ─────────────────────────────────────────────────────────────

def open_alerts_for_user(
    session: Session,
    user_retailers: list[str],
    severity: str = None,
    limit: int = 50,
) -> list[dict]:
    """Fetch open/acknowledged alerts for the user's retailer scope."""
    params: dict = {"limit": limit}
    filters = ["status IN ('Open', 'Acknowledged')"]
    if user_retailers:
        ph = ",".join([f":r{i}" for i in range(len(user_retailers))])
        filters.append(f"retailer_name IN ({ph})")
        for i, r in enumerate(user_retailers): params[f"r{i}"] = r
    if severity:
        filters.append("severity = :severity"); params["severity"] = severity
    sql = f"""
        SELECT * FROM kpi_alert_log
        WHERE {" AND ".join(filters)}
        ORDER BY
            CASE severity WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
            alert_timestamp DESC
        LIMIT :limit
    """
    return run_raw_sql(session, sql, params)


# ─── Revenue breakdown by brand/SKU ───────────────────────────────────────────

def revenue_by_brand(
    session: Session,
    retailer_name: str = None,
    period_weeks: int = 4,
    region: str = None,
) -> list[dict]:
    """Dollar sales breakdown by brand for pie/bar charts."""
    anchor = get_latest_date(session)
    start  = anchor - timedelta(weeks=period_weeks)
    params: dict = {"start": str(start), "end": str(anchor)}
    filters = ["week_ending_date >= :start", "week_ending_date <= :end"]
    if retailer_name:
        filters.append("retailer_name = :retailer"); params["retailer"] = retailer_name
    if region:
        filters.append("region = :region"); params["region"] = region
    sql = f"""
        SELECT
            brand_name,
            ROUND(SUM(dollar_sales),2) AS total_sales,
            SUM(unit_sales) AS total_units,
            ROUND(AVG(velocity_per_store),3) AS avg_velocity,
            ROUND(AVG(yoy_dollar_growth_pct),2) AS avg_yoy
        FROM sales_kpi_weekly
        WHERE {" AND ".join(filters)}
        GROUP BY brand_name
        ORDER BY total_sales DESC
    """
    return run_raw_sql(session, sql, params)
