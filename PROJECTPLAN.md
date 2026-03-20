# TestGPT — Project Plan
**Last Updated:** 2026-03-20  
**Status:** Prototype — Step 1 in progress  
**Repo:** btpope/RetailLLM

---

## What We're Building

TestGPT is an AI analyst agent embedded in **Engine**, DecisionFrame AI's CPG retail analytics platform. It replaces static dashboards with a conversational analyst that can answer any business question, surface issues proactively, and route them to the right person — all grounded in real data with full human-in-the-loop control.

**Primary model:** Anthropic Claude (claude-sonnet-4-6)  
**Secondary model:** Gemini (image generation for infographics — P2, deferred)  
**Language:** Python (prototype); .NET/C# for production Engine integration  
**Data layer:** SQLite (prototype) → Databricks Delta Lake (production)

---

## Key Decisions Made

### Architecture
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary AI model | Anthropic Claude (claude-sonnet-4-6) | Best-in-class reasoning, tool use, and narrative quality for CPG analytics |
| Language | Python for prototype | Faster iteration; richer AI tooling ecosystem for prototyping |
| Language (production) | Port to C#/.NET | Engine team is .NET-native; Anthropic.SDK on NuGet supports tool use |
| API framework | FastAPI | Simple, fast, OpenAPI docs auto-generated |
| Database (prototype) | SQLite via SQLAlchemy | Zero-setup, ORM is DB-agnostic; swap DB_URL for production |
| Database (production) | Databricks Delta Lake | Engine's existing data infrastructure; per-customer workspace isolation |
| AI inference (production) | Databricks AI Gateway | Keeps data inside the Databricks perimeter; single vendor; governed/logged |
| Model-switching | Config-only (ANALYST_MODEL + ANALYST_PROVIDER) | Agent graph is model-agnostic; switching Claude ↔ GPT ↔ Gemini = 1 config change |
| Data exposure | No direct Anthropic calls in production | Real retailer POS/trade data is governed by supplier agreements; must stay in Databricks perimeter |
| Infographic generation | Deferred to P2 | Requires Gemini API access approval; Step 3 only |
| Fine-tuning (Engine-7B) | Explicitly deferred | Validate Claude base model performance before custom training (Req #23) |

### Data Strategy
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pre-calculated metrics | Yes — `kpi_snapshot` materialized view | Faster responses, consistent metric definitions, auditable formulas |
| Metric definitions | KPI Registry table (metadata) | Single source of truth for CPG formulas, thresholds, units |
| Data grain | Weekly (CPG industry standard) | Sub-week data not in scope for v1 |
| Retailers in prototype | 8 top US retailers | Walmart, Target, Kroger, Costco, Amazon, CVS, Walgreens, Albertsons |
| Brands in prototype | 3 brands, ~30 SKUs | Realistic variety across snacks/beverages/personal care |
| Synthetic data range | Jan 2023 — Feb 2025 | 2+ years enables YoY comparisons; covers seasonal patterns |

### Safety & Governance
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Read-only enforcement | Hard block in execute_sql | `_assert_readonly()` raises before any mutation reaches DB |
| HITL gates | Mandatory for all outbound actions | No email, assignment, or publish without explicit user approval |
| Confidence scoring | Required on every recommendation | High/Medium/Low with rationale; never present a recommendation without it |
| Synthetic data labeling | `[SYNTHETIC DATA — DEMO ONLY]` on all outputs | Prototype mode flag; never mix synthetic and live data |

### Domain Expertise Layers
| Layer | Approach | Status |
|-------|----------|--------|
| 1. System prompt | CPG vocabulary, HITL rules, chart selection | ✅ Done |
| 2. KPI Registry | Metric definitions + thresholds + formulas | 📋 Planned |
| 3. Retailer knowledge | walmart.md, kroger.md, supply_chain.md | 📋 Planned |
| 4. RAG vector store | Searchable domain depth for complex queries | P2 |
| 5. Feedback loop | HITL edits → prompt improvements | Post-prototype |

---

## Requirements Summary

### P1 — Must Have (Prototype)
| # | Name | Step |
|---|------|------|
| 1 | "How Is My Business?" Default Summary | Step 1 |
| 2 | General Business Q&A | Step 1 |
| 3 | Agent-Selected Visualization on Request | Step 1 |
| 4 | Narrative KPI Cards v1 | Step 1 |
| 10 | Engine Analyst Agent — SQL + KPI Tool Use | Step 1 |
| 11 | Safety Layer — Read-Only, No Source Mutation | Step 1 |
| 5 | Issue Flagging + Disposition Workflow | Step 2 |
| 6 | Per-User Business Priority Configuration | Step 2 |
| 7 | Reactive Insight Agents (Threshold Monitoring) | Step 2 |
| 9 | Human-in-the-Loop (HITL) Approval Gates | Step 2 |

### P2 — Should Have (Post-Prototype)
`#8` Native Infographic Generation (Gemini) · `#12` Intent Router/Orchestrator · `#13` Multi-Chart Dashboard · `#14` Narrative Cards v2 · `#15` Deep Research Mode · `#16` Long-Term Memory · `#17` Scheduled Monday Reports · `#21` Retailer Benchmarking · `#22` Retailer Account View (JBP)

### P3 — Deferred
`#18` Email/Attachment Intelligence · `#19` Autonomous Agent Swarm · `#20` Self-Healing Pipelines · `#23` Engine-7B Fine-Tuning

---

## Implementation Steps

### ✅ Step 0 — Scaffold (Complete)
- Full project structure created
- All interfaces and stubs written
- System prompt finalized
- Schema defined (5 tables)
- Query library stubbed (5 patterns)
- All 8 tools defined with schemas
- FastAPI endpoints stubbed
- Synthetic data generator written (Jan 2023 – Feb 2025)

### 🔧 Step 1 — Core Analytics Engine (In Progress)
**Goal:** Ask a question, get a grounded narrative + chart back  
**Requirements:** #1, #2, #3, #4, #10, #11

Implementation tasks:
- [ ] Seed synthetic data into SQLite DB
- [ ] Implement `execute_sql` query routing (all 5 patterns)
- [ ] Implement `get_kpi_card` metric aggregation (map metric name → column → aggregate)
- [ ] Implement `generate_vega_chart` fully (all 6 chart types)
- [ ] Implement `kpi_summary` handler in the agent
- [ ] Wire TestGPTAgent end-to-end: receive query → tools → narrative
- [ ] Build `kpi_snapshot` materialized view query
- [ ] Add KPI Registry metadata
- [ ] End-to-end test: POST /chat → narrative + Vega spec returned
- [ ] Add Walmart and supply chain prompt fragments

### 📋 Step 2 — Reactive Agents + Issue Workflow
**Goal:** System watches metrics and routes issues with approval  
**Requirements:** #5, #6, #7, #9

- [ ] Reactive agent: poll kpi_alert_log for threshold breaches
- [ ] Issue flagging: `flag_issue` persists to DB, returns disposition options
- [ ] `send_for_approval` halt logic in agent loop
- [ ] Per-user priority loading shapes default summary (Req #6)
- [ ] POST /approve endpoint fully implemented
- [ ] Retailer prompt fragments: walmart.md, kroger.md, kroger.md

### 📋 Step 3 — Infographic Generation (P2, conditional)
**Requirements:** #8  
- [ ] Confirm Gemini API access
- [ ] Implement `generate_infographic_image` via Gemini
- [ ] HITL gate before any infographic is shared

---

## File Structure

```
RetailLLM/
├── api/
│   └── main.py                    ← FastAPI: POST /chat, POST /approve, GET /issues
├── agents/
│   └── testgpt_agent.py         ← Main tool loop orchestrator + HITL
├── tools/
│   ├── execute_sql.py             ← SQL tool (read-only enforced)
│   ├── generate_vega_chart.py     ← Vega-Lite chart builder
│   ├── kpi_tools.py               ← get_kpi_card, get_promo_calendar, get_retailer_account, search_memory
│   └── workflow_tools.py          ← flag_issue, send_for_approval, generate_infographic_image
├── models/
│   ├── schema.py                  ← SQLAlchemy ORM (5 tables)
│   └── queries.py                 ← Pre-built read-only query library
├── prompts/
│   ├── testgpt_system_prompt.md ← Full Claude system prompt
│   └── retailers/                 ← (planned) walmart.md, kroger.md, supply_chain.md
├── scripts/
│   └── generate_synthetic_data.py ← Seeds SQLite with Jan 2023–Feb 2025 data
├── config/
│   └── settings.py                ← Model/provider/DB config
├── PROJECTPLAN.md                 ← This file
├── OPEN_QUESTIONS.md              ← 20 open questions for product input
└── README.md                      ← Quickstart
```

---

## Open Questions (Resolved)

| Question | Decision |
|----------|----------|
| Which cloud? | Azure (existing Engine infrastructure) |
| Which database (prototype)? | SQLite — zero setup, ORM-agnostic |
| Which database (production)? | Databricks Delta Lake |
| Which AI provider? | Anthropic Claude (direct API for prototype; Databricks AI Gateway for production) |
| Python or .NET? | Python for prototype; port to C#/.NET for Engine integration |
| Infographic via Gemini? | Deferred to P2 — needs API access confirmation |
| Fine-tune Engine-7B? | Deferred — validate base Claude first |
| Azure in the middle? | Yes for production (Databricks AI Gateway keeps data in perimeter) |
| Pre-calculated metrics? | Yes — `kpi_snapshot` materialized view + KPI Registry table |

## Open Questions (Still Pending)
See `OPEN_QUESTIONS.md` for the full list. Top priority:
- **I1** Which cloud for production infrastructure?
- **A1/A3** Auth model and multi-tenancy approach?
- **D1** How does TestGPT connect to live Engine warehouse?
- **P1** Frontend: standalone SPA or embedded in Glass?
