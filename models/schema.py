"""
RetailGPT — Database Schema (SQLAlchemy ORM)
Matches the Synthetic Data Schema sheet exactly.
Run `python models/schema.py` to create tables in the prototype DB.
"""

from sqlalchemy import (
    Column, String, Integer, Numeric, Date, DateTime, Text,
    create_engine
)
from sqlalchemy.orm import declarative_base
from config.settings import DB_URL

Base = declarative_base()


class SalesKPIWeekly(Base):
    """TABLE 1: Sales KPIs (Weekly Grain)"""
    __tablename__ = "sales_kpi_weekly"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    week_ending_date      = Column(Date,          nullable=False, index=True)
    retailer_name         = Column(String(100),   nullable=False, index=True)
    region                = Column(String(50),    nullable=False, index=True)
    brand_name            = Column(String(100),   nullable=False, index=True)
    category              = Column(String(100))
    sub_category          = Column(String(100))
    sku_id                = Column(String(20),    nullable=False, index=True)
    sku_description       = Column(String(200))
    upc                   = Column(String(20))
    dollar_sales          = Column(Numeric(12, 2))
    unit_sales            = Column(Integer)
    velocity_per_store    = Column(Numeric(8, 2))   # Units/store/week — primary CPG KPI
    avg_selling_price     = Column(Numeric(6, 2))
    num_stores_selling    = Column(Integer)
    acv_distribution_pct  = Column(Numeric(5, 2))
    oos_rate_pct          = Column(Numeric(5, 2))   # Alert threshold > 5%
    prior_year_dollar_sales = Column(Numeric(12, 2))
    prior_year_unit_sales   = Column(Integer)
    yoy_dollar_growth_pct   = Column(Numeric(6, 2))


class PromoCalendar(Base):
    """TABLE 2: Promotion Calendar & Lift"""
    __tablename__ = "promo_calendar"

    promo_id               = Column(String(30),   primary_key=True)
    retailer_name          = Column(String(100),  nullable=False, index=True)
    sku_id                 = Column(String(20),   nullable=False, index=True)
    promo_start_date       = Column(Date)
    promo_end_date         = Column(Date)
    promo_type             = Column(String(50))   # TPR, Feature, Display, BOGO, Feature+Display
    promo_depth_pct        = Column(Numeric(5, 2))
    baseline_velocity      = Column(Numeric(8, 2))
    promo_velocity         = Column(Numeric(8, 2))
    promo_lift_pct         = Column(Numeric(6, 2))
    incremental_units      = Column(Integer)
    cannibalization_rate_pct = Column(Numeric(5, 2))
    promo_roi              = Column(Numeric(6, 2))  # ROI: 1.0 = breakeven
    trade_spend_dollars    = Column(Numeric(10, 2))


class RetailerAccountScorecard(Base):
    """TABLE 3: Retailer Account Scorecard (Quarterly)"""
    __tablename__ = "retailer_account_scorecard"

    id                         = Column(Integer, primary_key=True, autoincrement=True)
    scorecard_period           = Column(String(10),  nullable=False, index=True)  # e.g. 2026-Q1
    retailer_name              = Column(String(100), nullable=False, index=True)
    brand_name                 = Column(String(100), nullable=False)
    total_dollar_sales         = Column(Numeric(14, 2))
    dollar_share_of_category_pct = Column(Numeric(5, 2))
    distribution_points        = Column(Integer)
    avg_acv_pct                = Column(Numeric(5, 2))
    avg_oos_rate_pct           = Column(Numeric(5, 2))
    total_promo_weeks          = Column(Integer)
    on_shelf_availability_pct  = Column(Numeric(5, 2))
    yoy_sales_growth_pct       = Column(Numeric(6, 2))
    new_items_added            = Column(Integer)
    items_delisted             = Column(Integer)
    buyer_name                 = Column(String(100))
    jbp_target_growth_pct     = Column(Numeric(5, 2))


class KPIAlertLog(Base):
    """TABLE 4: KPI Alert Log (Issues)"""
    __tablename__ = "kpi_alert_log"

    alert_id            = Column(String(30),    primary_key=True)
    alert_timestamp     = Column(DateTime,      nullable=False, index=True)
    alert_type          = Column(String(50),    index=True)  # OOS_BREACH, VELOCITY_DECLINE, etc.
    severity            = Column(String(10),    index=True)  # High, Medium, Low
    sku_id              = Column(String(20),    index=True)
    retailer_name       = Column(String(100),   index=True)
    metric_name         = Column(String(50))
    threshold_value     = Column(Numeric(8, 2))
    actual_value        = Column(Numeric(8, 2))
    root_cause_narrative = Column(Text)         # AI-generated
    status              = Column(String(20),    default="Open")  # Open/Acknowledged/Assigned/Resolved
    assigned_to         = Column(String(200))
    assignment_comment  = Column(Text)
    resolved_timestamp  = Column(DateTime)


class UserPreferences(Base):
    """TABLE 5: User Preferences & Priorities"""
    __tablename__ = "user_preferences"

    user_id                      = Column(String(20),   primary_key=True)
    user_name                    = Column(String(100))
    user_email                   = Column(String(200),  index=True)
    user_role                    = Column(String(50))   # Brand Manager, Category Manager, etc.
    default_narrative_mode       = Column(String(20),   default="Merchant")  # Executive/Merchant/Analyst
    priority_metrics             = Column(String(500))  # CSV: "Revenue, Promo Lift, OOS Rate"
    retailer_scope               = Column(String(500))  # CSV, blank = all
    region_scope                 = Column(String(500))  # CSV, blank = national
    brand_scope                  = Column(String(500))  # CSV, blank = all
    excluded_regions             = Column(String(500))
    oos_alert_threshold_pct      = Column(Numeric(5, 2), default=5.00)
    velocity_decline_threshold_pct = Column(Numeric(5, 2), default=10.00)
    promo_roi_floor              = Column(Numeric(4, 2), default=0.80)
    preferred_time_period        = Column(String(10),   default="L4W")  # L4W, L13W, L52W, YTD
    email_report_cadence         = Column(String(10),   default="Weekly")


# ─── Create all tables ────────────────────────────────────────────────────────
if __name__ == "__main__":
    engine = create_engine(DB_URL, echo=True)
    Base.metadata.create_all(engine)
    print("✅ All RetailGPT tables created.")
