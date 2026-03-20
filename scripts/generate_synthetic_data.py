"""
TestGPT — Synthetic Data Generator
Generates ~2 years of realistic CPG weekly data (Jan 2023 – Feb 2025).
Seeds all 5 tables: sales_kpi_weekly, promo_calendar, retailer_account_scorecard,
                    kpi_alert_log, user_preferences.

Usage:
    python scripts/generate_synthetic_data.py

Output:
    testgpt_prototype.db (SQLite) in project root
    Also writes CSVs to scripts/data/ for inspection

All outputs labeled [SYNTHETIC DATA — DEMO ONLY]
"""

import random
import math
import uuid
import os
import csv
import sys
from datetime import date, timedelta, datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models.schema import Base, SalesKPIWeekly, PromoCalendar, RetailerAccountScorecard, KPIAlertLog, UserPreferences
from config.settings import DB_URL

# ─── Seed for reproducibility ─────────────────────────────────────────────────
random.seed(42)

# ─── Master reference data ────────────────────────────────────────────────────
RETAILERS = ["Walmart", "Target", "Kroger", "Costco", "Amazon", "CVS", "Walgreens", "Albertsons"]

REGIONS = ["Southeast", "Northeast", "Midwest", "West", "South Central"]

BRANDS = {
    "Brand A": {
        "category": "Snacks",
        "sub_category": "Salty Snacks",
        "base_velocity": 4.50,
        "base_price": 4.99,
        "base_stores": {"Walmart": 3800, "Target": 1600, "Kroger": 1200, "Costco": 550,
                        "Amazon": 0, "CVS": 400, "Walgreens": 350, "Albertsons": 500},
    },
    "Brand B": {
        "category": "Beverages",
        "sub_category": "Energy Drinks",
        "base_velocity": 6.20,
        "base_price": 2.49,
        "base_stores": {"Walmart": 3600, "Target": 1500, "Kroger": 1100, "Costco": 480,
                        "Amazon": 0, "CVS": 550, "Walgreens": 500, "Albertsons": 420},
    },
    "Brand C": {
        "category": "Personal Care",
        "sub_category": "Hair Care",
        "base_velocity": 2.80,
        "base_price": 8.99,
        "base_stores": {"Walmart": 3200, "Target": 1800, "Kroger": 900, "Costco": 300,
                        "Amazon": 0, "CVS": 700, "Walgreens": 650, "Albertsons": 380},
    },
}

# SKUs per brand — 10 each = 30 total
SKUS = {}
for brand_name, brand_info in BRANDS.items():
    prefix = brand_name.split()[-1]  # A, B, C
    sizes  = ["4oz", "8oz", "12oz", "16oz", "24oz", "32oz", "6pk", "12pk", "Value", "XL"]
    flavors = ["Original", "Bold", "Lite", "Premium", "Classic", "Pro", "Max", "Pure", "Fresh", "Wild"]
    for i, (size, flavor) in enumerate(zip(sizes, flavors)):
        sku_id = f"SKU-{prefix}{i+1:02d}"
        SKUS[sku_id] = {
            "brand": brand_name,
            "description": f"{brand_name} {size} {flavor}",
            "upc": f"0-{random.randint(10000,99999)}-{random.randint(10000,99999)}-{i}",
            "velocity_mult": random.uniform(0.5, 1.8),   # relative to brand base
            "price_mult": random.uniform(0.7, 1.5),
            "store_mult": random.uniform(0.4, 1.0),
            "is_hero": i < 3,  # top 3 SKUs per brand are hero items
        }

# ─── Date range: Jan 2023 – Feb 2025 (weekly, Saturday week-ending) ──────────
def get_week_dates(start: date, end: date):
    """Return all Saturday week-ending dates in range."""
    dates = []
    # Find first Saturday on or after start
    d = start
    while d.weekday() != 5:  # 5 = Saturday
        d += timedelta(days=1)
    while d <= end:
        dates.append(d)
        d += timedelta(weeks=1)
    return dates

WEEK_DATES = get_week_dates(date(2023, 1, 7), date(2025, 2, 22))
print(f"Generating {len(WEEK_DATES)} weeks of data ({WEEK_DATES[0]} → {WEEK_DATES[-1]})")

# ─── Seasonal index (CPG-realistic annual pattern) ────────────────────────────
def seasonal_index(d: date) -> float:
    """Return a seasonal multiplier for a given date. Peak in summer/holiday."""
    week_of_year = d.timetuple().tm_yday / 7
    # Dual peak: summer (week 26) and holiday (week 50)
    summer   = 0.15 * math.sin(math.pi * (week_of_year - 10) / 26)
    holiday  = 0.20 * math.sin(math.pi * (week_of_year - 35) / 20) if week_of_year > 35 else 0
    return 1.0 + summer + holiday

# ─── Long-term growth trend ───────────────────────────────────────────────────
def growth_trend(d: date) -> float:
    """Simulate ~8% annual YoY growth with some noise."""
    weeks_since_start = (d - date(2023, 1, 1)).days / 7
    return 1.0 + (0.08 / 52) * weeks_since_start + random.gauss(0, 0.005)

# ─── Promo schedule (pre-planned) ────────────────────────────────────────────
def build_promo_schedule():
    """Generate a realistic promo calendar for 2023-2025."""
    promos = []
    promo_counter = 1
    promo_types = ["TPR", "Feature", "Display", "Feature+Display", "BOGO"]
    promo_weights = [0.40, 0.20, 0.15, 0.15, 0.10]

    for year in [2023, 2024, 2025]:
        for brand_name in BRANDS:
            skus_for_brand = [s for s, v in SKUS.items() if v["brand"] == brand_name]
            hero_skus = [s for s in skus_for_brand if SKUS[s]["is_hero"]]

            for retailer in ["Walmart", "Target", "Kroger", "Albertsons"]:
                # ~6-8 promo events per brand per retailer per year on hero SKUs
                n_promos = random.randint(5, 8)
                used_starts = []

                for _ in range(n_promos):
                    # Find a non-overlapping 2-week window
                    attempts = 0
                    while attempts < 20:
                        start_week = random.randint(1, 50)
                        start_d = date(year, 1, 1) + timedelta(weeks=start_week)
                        # Find next Saturday
                        while start_d.weekday() != 5:
                            start_d += timedelta(days=1)
                        end_d = start_d + timedelta(days=13)

                        # Check no overlap with existing promos for same brand/retailer
                        overlap = any(abs((start_d - s).days) < 14 for s in used_starts)
                        if not overlap and end_d <= date(year + 1, 1, 1):
                            break
                        attempts += 1
                    else:
                        continue

                    used_starts.append(start_d)
                    sku_id = random.choice(hero_skus)
                    brand_info = BRANDS[brand_name]
                    promo_type = random.choices(promo_types, weights=promo_weights)[0]
                    depth = random.uniform(10, 35) if promo_type != "BOGO" else 50
                    base_vel = brand_info["base_velocity"] * SKUS[sku_id]["velocity_mult"]
                    lift_pct = random.uniform(8, 60) * (1.5 if promo_type in ["Feature+Display", "BOGO"] else 1.0)
                    promo_vel = base_vel * (1 + lift_pct / 100)
                    stores = brand_info["base_stores"][retailer] * SKUS[sku_id]["store_mult"]
                    incr_units = int((promo_vel - base_vel) * stores * 2)
                    cannib = random.uniform(0, 15)
                    trade_spend = random.uniform(8000, 180000)
                    roi = (incr_units * brand_info["base_price"] * SKUS[sku_id]["price_mult"] * 0.25) / max(trade_spend, 1)

                    promos.append({
                        "promo_id": f"PROMO-{year}-{promo_counter:04d}",
                        "retailer_name": retailer,
                        "sku_id": sku_id,
                        "promo_start_date": start_d,
                        "promo_end_date": end_d,
                        "promo_type": promo_type,
                        "promo_depth_pct": round(depth, 2),
                        "baseline_velocity": round(base_vel, 2),
                        "promo_velocity": round(promo_vel, 2),
                        "promo_lift_pct": round(lift_pct, 2),
                        "incremental_units": max(incr_units, 0),
                        "cannibalization_rate_pct": round(cannib, 2),
                        "promo_roi": round(roi, 2),
                        "trade_spend_dollars": round(trade_spend, 2),
                    })
                    promo_counter += 1
    return promos

PROMO_SCHEDULE = build_promo_schedule()
print(f"Generated {len(PROMO_SCHEDULE)} promo events")

def get_active_promo(sku_id: str, retailer: str, week_date: date):
    """Return the active promo for a SKU/retailer on a given week, or None."""
    for p in PROMO_SCHEDULE:
        if (p["sku_id"] == sku_id and
                p["retailer_name"] == retailer and
                p["promo_start_date"] <= week_date <= p["promo_end_date"]):
            return p
    return None


# ─── Generate sales_kpi_weekly rows ──────────────────────────────────────────
def generate_sales_rows():
    rows = []
    for week_date in WEEK_DATES:
        season = seasonal_index(week_date)
        trend  = growth_trend(week_date)

        for sku_id, sku_info in SKUS.items():
            brand_name  = sku_info["brand"]
            brand_info  = BRANDS[brand_name]

            for retailer in RETAILERS:
                # Amazon doesn't have traditional store counts
                if retailer == "Amazon" and brand_info["category"] != "Beverages":
                    if random.random() < 0.7:
                        continue  # sparse Amazon presence for non-beverage

                base_stores = brand_info["base_stores"][retailer] * sku_info["store_mult"]
                if base_stores < 50:
                    continue  # not distributed at this retailer

                for region in REGIONS:
                    region_mult = {"Southeast": 1.05, "Northeast": 0.95, "Midwest": 1.00,
                                   "West": 1.10, "South Central": 0.92}[region]
                    stores = int(base_stores * region_mult / len(REGIONS) * random.uniform(0.88, 1.12))
                    if stores < 20:
                        continue

                    base_vel = brand_info["base_velocity"] * sku_info["velocity_mult"]
                    price    = brand_info["base_price"] * sku_info["price_mult"]

                    # Apply trend + season + noise
                    vel = base_vel * trend * season * region_mult * random.uniform(0.85, 1.15)

                    # Check for active promo
                    promo = get_active_promo(sku_id, retailer, week_date)
                    if promo:
                        vel = promo["promo_velocity"] * region_mult * random.uniform(0.90, 1.10)
                        price *= (1 - promo["promo_depth_pct"] / 100)

                    units = int(vel * stores)
                    dollar_sales = units * price

                    # OOS rate — higher during promos, occasionally spikes
                    oos_base = random.gauss(2.5, 1.0)
                    if promo:
                        oos_base += random.uniform(1, 6)  # promo demand spikes can cause OOS
                    if random.random() < 0.03:
                        oos_base += random.uniform(5, 12)  # occasional OOS event
                    oos_rate = max(0.5, min(oos_base, 25.0))

                    # Prior year (same week last year, with growth backed out)
                    py_vel = base_vel * seasonal_index(week_date - timedelta(weeks=52)) * region_mult
                    py_units = int(py_vel * stores * 0.93)  # ~7% fewer stores/velocity last year
                    py_sales = py_units * brand_info["base_price"] * sku_info["price_mult"]
                    yoy_growth = (dollar_sales - py_sales) / max(py_sales, 1) * 100

                    rows.append({
                        "week_ending_date": week_date,
                        "retailer_name": retailer,
                        "region": region,
                        "brand_name": brand_name,
                        "category": brand_info["category"],
                        "sub_category": brand_info["sub_category"],
                        "sku_id": sku_id,
                        "sku_description": sku_info["description"],
                        "upc": sku_info["upc"],
                        "dollar_sales": round(dollar_sales, 2),
                        "unit_sales": units,
                        "velocity_per_store": round(vel, 2),
                        "avg_selling_price": round(price, 2),
                        "num_stores_selling": stores,
                        "acv_distribution_pct": round(min(95, random.gauss(72, 8)), 2),
                        "oos_rate_pct": round(oos_rate, 2),
                        "prior_year_dollar_sales": round(py_sales, 2),
                        "prior_year_unit_sales": py_units,
                        "yoy_dollar_growth_pct": round(yoy_growth, 2),
                    })
    return rows


# ─── Generate retailer_account_scorecard rows (quarterly) ────────────────────
def generate_scorecards():
    rows = []
    periods = ["2023-Q1", "2023-Q2", "2023-Q3", "2023-Q4",
               "2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4", "2025-Q1"]
    buyers = {
        "Walmart": "Jennifer Martinez", "Target": "Michael Chen",
        "Kroger": "Sarah Johnson", "Costco": "David Kim",
        "Amazon": "Rachel Thompson", "CVS": "James Williams",
        "Walgreens": "Emily Davis", "Albertsons": "Robert Wilson"
    }
    for period in periods:
        year = int(period[:4])
        trend = 1.0 + 0.08 * (year - 2023)
        for brand_name in BRANDS:
            for retailer in RETAILERS:
                if BRANDS[brand_name]["base_stores"][retailer] < 100:
                    continue
                base_sales = BRANDS[brand_name]["base_stores"][retailer] * BRANDS[brand_name]["base_velocity"] * BRANDS[brand_name]["base_price"] * 13  # ~13 weeks per quarter
                rows.append({
                    "scorecard_period": period,
                    "retailer_name": retailer,
                    "brand_name": brand_name,
                    "total_dollar_sales": round(base_sales * trend * random.uniform(0.88, 1.12), 2),
                    "dollar_share_of_category_pct": round(random.uniform(4, 22), 2),
                    "distribution_points": random.randint(8, 28),
                    "avg_acv_pct": round(random.uniform(55, 88), 2),
                    "avg_oos_rate_pct": round(random.uniform(2, 8), 2),
                    "total_promo_weeks": random.randint(4, 18),
                    "on_shelf_availability_pct": round(random.uniform(90, 99), 2),
                    "yoy_sales_growth_pct": round(random.gauss(8, 6), 2),
                    "new_items_added": random.randint(0, 4),
                    "items_delisted": random.randint(0, 2),
                    "buyer_name": buyers[retailer],
                    "jbp_target_growth_pct": round(random.uniform(5, 12), 2),
                })
    return rows


# ─── Generate kpi_alert_log rows ──────────────────────────────────────────────
def generate_alerts():
    rows = []
    counter = 1
    alert_types = [
        ("OOS_BREACH",      "High",   "OOS rate {actual:.1f}% at {retailer} exceeded {threshold:.0f}% threshold for {sku}. DC safety stock may be depleted following recent promotional demand spike."),
        ("VELOCITY_DECLINE","Medium", "Velocity for {sku} at {retailer} declined {actual:.1f}% week-over-week, below the {threshold:.0f}% alert threshold. Possible competitive distribution gain or shelf reset impact."),
        ("PROMO_ROI_MISS",  "Medium", "Promotion ROI for {sku} at {retailer} came in at {actual:.2f}x vs. {threshold:.2f}x target. Trade spend efficiency below breakeven."),
        ("DISTRIBUTION_LOSS","Low",   "ACV distribution for {sku} at {retailer} dropped {actual:.1f} points. Possible delist or planogram reset. Verify item status with buyer."),
    ]
    statuses = ["Open", "Open", "Open", "Acknowledged", "Assigned", "Resolved"]
    assignees = ["john.smith@company.com", "sarah.jones@company.com", "mike.chen@company.com"]

    all_skus = list(SKUS.keys())
    all_dates = [d for d in WEEK_DATES if d >= date(2023, 6, 1)]

    for _ in range(120):
        alert_type, severity, narrative_template = random.choice(alert_types)
        sku_id = random.choice(all_skus)
        retailer = random.choice(RETAILERS[:6])
        alert_date = random.choice(all_dates)
        threshold = {"OOS_BREACH": 5.0, "VELOCITY_DECLINE": 10.0, "PROMO_ROI_MISS": 1.0, "DISTRIBUTION_LOSS": 5.0}[alert_type]
        actual = threshold + random.uniform(1, 12) if alert_type != "PROMO_ROI_MISS" else random.uniform(0.2, 0.95)
        status = random.choice(statuses)
        narrative = narrative_template.format(
            sku=SKUS[sku_id]["description"], retailer=retailer,
            actual=actual, threshold=threshold
        )
        assigned_to = random.choice(assignees) if status in ["Assigned", "Resolved"] else None
        resolved_ts = datetime(alert_date.year, alert_date.month, alert_date.day) + timedelta(days=random.randint(1, 5)) if status == "Resolved" else None

        rows.append({
            "alert_id": f"ALERT-{alert_date.strftime('%Y%m%d')}-{counter:04d}",
            "alert_timestamp": datetime(alert_date.year, alert_date.month, alert_date.day, 8, 0),
            "alert_type": alert_type,
            "severity": severity,
            "sku_id": sku_id,
            "retailer_name": retailer,
            "metric_name": alert_type.replace("_", " ").title(),
            "threshold_value": threshold,
            "actual_value": round(actual, 2),
            "root_cause_narrative": narrative,
            "status": status,
            "assigned_to": assigned_to,
            "assignment_comment": f"Please review and take action." if assigned_to else None,
            "resolved_timestamp": resolved_ts,
        })
        counter += 1
    return rows


# ─── Generate user_preferences rows ──────────────────────────────────────────
def generate_users():
    return [
        {
            "user_id": "USR-001",
            "user_name": "Sarah Johnson",
            "user_email": "sarah.johnson@company.com",
            "user_role": "Brand Manager",
            "default_narrative_mode": "Merchant",
            "priority_metrics": "Revenue,Velocity,OOS Rate",
            "retailer_scope": "Walmart,Target,Kroger",
            "region_scope": "",
            "brand_scope": "Brand A",
            "excluded_regions": "",
            "oos_alert_threshold_pct": 5.00,
            "velocity_decline_threshold_pct": 10.00,
            "promo_roi_floor": 0.80,
            "preferred_time_period": "L4W",
            "email_report_cadence": "Weekly",
        },
        {
            "user_id": "USR-002",
            "user_name": "Michael Chen",
            "user_email": "michael.chen@company.com",
            "user_role": "Sales Director",
            "default_narrative_mode": "Executive",
            "priority_metrics": "Revenue,Promo Lift,Distribution Points",
            "retailer_scope": "Walmart,Costco",
            "region_scope": "Southeast,Midwest",
            "brand_scope": "",
            "excluded_regions": "",
            "oos_alert_threshold_pct": 7.00,
            "velocity_decline_threshold_pct": 15.00,
            "promo_roi_floor": 1.00,
            "preferred_time_period": "L13W",
            "email_report_cadence": "Weekly",
        },
        {
            "user_id": "USR-003",
            "user_name": "Rachel Thompson",
            "user_email": "rachel.thompson@company.com",
            "user_role": "Category Manager",
            "default_narrative_mode": "Analyst",
            "priority_metrics": "Velocity,OOS Rate,ACV,Promo ROI",
            "retailer_scope": "Kroger,Albertsons,CVS",
            "region_scope": "West,Northeast",
            "brand_scope": "Brand B,Brand C",
            "excluded_regions": "",
            "oos_alert_threshold_pct": 4.00,
            "velocity_decline_threshold_pct": 8.00,
            "promo_roi_floor": 0.90,
            "preferred_time_period": "L4W",
            "email_report_cadence": "Daily",
        },
        {
            "user_id": "USR-004",
            "user_name": "James Williams",
            "user_email": "james.williams@company.com",
            "user_role": "Retail Ops VP",
            "default_narrative_mode": "Executive",
            "priority_metrics": "Revenue,OOS Rate,OTIF",
            "retailer_scope": "",
            "region_scope": "",
            "brand_scope": "",
            "excluded_regions": "Puerto Rico",
            "oos_alert_threshold_pct": 6.00,
            "velocity_decline_threshold_pct": 12.00,
            "promo_roi_floor": 0.75,
            "preferred_time_period": "L52W",
            "email_report_cadence": "Weekly",
        },
        {
            "user_id": "USR-005",
            "user_name": "Emily Davis",
            "user_email": "emily.davis@company.com",
            "user_role": "Analyst",
            "default_narrative_mode": "Analyst",
            "priority_metrics": "Velocity,YoY Growth,Promo Lift,Cannibalization",
            "retailer_scope": "",
            "region_scope": "",
            "brand_scope": "Brand A",
            "excluded_regions": "",
            "oos_alert_threshold_pct": 3.00,
            "velocity_decline_threshold_pct": 5.00,
            "promo_roi_floor": 1.20,
            "preferred_time_period": "L13W",
            "email_report_cadence": "None",
        },
    ]


# ─── Seed the database ────────────────────────────────────────────────────────
def main():
    output_dir = Path(__file__).parent / "data"
    output_dir.mkdir(exist_ok=True)

    engine = create_engine(DB_URL, echo=False)
    Base.metadata.create_all(engine)
    print(f"✅ Tables created in: {DB_URL}")

    with Session(engine) as session:
        # 1. Users
        print("Seeding user_preferences...")
        users = generate_users()
        for u in users:
            session.merge(UserPreferences(**u))
        session.commit()
        print(f"  ✅ {len(users)} users")

        # 2. Promos
        print("Seeding promo_calendar...")
        for p in PROMO_SCHEDULE:
            session.merge(PromoCalendar(**p))
        session.commit()
        print(f"  ✅ {len(PROMO_SCHEDULE)} promos")

        # 3. Sales (largest table — batch insert)
        print("Generating sales_kpi_weekly rows (this takes ~30s)...")
        sales_rows = generate_sales_rows()
        print(f"  Generated {len(sales_rows):,} rows — inserting in batches...")
        batch_size = 1000
        for i in range(0, len(sales_rows), batch_size):
            batch = sales_rows[i:i+batch_size]
            session.bulk_insert_mappings(SalesKPIWeekly, batch)
            if i % 10000 == 0 and i > 0:
                session.commit()
                print(f"  ... {i:,} / {len(sales_rows):,}")
        session.commit()
        print(f"  ✅ {len(sales_rows):,} sales rows")

        # 4. Scorecards
        print("Seeding retailer_account_scorecard...")
        scorecards = generate_scorecards()
        session.bulk_insert_mappings(RetailerAccountScorecard, scorecards)
        session.commit()
        print(f"  ✅ {len(scorecards)} scorecard rows")

        # 5. Alerts
        print("Seeding kpi_alert_log...")
        alerts = generate_alerts()
        for a in alerts:
            session.merge(KPIAlertLog(**a))
        session.commit()
        print(f"  ✅ {len(alerts)} alert records")

    # Write CSVs for inspection
    print("\nWriting CSVs to scripts/data/...")
    _write_csv(output_dir / "users.csv", users)
    _write_csv(output_dir / "promos.csv", PROMO_SCHEDULE)
    _write_csv(output_dir / "scorecards.csv", scorecards)
    _write_csv(output_dir / "alerts.csv", alerts)
    # Skip sales CSV — too large; use DB directly
    print(f"  (Sales rows too large for CSV — query testgpt_prototype.db directly)")

    print(f"""
✅ Synthetic data generation complete!
   DB:       {DB_URL}
   Weeks:    {len(WEEK_DATES)} ({WEEK_DATES[0]} → {WEEK_DATES[-1]})
   SKUs:     {len(SKUS)} across {len(BRANDS)} brands
   Retailers:{len(RETAILERS)}
   Sales rows: {len(sales_rows):,}
   Promos:   {len(PROMO_SCHEDULE)}
   Alerts:   {len(alerts)}
   Users:    {len(users)}

   [SYNTHETIC DATA — DEMO ONLY]
""")


def _write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Wrote {path.name} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
