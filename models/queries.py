"""
RetailGPT — Pre-built Query Library
Covers all P1 analytical patterns needed by execute_sql tool.
All queries are read-only. No INSERT, UPDATE, DELETE, DROP allowed.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session
from config.settings import MAX_SQL_ROWS


# ─── Safety guard — enforced before every query ───────────────────────────────
BLOCKED_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"}

def _assert_readonly(sql: str):
    """Raise if the SQL contains any mutation keywords."""
    upper = sql.upper()
    for kw in BLOCKED_KEYWORDS:
        if kw in upper:
            raise PermissionError(f"RetailGPT safety: '{kw}' is not permitted. All queries must be read-only.")


def run_raw_sql(session: Session, sql: str, params: dict = None) -> list[dict]:
    """
    Execute a raw SQL string (read-only enforced).
    Returns a list of dicts (one per row), capped at MAX_SQL_ROWS.
    """
    _assert_readonly(sql)
    result = session.execute(text(sql), params or {})
    cols = result.keys()
    rows = result.fetchmany(MAX_SQL_ROWS)
    return [dict(zip(cols, row)) for row in rows]


# ─── P1 Query Templates ───────────────────────────────────────────────────────

def velocity_trend_by_sku_retailer(session: Session, sku_id: str, retailer_name: str, weeks: int = 13) -> list[dict]:
    """
    Trend of velocity (units/store/week) for a SKU at a specific retailer.
    Covers: Req #2 (General Q&A), Req #4 (KPI Narratives), Req #10 (SQL tool use)
    """
    sql = """
        SELECT
            week_ending_date,
            sku_id,
            sku_description,
            retailer_name,
            velocity_per_store,
            dollar_sales,
            unit_sales,
            oos_rate_pct,
            yoy_dollar_growth_pct
        FROM sales_kpi_weekly
        WHERE sku_id        = :sku_id
          AND retailer_name = :retailer_name
        ORDER BY week_ending_date DESC
        LIMIT :weeks
    """
    return run_raw_sql(session, sql, {"sku_id": sku_id, "retailer_name": retailer_name, "weeks": weeks})


def promo_lift_vs_baseline(session: Session, retailer_name: str = None, sku_id: str = None) -> list[dict]:
    """
    Promo lift vs. baseline velocity, with ROI and cannibalization.
    Covers: Req #2, Req #4 (promo analysis), Req #7 (threshold monitoring)
    """
    filters = "WHERE 1=1"
    params = {}
    if retailer_name:
        filters += " AND retailer_name = :retailer_name"
        params["retailer_name"] = retailer_name
    if sku_id:
        filters += " AND sku_id = :sku_id"
        params["sku_id"] = sku_id

    sql = f"""
        SELECT
            promo_id,
            retailer_name,
            sku_id,
            promo_type,
            promo_start_date,
            promo_end_date,
            baseline_velocity,
            promo_velocity,
            promo_lift_pct,
            incremental_units,
            cannibalization_rate_pct,
            promo_roi,
            trade_spend_dollars
        FROM promo_calendar
        {filters}
        ORDER BY promo_start_date DESC
        LIMIT 50
    """
    return run_raw_sql(session, sql, params)


def oos_threshold_breaches(session: Session, threshold_pct: float = 5.0,
                            retailer_name: str = None, weeks_back: int = 4) -> list[dict]:
    """
    SKUs breaching OOS rate threshold — triggers reactive agent alerts.
    Covers: Req #7 (Reactive Insight Agents), Req #5 (Issue Flagging)
    """
    filters = "WHERE oos_rate_pct > :threshold"
    params = {"threshold": threshold_pct}
    if retailer_name:
        filters += " AND retailer_name = :retailer_name"
        params["retailer_name"] = retailer_name

    sql = f"""
        SELECT
            sku_id,
            sku_description,
            retailer_name,
            region,
            week_ending_date,
            oos_rate_pct,
            velocity_per_store,
            dollar_sales
        FROM sales_kpi_weekly
        {filters}
          AND week_ending_date >= date('now', '-{weeks_back * 7} days')
        ORDER BY oos_rate_pct DESC
        LIMIT 100
    """
    return run_raw_sql(session, sql, params)


def top_kpi_summary_for_user(session: Session, user_retailers: list[str],
                               user_regions: list[str], period_weeks: int = 4) -> list[dict]:
    """
    Aggregate KPI summary for a user's configured retailer/region scope.
    Powers: Req #1 ("How Is My Business?" default summary)
    """
    retailer_filter = ""
    params = {"period_weeks": period_weeks * 7}
    if user_retailers:
        placeholders = ",".join([f":r{i}" for i in range(len(user_retailers))])
        retailer_filter = f"AND retailer_name IN ({placeholders})"
        for i, r in enumerate(user_retailers):
            params[f"r{i}"] = r

    region_filter = ""
    if user_regions:
        placeholders = ",".join([f":rg{i}" for i in range(len(user_regions))])
        region_filter = f"AND region IN ({placeholders})"
        for i, r in enumerate(user_regions):
            params[f"rg{i}"] = r

    sql = f"""
        SELECT
            retailer_name,
            SUM(dollar_sales)                                      AS total_dollar_sales,
            SUM(unit_sales)                                        AS total_units,
            AVG(velocity_per_store)                                AS avg_velocity,
            AVG(oos_rate_pct)                                      AS avg_oos_rate,
            AVG(acv_distribution_pct)                              AS avg_acv,
            AVG(yoy_dollar_growth_pct)                             AS avg_yoy_growth,
            COUNT(DISTINCT sku_id)                                 AS active_skus
        FROM sales_kpi_weekly
        WHERE week_ending_date >= date('now', '-' || :period_weeks || ' days')
          {retailer_filter}
          {region_filter}
        GROUP BY retailer_name
        ORDER BY total_dollar_sales DESC
    """
    return run_raw_sql(session, sql, params)


def retailer_account_scorecard(session: Session, retailer_name: str, period: str = None) -> list[dict]:
    """
    Full account scorecard for a retailer — JBP support.
    Covers: Req #22 (Retailer Account View / JBP Intelligence)
    """
    filters = "WHERE retailer_name = :retailer_name"
    params = {"retailer_name": retailer_name}
    if period:
        filters += " AND scorecard_period = :period"
        params["period"] = period

    sql = f"""
        SELECT *
        FROM retailer_account_scorecard
        {filters}
        ORDER BY scorecard_period DESC
        LIMIT 4
    """
    return run_raw_sql(session, sql, params)


def open_alerts_for_user(session: Session, user_retailers: list[str],
                          severity: str = None) -> list[dict]:
    """
    Fetch open/acknowledged alerts for the user's retailer scope.
    Covers: Req #5 (Issue Flagging), Req #7 (Reactive Agents)
    """
    retailer_filter = ""
    params = {}
    if user_retailers:
        placeholders = ",".join([f":r{i}" for i in range(len(user_retailers))])
        retailer_filter = f"AND retailer_name IN ({placeholders})"
        for i, r in enumerate(user_retailers):
            params[f"r{i}"] = r

    severity_filter = ""
    if severity:
        severity_filter = "AND severity = :severity"
        params["severity"] = severity

    sql = f"""
        SELECT *
        FROM kpi_alert_log
        WHERE status IN ('Open', 'Acknowledged')
          {retailer_filter}
          {severity_filter}
        ORDER BY
            CASE severity WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
            alert_timestamp DESC
        LIMIT 50
    """
    return run_raw_sql(session, sql, params)
