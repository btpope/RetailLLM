# TestGPT — Project Plan
**Last Updated:** 2026-03-20  
**Status:** Prototype — Steps 1–3 complete; Phase 1–3 semantic layer complete  
**Repo:** btpope/RetailLLM

---

## What We're Building

TestGPT is an AI analyst agent embedded in **Engine**, DecisionFrame AI's CPG retail analytics platform. It replaces static dashboards with a conversational analyst that answers any business question, surfaces issues proactively, and routes them to the right person — all grounded in real data with full human-in-the-loop control.

**Primary model:** Anthropic Claude (claude-sonnet-4-6)  
**Secondary model:** Gemini (image generation for infographics — P2, deferred)  
**Language:** Python (prototype); .NET/C# for production Engine integration  
**Data layer:** SQLite (prototype) → Databricks Delta Lake (production)

---

## Key Decisions Made

### Architecture
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary AI model | Anthropic Claude (claude-sonnet-4-6) | Best-in-class reasoning, tool use, and CPG narrative quality |
| Language (prototype) | Python + FastAPI | Faster iteration; richer AI tooling ecosystem |
| Language (production) | Port to C#/.NET | Engine team is .NET-native; Anthropic.SDK on NuGet |
| Database (prototype) | SQLite via SQLAlchemy | Zero-setup; ORM-agnostic (swap DB_URL for production) |
| Database (production) | Databricks Delta Lake | Engine's existing data infrastructure; per-customer workspace isolation |
| AI inference (production) | Databricks AI Gateway → Azure AI Foundry | Data stays in Databricks perimeter; governed + logged |
| No direct Anthropic in production | Yes | Real retailer POS/trade data governed by supplier agreements |
| Multi-turn memory (prototype) | In-process Python dict | `_agent_sessions`; Redis for production |
| Feature branches | Yes (from Phase 4+) | PR-based diff review in GitHub before merging to master |

### Data Strategy
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Metric store (pre-computed) | Yes — `metric_store` table | Faster responses, zero SQL hallucination, consistent definitions |
| Benchmark reference | Yes — `benchmark_reference` table | CPG category benchmarks + Walmart-specific thresholds baked in |
| Supply chain data | Yes — `supply_chain_weekly` table | OTIF, DC fill rate, chargebacks, SQEP compliance per brand/week |
| Data grain | Weekly (CPG standard) | Sub-week not in scope for v1 |
| Retailer scope | **Walmart only** | CPG customer team calling on one retailer; multi-retailer removed |
| Brands | Apex (snacks), Bolt (energy), Silke (hair care) | Realistic variety across CPG categories |
| Date range | Jan 2023 – Feb 2025 (112 weeks) | 2+ years enables YoY comparisons + seasonal patterns |
| Data seed | Deterministic (mulberry32, seed=42) | Reproducible demo data; `npm run seed` always gives same result |

### Safety & Governance
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Read-only enforcement | Hard block in `execute_sql` | `_assert_readonly()` raises before any mutation reaches DB |
| HITL gates | Mandatory for all outbound actions | No email/assignment/publish without explicit user approval |
| Approval panel UI | Yes — renders preview with Approve/Cancel | `pending_approval` in response triggers panel in frontend |
| Synthetic data labeling | `[SYNTHETIC DATA — DEMO ONLY]` on all outputs | Prototype mode flag; never mix synthetic and live data |

### Semantic Layer Decisions
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Walmart week | Saturday–Friday | Hard-coded in system prompt; never assume calendar months |
| OTIF threshold | 98% target; 3% COGS penalty below 95% | Standard Walmart supplier requirement |
| Velocity benchmarks | Brand-specific: Apex 3/6/10+ Bolt 5/10/16+ Silke 1.5/3/5+ | Category-calibrated vs generic thresholds |
| Benchmark tiers | WEAK/AVERAGE/STRONG/ELITE | Simple, actionable, consistent across all metrics |
| Trend signals | ACCELERATING/DECELERATING/DECLINING via L4W vs L13W vs L52W | Multi-window comparison catches both short and structural trends |
| Line review risk | HIGH/MEDIUM/LOW | Tied to Walmart's Feb+Aug reset cycle; surfaced in every trend response |
| Pre-fetch brief | Inject once (first turn only) | Eliminates 2 API round-trips; `_brief_injected` flag tracks injection |
| History trimming | Last 12 exchange pairs; preserve brief+ack prefix | Token-safe for long sessions; brief preserved for context |

---

## Implementation Progress

### ✅ Step 0 — Scaffold (Complete)
- Full project structure, all interfaces and stubs, system prompt, schema, query library, 8 tools, FastAPI endpoints, synthetic data generator

### ✅ Step 1 — Core Analytics Engine (Complete)
- Synthetic data seeded: 16,800 sales rows, 60 promos, 120 alerts, 27 scorecards
- `execute_sql` routing — all 5 patterns + raw SQL (read-only enforced)
- `get_kpi_card` metric aggregation with delta% and trend
- `generate_vega_chart` — 5 chart types; auto-horizontal for >6 items; field type auto-detection
- `get_business_summary` — all priority KPIs ranked by change
- End-to-end: POST /chat → Claude tool loop → narrative + Vega specs
- Chat UI: password login, user selector, sidebar with suggested starters, vega-embed rendering

### ✅ Step 2 — Speed + Data Layer Optimization (Complete)
- Pre-fetch brief: KPI summary + open alerts injected before first Claude call
- `metric_store` table (136 rows): pre-computed L4W/L13W/L52W/YTD × total/brand/SKU
- `get_metric` tool: single-row lookups with benchmark context annotations
- Walmart-only dataset rebuild (removed Target, Kroger, Costco, etc.)
- Bar chart auto-horizontal + dynamic height
- Chart field type auto-detection (categorical vs numeric, ignores Claude's x/y order)
- 10–20s response times (down from ~23s)

### ✅ Phase 1 — Walmart + CPG Semantic Layer (Complete)
System prompt rewrite with expert-level Walmart knowledge:
- Full buying cycle (buyer/DMM/line review/modular reset/JBP)
- Supply chain mechanics (OTIF, DC fill, phantom inventory, VNPK/WHPK, SQEP)
- Velocity benchmarks by brand/category
- OOS thresholds with buyer implication at each level
- 8 interpretation rules: every KPI signal → specific "so what + what to do"
- Persona adapts depth by role: executive / brand manager / analyst

### ✅ Phase 2 — Benchmark Intelligence + Trend Tools (Complete)
- `benchmark_reference` table: 9 metric/brand configs with 4 tiers + Walmart thresholds
- `supply_chain_weekly` table: 336 rows (112 weeks × 3 brands); OTIF, DC fill, chargebacks
- `get_benchmark` tool: tier comparison, gap to avg/strong, Walmart threshold status, action text
- `get_trend_analysis` tool: L4W/L13W/L52W with ACCELERATING/DECLINING/FLAT signals + line review risk
- Tool priority: get_metric → get_benchmark → get_trend_analysis → chart → SQL

### ✅ Phase 3 — Multi-Turn Memory + Proactive Intelligence (Complete)
- Multi-turn conversation history (server-side `_agent_sessions` dict)
- Pre-fetch brief injected once on first turn (`_brief_injected` flag)
- History trimming: `_trim_history()` keeps last 12 pairs; preserves brief prefix
- Stale DB session bug fixed: `agent.session = db` on every request
- Open Alerts sidebar panel: loads live from `/issues`, color-coded, click-to-ask
- Approval panel UI: renders when `pending_approval` present; Approve/Cancel buttons
- YoY line chart: auto-detects temporal vs ordinal x-axis; multi-series with color_field
- Multi-turn context rules in system prompt: "what about L13W?", "drill into Bolt", etc.
- User avatar shows first+last initials (MC, SJ, RT — not static "B")
- TG monogram (white T, blue G) for bot avatar
- Conversation history sidebar (localStorage, max 30, restore on click)

### 📋 Step 4 — Reactive Agents + Issue Workflow (Next)
- Reactive agent: poll `kpi_alert_log` for threshold breaches
- `flag_issue` — persist to DB (currently in-memory only)
- `send_for_approval` — full execution on approval (currently stubs + logs)
- Per-user priority loading shapes default summary (Req #6)
- POST /approve endpoint fully implemented
- Retailer prompt fragments: walmart.md, supply_chain.md

### 📋 Step 5 — Infographic Generation (P2, conditional)
- Confirm Gemini API access
- `generate_infographic_image` via Gemini
- HITL gate before any infographic is shared

---

## Resolved Design Questions

| Question | Decision |
|----------|----------|
| Which cloud? | Azure (Engine's existing infrastructure) |
| Database (prototype)? | SQLite — zero setup, ORM-agnostic |
| Database (production)? | Databricks Delta Lake |
| AI provider? | Anthropic Claude (direct API for prototype; Databricks AI Gateway for production) |
| Python or .NET? | Python for prototype; port to C#/.NET for Engine integration |
| Infographic (Gemini)? | Deferred to P2 — needs API access confirmation |
| Fine-tune Engine-7B? | Deferred — validate base Claude first |
| Pre-calculated metrics? | Yes — `metric_store` table seeded at build time |
| Multi-retailer vs Walmart-only? | Walmart-only for prototype — CPG customer team at one retailer |
| Feature branches? | Yes, from Phase 4 onwards — PR review in GitHub |

---

## File Structure

```
RetailLLM/
├── api/
│   ├── main.py              ← FastAPI: /chat, /issues, /sessions, /approve, /summary, /users
│   └── auth.py              ← API key middleware
├── agents/
│   └── testgpt_agent.py     ← Tool loop + multi-turn memory + HITL + pre-fetch brief
├── tools/
│   ├── metric_store.py      ← get_metric: pre-computed KPI lookups (ALWAYS FIRST)
│   ├── benchmark.py         ← get_benchmark + get_trend_analysis (Phase 2)
│   ├── execute_sql.py       ← SQL tool (read-only enforced; last resort)
│   ├── generate_vega_chart.py ← Vega-Lite chart builder (auto-type detection)
│   ├── kpi_tools.py         ← get_kpi_card, get_business_summary, get_promo_calendar,
│   │                           get_retailer_account, search_memory
│   └── workflow_tools.py    ← flag_issue, send_for_approval, generate_infographic_image (stub)
├── models/
│   ├── schema.py            ← SQLAlchemy ORM (8 tables)
│   └── queries.py           ← Pre-built read-only query library (anchor-date aware)
├── prompts/
│   └── testgpt_system_prompt.md ← Full system prompt with Phase 1/2/3 semantic layers
├── scripts/
│   └── generate_synthetic_data.js ← Seeds all 8 tables; Walmart-only; seed=42 deterministic
├── config/
│   └── settings.py          ← Model/provider/DB/safety config
├── public/
│   └── index.html           ← SPA: login, user selector, chat, sidebar, alerts panel
├── README.md
├── PROJECTPLAN.md           ← This file
└── OPEN_QUESTIONS.md        ← Resolved + pending questions
```
