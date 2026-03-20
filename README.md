# RetailGPT

AI analyst agent for CPG retail analytics — powered by Claude (Anthropic).

**Status:** Step 1 complete — end-to-end `/chat` working with real SQLite data.

---

## Quickstart

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Seed the database
node scripts/generate_synthetic_data.js
# → creates retailgpt_prototype.db with 117,600 rows of Walmart/CPG data

# 3. Configure
cp .env.example .env
# edit .env → add your ANTHROPIC_API_KEY

# 4. Run
uvicorn api.main:app --reload --port 8000
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Status check |
| `GET`  | `/users` | List test users |
| `GET`  | `/summary/{user_id}` | Quick KPI summary (no Claude, data layer only) |
| `POST` | `/chat` | Main analyst chat (Claude tool loop) |
| `POST` | `/approve` | HITL approval gate |
| `GET`  | `/issues` | Open alert queue for a user |
| `DELETE` | `/sessions/{id}` | Clear conversation history |

---

## Test Calls

```bash
# Check data layer (no API key needed)
curl http://localhost:8000/users
curl http://localhost:8000/summary/USR-001
curl http://localhost:8000/summary/USR-002?period_weeks=13

# Full Claude agent call
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "USR-001", "message": "How is my business?"}'

# Single metric drilldown
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "USR-001", "message": "What is OOS rate at Walmart for Apex this month?", "session_id": "USR-001"}'

# Promo analysis
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "USR-002", "message": "Show me Walmart promo ROI for the last year"}'
```

---

## Users (prototype)

| ID | Name | Role | Scope |
|----|------|------|-------|
| USR-001 | Sarah Johnson | Brand Manager | Walmart/Target/Kroger — Apex only |
| USR-002 | Michael Chen | Sales Director | Walmart/Costco — Southeast+Midwest |
| USR-003 | Rachel Thompson | Category Manager | Kroger/Albertsons/CVS — Bolt+Silke |
| USR-004 | James Williams | Retail Ops VP | All retailers — all brands |
| USR-005 | Emily Davis | Analyst | All retailers — Apex only |

---

## Architecture

```
POST /chat
  → _resolve_user_context (load prefs from user_preferences)
  → RetailGPTAgent.chat()
      → Claude (claude-sonnet-4-6) tool loop
          → search_memory        load user prefs
          → get_business_summary L4W KPI cards, ranked by change
          → get_kpi_card         single-metric current vs. prior
          → execute_sql          flexible read-only queries
          → generate_vega_chart  Vega-Lite spec for frontend
          → get_promo_calendar   promo events + ROI
          → get_retailer_account quarterly scorecard (JBP)
          → flag_issue           surface anomaly for review
          → send_for_approval    HITL gate (halts loop)
  → AgentResponse { narrative, charts[], issues[], pending_approval }
```

### Data

- **DB:** SQLite `retailgpt_prototype.db` (117,600 rows, Jan 2023 – Feb 2025)
- **Brands:** Apex (Snacks), Bolt (Energy Drinks), Silke (Hair Care)
- **Retailers:** Walmart, Target, Kroger, Costco, Amazon, CVS, Walgreens, Albertsons
- **Calibration:** Velocity/price/promo lift/ROI ranges from Brad Pope / Perplexity spec 2026-03-20

### Production path

- Swap `DB_URL` for Databricks SQL connector
- Set `ANALYST_PROVIDER=openai` + `OPENAI_API_KEY=dapi...` for Azure AI Foundry (Claude via Databricks AI Gateway)
- Port API to C#/.NET to match Engine team stack

---

## Step Roadmap

| Step | Requirements | Status |
|------|-------------|--------|
| Step 1 | #1,#2,#3,#4,#10,#11 — core analytics + tool loop | ✅ Done |
| Step 2 | #5,#6,#7,#9 — reactive agents, issue workflow, per-user priorities | 🔲 Next |
| Step 3 | #8 — Gemini infographic image generation | 🔲 P2 |

---

*[SYNTHETIC DATA — DEMO ONLY]*
