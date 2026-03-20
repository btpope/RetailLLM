# TestGPT — Walmart Semantic Knowledge Reference
**Last Updated:** 2026-03-20  
**Purpose:** Documents all Walmart-specific and CPG-specific knowledge baked into TestGPT across Phase 1, Phase 2, and Phase 3. This is the authoritative reference for the semantic layer.

---

## Phase 1 — Walmart + CPG Expert Knowledge (System Prompt)

### Walmart Reporting & Data
| Knowledge | Detail |
|-----------|--------|
| **Reporting week** | Saturday → Friday (never assume calendar months align to Walmart periods) |
| **Data grain** | Weekly only; sub-week analysis not in scope for v1 |
| **Retail Link** | Walmart's supplier portal; Engine ingests this format |
| **WMT Item Number** | 9-digit number; each item/store/week = one row |
| **Fineline** | Walmart's sub-category classification; affects modular placement and share of shelf |

### Buying & Merchandising Cycle
| Knowledge | Detail |
|-----------|--------|
| **Buyer** | Primary commercial contact; owns category P&L; decides which items get shelf space |
| **DMM** | Divisional Merchandise Manager; buyer's boss; involved in JBP reviews and major distribution decisions |
| **Line Review** | Semi-annual (typically Feb + Aug); buyer decides which items stay, get added, or get cut |
| **Modular reset** | Planogram changes after line review; executes Feb and Aug |
| **New item ramp** | Must reach ≥50% of comparable item velocity by week 13 or at risk in next line review |
| **JBP** | Joint Business Plan; annual volume/promo/investment commitment; tracked quarterly; shortfalling = buyer conversation |
| **Category Captain** | Brand with highest category share often influences planogram recommendations; competitors benefit from category growth |

### Supply Chain Knowledge
| Knowledge | Detail |
|-----------|--------|
| **OTIF** | On-Time In-Full = (on-time delivery %) × (in-full delivery %); Walmart's primary supplier scorecard |
| **OTIF target** | ≥98.0% — below triggers monitoring |
| **OTIF penalty** | Below 95% → Walmart charges **3% of cost-of-goods** as fine on affected POs |
| **DC Fill Rate** | Supplier ships to Walmart DC; distinct from store-level OOS |
| **Root cause distinction** | DC fill rate low → supply chain problem (supplier's fault). DC fill rate high but store OOS high → phantom inventory / replenishment problem (Walmart system) |
| **Phantom Inventory** | System shows stock on hand but shelf is empty; common cause of high OOS despite adequate supply |
| **Automatic replenishment** | Walmart uses system-generated POs; supplier fills POs; execution quality determines OTIF |
| **VNPK** | Vendor Pack — quantity supplier ships per case; must match Walmart planogram spec |
| **WHPK** | Warehouse Pack — how Walmart's DC repackages for stores; mismatches cause fill rate issues |
| **SQEP** | Supplier Quality Excellence Program; compliance scoring for labeling, packaging, case marking; non-compliance = chargebacks |

### Walmart Financial + Commercial
| Knowledge | Detail |
|-----------|--------|
| **EDLC** | Everyday Low Cost; Walmart expects suppliers to pass savings through to EDLP pricing |
| **Rollback** | Walmart-funded temporary price reduction; drives stronger lift than TPR (prominently merchandised) |
| **TPR** | Temporary Price Reduction — trade-funded by supplier |
| **Walmart Connect** | Walmart's retail media network; Sponsored Search + Display; increasingly important for velocity especially new items |

---

## Phase 1 — CPG Metric Benchmarks

### Velocity (U/S/W — Units Per Store Per Week)
Primary metric for all Walmart decisions: distribution, shelf space, promotional investment.

| Brand | Category | WEAK | AVERAGE | STRONG | ELITE |
|-------|----------|------|---------|--------|-------|
| **Apex** | Salty Snacks | < 3.0 | 3.0–6.0 | 6.0–10.0 | > 10.0 |
| **Bolt** | Energy Drinks | < 5.0 | 5.0–10.0 | 10.0–16.0 | > 16.0 |
| **Silke** | Hair Care | < 1.5 | 1.5–3.0 | 3.0–5.0 | > 5.0 |

**Delistment rule:** New item must reach ≥50% of category average by week 13.  
**Trend rule:** Velocity declining 3+ consecutive periods = at risk in next line review.

### OOS Rate (Out-of-Stock %)
| Rate | Status | Buyer Implication |
|------|--------|-------------------|
| < 3% | Excellent | No action needed |
| 3–5% | Normal | Monitor; flag if trending up |
| 5–8% | **Elevated** | Buyer visibility risk; investigate root cause |
| 8–12% | **Critical** | Buyer conversation likely; replenishment review |
| > 12% | **Severe** | Walmart may reduce PO frequency or delist |

**Always distinguish:** DC OOS (supplier problem) vs. store OOS (Walmart phantom inventory/replenishment problem).

### Promo ROI (Incremental Contribution Margin / Trade Spend)
| ROI | Assessment | Action |
|-----|------------|--------|
| < 0.8x | Losing money | Stop or restructure; reduce depth or frequency |
| 0.8–1.0x | Below breakeven | Marginal; justify only with strategic rationale (trial, JBP) |
| **1.0x** | **Breakeven** | Every dollar below this = losing money on the promotion |
| 1.0–1.5x | Acceptable | Optimize depth or timing |
| 1.5–2.5x | Good | Continue; test scaling |
| > 2.5x | Excellent | Prioritize; invest more trade |

### Promo Lift (vs. Baseline Velocity)
| Lift | Status |
|------|--------|
| < 15% | Below expected; investigate depth, display execution, competitive overlap |
| 15–40% | Average response |
| 40–70% | Strong; verify supply chain readiness |
| > 70% | Exceptional/event-level; check cannibalization and OOS in promo weeks |

**By category:** Snacks avg 30–50%; Energy drinks avg 40–70%; Hair care avg 20–35%

### OTIF
| Rate | Status |
|------|--------|
| ≥ 98.0% | Compliant |
| 95–97.9% | Fine risk / monitoring |
| < 95% | **3% COGS fine** per affected PO |

### DC Fill Rate
| Rate | Status |
|------|--------|
| ≥ 97% | Good |
| 93–97% | Monitor |
| < 93% | Critical — root cause of store OOS |

### ACV Distribution
| Rate | Status |
|------|--------|
| ≥ 85% | Full national distribution |
| 70–85% | Strong |
| 50–70% | Building / regional |
| < 50% | Limited distribution |

**Note:** 90% ACV ≠ 90% of Walmart stores. ACV weights by store sales volume — a brand in Walmart's top-volume stores can have 90% ACV in 60% of locations.

### YoY Revenue Growth
| Growth | Status |
|--------|--------|
| < 0% | Declining — losing share (category avg is 3–5%) |
| 0–8% | Modest / tracking category |
| > 8% | Above-market — gaining share (favorable in line review) |
| > 20% | Elite |

---

## Phase 1 — Interpretation Rules (Baked into Every Response)

The agent applies these automatically whenever it detects a signal in the data:

| Signal | What the Agent Says |
|--------|---------------------|
| OOS > 8% | "Above the threshold where Walmart begins reducing replenishment orders. Root cause investigation and proactive buyer communication recommended." |
| OOS spike after promo | "Demand forecast miss — most common root cause when OOS spikes immediately post-promo." |
| Promo ROI < 1.0x | "This promotion lost money. You spent $[X] to generate $[Y] in incremental contribution — below 1.0x breakeven." |
| Velocity declining 3+ periods | "At this trajectory, this item is at risk in the next line review. Corrective action plan should be in place before week [N+4]." |
| Velocity < category weak threshold | "Delistment risk territory. Walmart buyers expect new items to reach [benchmark] U/S/W by week 13." |
| YoY revenue up but velocity flat | "Revenue growth is price-driven, not volume-driven. Watch for elasticity — if velocity declines in 4–8 weeks, the price increase is not holding." |
| ACV distribution dropping | "Distribution is contracting. Check if lost stores are high- or low-ACV — losing high-ACV stores has disproportionate revenue impact." |
| Promo lift < 15% | "Below expected lift range. Check promo depth, feature/display execution, and competitive overlap." |
| Promo lift > 80% | "Exceptional response. Check cannibalization across brand portfolio and verify supply chain met demand (check OOS in promo weeks)." |

### Persona Adaptation by Role
The agent adapts response depth to the user's role:
- **Executive / VP**: 2–3 bullets, dollar impact front and center, no methodology
- **Brand Manager / Account Manager**: mid-detail — trend context, promo drivers, recommended action
- **Category Analyst**: full narrative with metric definitions, data confidence, root cause hypothesis

### Confidence Labeling
Every response must state confidence explicitly:
- `[HIGH CONFIDENCE]` — data is clear and complete
- `[MEDIUM — limited data]` — partial data or short window
- `[FLAG FOR REVIEW]` — unusual signal; may need investigation

---

## Phase 2 — Benchmark Intelligence Tools

### `get_benchmark` Tool
Compares any metric value to the `benchmark_reference` table. Returns:
- **Tier**: WEAK / AVERAGE / STRONG / ELITE
- **Gap to avg midpoint**: how far the value is from category average
- **Gap to strong**: how much improvement needed to reach STRONG tier
- **Walmart threshold status**: ABOVE/BELOW threshold with penalty language
- **Action recommended**: specific text for WEAK tier only

**Benchmark configs in `benchmark_reference` table:**

| Metric | Brand | Weak | Avg Range | Strong | Elite | Walmart Threshold |
|--------|-------|------|-----------|--------|-------|-------------------|
| velocity | Apex | < 3.0 | 3.0–6.0 | ≥ 6.0 | ≥ 10.0 | None |
| velocity | Bolt | < 5.0 | 5.0–10.0 | ≥ 10.0 | ≥ 16.0 | None |
| velocity | Silke | < 1.5 | 1.5–3.0 | ≥ 3.0 | ≥ 5.0 | None |
| oos_rate | All | > 8.0% | 3.0–5.0% | < 3.0% | < 1.5% | 5.0% (monitoring); 8.0% (replenishment risk); 12.0% (delistment) |
| promo_roi | All | < 1.0x | 1.0–1.8x | ≥ 1.8x | ≥ 2.5x | None |
| promo_lift | All | < 15% | 15–40% | ≥ 40% | ≥ 70% | None |
| otif | All | < 95.0% | 95–98.0% | ≥ 98.0% | ≥ 99.5% | 98.0% (fine at <95%) |
| dc_fill_rate | All | < 93.0% | 93–97.0% | ≥ 97.0% | ≥ 99.0% | 97.0% |
| acv | All | < 50.0% | 70–85.0% | ≥ 85.0% | ≥ 95.0% | None |
| yoy_growth | All | < 0.0% | 0–8.0% | ≥ 8.0% | ≥ 20.0% | None |

### `get_trend_analysis` Tool
Multi-period comparison across L4W, L13W, and L52W. Returns per entity:
- **Short-term trend** (L4W vs L13W): ACCELERATING ↑ / STABLE → / DECELERATING ↓ (threshold: ±5%)
- **Long-term trend** (L13W vs L52W): IMPROVING ↑ / FLAT → / DECLINING ↓ (threshold: ±3%)
- **Delta %** for both windows
- **Line review risk**: HIGH / MEDIUM / LOW (velocity metric only)
  - HIGH: velocity below weak threshold
  - MEDIUM: declining trend in both short and long window (>10% decline each)
  - LOW: everything else
- **OOS escalation**: CRITICAL (>8%) / ELEVATED (>5%) / None

### `supply_chain_weekly` Table
336 rows (112 weeks × 3 brands). Fields:
- `otif_rate_pct` — On-Time In-Full %
- `dc_fill_rate_pct` — DC Fill Rate %
- `case_fill_rate_pct` — Supplier Case Fill %
- `on_time_delivery_pct` — On-Time component of OTIF
- `in_full_delivery_pct` — In-Full component of OTIF
- `chargebacks_dollars` — OTIF fines (non-zero only when OTIF < 95%)
- `compliance_score` — SQEP compliance 0–100

---

## Phase 3 — Multi-Turn Memory + Conversation Intelligence

### Context Resolution Rules (System Prompt)
The agent resolves natural follow-up references without the user restating context:

| User Says | Agent Does |
|-----------|------------|
| "What about L13W?" | Applies same metric/brand/SKU to L13W period |
| "Show me a chart of that" | Charts the data from the prior answer |
| "Which one is worst?" | Ranks entities from the prior answer |
| "Drill into Bolt" | Re-runs the same analysis scoped to Bolt only |
| "Compare that to last year" | Gets L4W current + same window prior year; calls chart with `color_field="year"` |

### Session Memory Architecture
- **First turn**: pre-fetch brief injected (KPI summary + open alerts); `_brief_injected = True`; brief stays as first 2 messages for life of session
- **Subsequent turns**: user message appended; tool loop runs with full history
- **History trimming**: `_trim_history()` — keeps brief+ack prefix (2 messages) + last 12 exchange pairs; trims to 8 pairs when exceeded
- **Session persistence**: `_agent_sessions` dict keyed by `session_id` or `user_id`; DB session refreshed per request

### Pre-Fetch Brief Content
On first turn, the agent is given (before the user's actual question):
1. User name, role, brand scope, retailer, period
2. KPI summary: velocity, revenue, OOS, ACV, promo ROI with delta% and trend
3. Open alerts (top 3) with severity and description
4. Instruction: "You already have this data. Answer directly. Only call tools for data NOT shown above."

---

## Chart Selection Rules

| Question Type | Chart Type | Notes |
|--------------|------------|-------|
| Trends over time | `line` | `color_field` for multi-series (YoY, multi-brand) |
| Top N by metric (> 5 items) | `horizontal_bar` | SKU names on Y-axis; height = max(300, n × 36px) |
| Category comparison (≤ 5) | `bar` | Vertical |
| Distribution/composition (≤ 6) | `pie` | More than 6 = use stacked_bar |
| Correlation | `scatter` | |

**Auto-horizontal trigger**: avg label length > 12 chars OR > 6 items → promote to horizontal  
**X-axis type**: auto-detects temporal (YYYY-MM-DD pattern) vs. ordinal (period labels, years)  
**Field type**: auto-detects categorical vs. quantitative from data values (ignores Claude's x/y parameter order)  
**Dark theme**: applied at render time via vega-embed config (background transparent, axis/legend colors overridden)

---

## Tool Priority (Enforced in System Prompt)

```
1. get_metric           → ALWAYS FIRST for standard KPI questions
2. get_benchmark        → ALWAYS call after get_metric to contextualize numbers
3. get_trend_analysis   → for any trajectory / momentum / "is this getting better?" question
4. generate_vega_chart  → ALWAYS call when chart requested; NEVER substitute markdown table
5. get_promo_calendar   → promo schedule, timing, depth, type
6. get_retailer_account → JBP scorecard, quarterly commitments
7. get_business_summary → fallback if get_metric insufficient
8. get_kpi_card         → fallback single-metric
9. execute_sql          → LAST RESORT for custom questions only
```

---

## Known Constraints & Limitations

| Constraint | Detail |
|-----------|--------|
| Walmart-only | Multi-retailer comparisons removed; all users `retailer_scope: Walmart` |
| Weekly grain | Sub-week analysis not in scope for v1 |
| Synthetic data | All numbers simulated; `[SYNTHETIC DATA — DEMO ONLY]` on all outputs |
| HITL required | No email, issue assignment, or publish without explicit user approval |
| In-memory sessions | Lost on container restart; Redis needed for production |
| `flag_issue` | In-memory only; does not persist to DB (Step 4 work) |
| `send_for_approval` | Logs only; does not execute the action (Step 4 work) |
| Sub-week data | Not available; weekly grain only |
| Syndicated data | Nielsen/Circana benchmarks not in scope for v1 (Req #21, P2) |
