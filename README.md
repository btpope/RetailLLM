# TestGPT — DecisionFrame AI (Prototype)

AI analyst agent for CPG brands selling at Walmart. Ask questions in plain English — get back KPI narratives with expert Walmart context, trend analysis, benchmark comparisons, supply chain health, and Vega-Lite charts.

> ⚠️ **Prototype running on synthetic demo data only. All numbers are simulated. Label: `[SYNTHETIC DATA — DEMO ONLY]`**

---

## Live Demo

**URL**: `https://testgpt.srv1445355.hstgr.cloud`
**Password**: `testgpt2026`

Pick a user (e.g. Sarah Johnson = Apex Brand Manager), then ask:
- "How is my business?"
- "Is our OOS rate good or bad?"
- "What's the velocity trend for Bolt?"
- "Show me top SKUs by OOS rate as a chart"
- "What's our OTIF performance?"
- "Which SKUs are at risk in the next line review?"

---

## Architecture

```
Browser (Chat UI — public/index.html)
    ↓ POST /chat   (session_id maintained for multi-turn memory)
FastAPI (api/main.py)
    ↓ refreshes DB session per request; agent cached in _agent_sessions
TestGPTAgent (agents/testgpt_agent.py)
    ↓ one-time pre-fetch brief on first turn; tool loop for all subsequent turns
    │
    ├── get_metric           → pre-computed metric store (ALWAYS FIRST)
    ├── get_benchmark        → benchmark tier lookup + Walmart threshold (CALL AFTER get_metric)
    ├── get_trend_analysis   → L4W/L13W/L52W trend signals + line review risk
    ├── generate_vega_chart  → Vega-Lite spec (ALWAYS call for chart requests)
    ├── get_promo_calendar   → promo schedule, lift, ROI
    ├── get_retailer_account → JBP scorecard
    ├── get_kpi_card         → single-metric current vs. prior (fallback)
    ├── get_business_summary → full dashboard (fallback)
    ├── execute_sql          → ad-hoc custom queries (LAST RESORT)
    ├── search_memory        → user preferences from DB
    ├── flag_issue           → surface KPI anomaly for review
    └── send_for_approval    → HITL gate before any outbound action
    ↓
Narrative + Vega-Lite charts + optional approval panel
    ↓
Browser renders via vega-embed CDN; conversation history stored in localStorage
```

**Prototype stack**: Python 3.11 · FastAPI · SQLite · Anthropic claude-sonnet-4-6 · Vega-Lite  
**Production stack** (planned): C#/.NET · Databricks Delta Lake · Azure AI Foundry (OpenAI-compatible) · Engine integration

---

## Semantic Intelligence Layers

### Phase 1 — Walmart + CPG Expert Knowledge (system prompt)
The agent has deep Walmart operational knowledge baked in:
- **Reporting cadence**: Saturday–Friday week, Retail Link, WMT item numbers, Fineline
- **Buying cycle**: Buyer/DMM/line review/modular reset (Feb+Aug resets); 13-week new item ramp window
- **JBP tracking**: volume/promo/investment commitments; quarterly performance
- **OTIF**: 98% target; **3% cost-of-goods penalty below 95%** — stated explicitly in responses
- **DC fill rate vs. store OOS**: different root causes, different fixes
- **Phantom inventory**, VNPK/WHPK, SQEP compliance, replenishment mechanics
- **Velocity benchmarks by brand**: Apex snacks (3/6/10+ U/S/W), Bolt energy (5/10/16+), Silke hair care (1.5/3/5+)
- **OOS thresholds**: <3% excellent → 3-5% normal → 5-8% elevated → 8-12% critical → >12% delistment risk
- **8 interpretation rules**: every signal (OOS spike, velocity decline, promo ROI <1.0x) produces specific "so what + action" language

### Phase 2 — Benchmark Intelligence + Trend Analysis (tools)
- **`get_benchmark`**: compares any value to category benchmarks; returns WEAK/AVERAGE/STRONG/ELITE tier, gap to avg, gap to strong, Walmart threshold status, and action recommendation
- **`get_trend_analysis`**: L4W/L13W/L52W side-by-side with ACCELERATING/DECELERATING/DECLINING signals, line review risk (HIGH/MEDIUM/LOW), and OOS escalation flag
- **`benchmark_reference` table**: 9 benchmark configs (velocity brand-specific, OOS, promo ROI, promo lift, OTIF, DC fill rate, ACV, YoY) with Walmart-specific thresholds
- **`supply_chain_weekly` table**: weekly OTIF, DC fill rate, case fill rate, chargebacks, SQEP compliance by brand (336 rows)

### Phase 3 — Multi-Turn Memory + Proactive Alerts
- **Multi-turn conversation**: session persists server-side; data brief injected once (first turn only); history trimmed to last 12 exchange pairs with brief+ack preserved
- **Context resolution**: agent resolves "what about L13W?", "drill into Bolt", "show me a chart of that" without restating context
- **Open Alerts panel**: sidebar shows live `kpi_alert_log` entries color-coded by severity; click to ask about any alert
- **Approval panel**: when `send_for_approval` fires, UI renders a preview with Approve/Cancel buttons

---

> 📖 **Full semantic layer reference**: See [`WALMART_SEMANTICS.md`](WALMART_SEMANTICS.md) for the complete documentation of all Walmart + CPG knowledge, benchmarks, thresholds, and interpretation rules baked into the system.

---

## Local Setup

**Prerequisites**: Python 3.11+, Node.js 20+ (for seeding)

```bash
git clone https://github.com/btpope/RetailLLM.git
cd RetailLLM

# Install Python deps
pip install -r requirements.txt

# Seed the SQLite DB
npm install
npm run seed

# Configure
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY

# Start
uvicorn api.main:app --reload --port 8000
```

Open `http://localhost:8000` — no password needed locally (TESTGPT_API_KEY empty = open in dev mode).

---

## API Reference

All endpoints require `?api_key=<key>` or `X-API-Key` header (except `/health`, `/`, `/docs`).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Chat UI |
| `/health` | GET | Health check — `{"status":"ok","prototype":true}` |
| `/chat` | POST | Main agent endpoint (multi-turn) |
| `/issues` | GET | Open KPI alerts for a user scope |
| `/summary/{user_id}` | GET | KPI cards (no Claude — data layer only) |
| `/sessions/{id}` | DELETE | Clear conversation history for a session |
| `/approve` | POST | HITL approval outcome (stub — logs only) |
| `/users` | GET | List test users |
| `/docs` | GET | Swagger UI |

**POST /chat**
```json
{
  "user_id": "USR-001",
  "message": "How is my business?",
  "session_id": null
}
```

Response:
```json
{
  "session_id": "USR-001",
  "narrative": "Sarah Johnson's Business Summary...",
  "charts": [ /* Vega-Lite spec objects */ ],
  "issues": [],
  "pending_approval": null,
  "has_approval_gate": false,
  "synthetic_data": true
}
```

---

## Database Schema

| Table | Rows | Description |
|-------|------|-------------|
| `sales_kpi_weekly` | 16,800 | Weekly sales by SKU × region, Jan 2023–Feb 2025 |
| `promo_calendar` | 60 | Promo events with lift, ROI, cannibalization, type |
| `retailer_account_scorecard` | 27 | Quarterly JBP scorecards |
| `kpi_alert_log` | 120 | Open KPI alerts (OOS breach, velocity decline, etc.) |
| `user_preferences` | 5 | Test users with role, scope, priority metrics |
| `metric_store` | 136 | Pre-computed KPIs: L4W/L13W/L52W/YTD × total/brand/SKU |
| `benchmark_reference` | 9 | Category benchmarks + Walmart thresholds by metric |
| `supply_chain_weekly` | 336 | Weekly OTIF, DC fill rate, chargebacks, compliance |

**Brands**: Apex (Salty Snacks), Bolt (Energy Drinks), Silke (Hair Care)  
**Retailer**: Walmart only (CPG customer team calling on one retailer)  
**Regions**: 5 (Southeast, Northeast, Midwest, Southwest, West)  
**SKUs**: 30 (10 per brand)  
**Date range**: Jan 2023 – Feb 2025 (112 weeks)

Regenerate: `npm run seed` (deterministic, PRNG seed=42)

---

## Test Users

| User ID | Name | Role | Brand | Retailer | Period |
|---------|------|------|-------|----------|--------|
| USR-001 | Sarah Johnson | Brand Manager | Apex | Walmart | L4W |
| USR-002 | Michael Chen | Sales Director | All brands | Walmart | L13W |
| USR-003 | Rachel Thompson | Category Analyst | Bolt | Walmart | L4W |
| USR-004 | David Park | Account Manager | Silke | Walmart | L4W |
| USR-005 | Jennifer Walsh | VP Sales | All brands | Walmart | YTD |

---

## Deployment (BigB VPS)

**Source on BigB**: `/root/retailgpt/` (git clone of btpope/RetailLLM)  
**Docker service**: `testgpt` in `/docker/n8n/docker-compose.yml`  
**Container**: `n8n-testgpt-1` · port 8000 internal  
**Traefik host rule**: `testgpt.srv1445355.hstgr.cloud`  
**Env vars**: `TESTGPT_API_KEY=testgpt2026`, `ANTHROPIC_API_KEY`, `ANALYST_MODEL=claude-sonnet-4-6`

**Hot-copy (Python/HTML changes — no schema/dep changes):**
```bash
sudo git -C /root/retailgpt pull <repo-url> master
sudo docker cp /root/retailgpt/<file> n8n-testgpt-1:/app/<file>
sudo docker restart n8n-testgpt-1   # required for Python files; not needed for HTML
```

**Full rebuild (schema, new dependencies, seeder changes):**
```bash
sudo git -C /root/retailgpt pull <repo-url> master
cd /docker/n8n && sudo docker compose build --no-cache testgpt
sudo docker compose up -d testgpt
```

---

## Key Decisions & Constraints

| Decision | Choice | Rationale |
|----------|--------|-----------|
| AI model | claude-sonnet-4-6 | Best-in-class reasoning + tool use for CPG analytics |
| Data scope | Walmart-only | CPG customer team at one retailer; no multi-retailer comparisons |
| Data grain | Weekly | CPG industry standard; sub-week not in v1 scope |
| Data layer | SQLite → Databricks Delta Lake | Zero-setup for prototype; ORM-agnostic swap for production |
| Metric store | Pre-computed at seed time | Consistent definitions, zero SQL hallucination, fast lookups |
| Charts | Vega-Lite via vega-embed CDN | Declarative, JSON-serializable specs; renders in dark theme |
| Infographic generation | Deferred to P2 | Requires Gemini API approval |
| No direct Anthropic in production | Databricks AI Gateway | Keeps data in governed perimeter (supplier data agreements) |
| HITL | Mandatory for all outbound actions | No email/assignment/publish without explicit user approval |
| Multi-turn memory | In-process Python dict | Prototype only; Redis for production |
| Feature branches | Yes (from Phase 4+) | PR-based review workflow agreed with Brad |

---

## Recent Commit History

| Hash | Description |
|------|-------------|
| `e8b81ab` | Fix: alerts panel reads `root_cause_narrative` |
| `ea05511` | Refactor + QA: fix pre-fetch brief kwargs, SKU trend indices, trim logic |
| `22ba562` | Fix: stale DB session on multi-turn + approval panel UI |
| `1fbe280` | UI: user avatar shows first+last initials (MC, SJ, RT, etc.) |
| `b805678` | UI: TG monogram (white T, blue G) replaces Walmart spark |
| `87152c8` | Phase 3: multi-turn memory, alerts panel, YoY line chart, history trimming |
| `36785b8` | Fix: supply chain SQLite binding |
| `546447a` | Phase 2: benchmark intelligence, trend analysis, supply chain data |
| `ea39011` | Phase 1: deep Walmart + CPG semantic layer in system prompt |
| `469028b` | Pre-computed metric store (Crisp-style) |
