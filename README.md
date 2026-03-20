# TestGPT — DecisionFrame AI (Prototype)

AI analyst agent for CPG retail analytics. Ask questions about your business in plain English — get back KPI narratives, trend analysis, promo ROI, and visual charts.

> ⚠️ **This is a prototype running on synthetic demo data only. All numbers are simulated.**

---

## Live Demo

**URL**: `https://testgpt.srv1445355.hstgr.cloud`
**Password**: `testgpt2026`

Pick a user from the dropdown (e.g. Sarah Johnson = Apex Brand Manager at Walmart/Target/Kroger), then ask questions like:
- "How is my business?"
- "How did my last promotion perform?"
- "Show me revenue YoY as a chart"
- "Which SKUs have the highest out-of-stock rate?"

---

## Architecture

```
Browser (Chat UI)
    ↓ POST /chat
FastAPI (api/main.py)
    ↓
RetailGPTAgent (agents/retailgpt_agent.py)
    ↓ tool calls
    ├── get_kpi_card      → KPI aggregation (models/queries.py)
    ├── execute_sql        → read-only SQL (models/queries.py)
    ├── get_business_summary → top KPIs + alerts
    ├── generate_vega_chart → Vega-Lite chart specs
    ├── get_promo_calendar → promo schedule
    ├── get_retailer_account → account scorecard
    └── search_memory      → session context
    ↓
Narrative + Vega-Lite charts
    ↓
Browser renders charts via vega-embed
```

**Prototype stack**: Python 3.11 · FastAPI · SQLite · Anthropic Claude claude-sonnet-4-6 · Vega-Lite
**Production stack** (planned): C#/.NET · Databricks Delta Lake · Azure AI Foundry (OpenAI-compatible) · Engine integration

---

## Local Setup

**Prerequisites**: Python 3.11+, Node.js 20+ (for seeding)

```bash
git clone https://github.com/btpope/RetailLLM.git
cd RetailLLM

# Install Python deps
pip install -r requirements.txt

# Seed the SQLite DB (117,600 rows of synthetic data)
npm install
npm run seed

# Configure
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY

# Start
uvicorn api.main:app --reload --port 8000
```

Open `http://localhost:8000` — no password needed (TESTGPT_API_KEY empty = open in dev mode).

---

## API Reference

All endpoints require `?api_key=<key>` or `X-API-Key` header (except `/health`, `/`, `/docs`).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Chat UI |
| `/health` | GET | Health check |
| `/chat` | POST | Main agent endpoint |
| `/summary/{user_id}` | GET | KPI cards for user |
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
  "narrative": "Here's your business summary...",
  "charts": [ /* Vega-Lite spec objects */ ],
  "issues": [],
  "pending_approval": null
}
```

---

## Synthetic Data

| Table | Rows | Description |
|-------|------|-------------|
| `sales_kpi_weekly` | 117,600 | Weekly sales by SKU × retailer × region, Jan 2023–Feb 2025 |
| `promo_calendar` | 234 | Promo events with lift, ROI, type |
| `retailer_account_scorecard` | 189 | Quarterly scorecards |
| `kpi_alert_log` | 120 | Open KPI alerts |
| `user_preferences` | 5 | Test users |

**Brands**: Apex (Salty Snacks), Bolt (Energy Drinks), Silke (Hair Care)
**Retailers**: Walmart, Target, Kroger, Costco, Publix, Safeway, HEB

Regenerate: `npm run seed` (deterministic, seed=42)

---

## Test Users

| User ID | Name | Role | Brand | Retailers | Period |
|---------|------|------|-------|-----------|--------|
| USR-001 | Sarah Johnson | Brand Manager | Apex | Walmart, Target, Kroger | L4W |
| USR-002 | Michael Chen | Sales Director | All | Walmart, Costco | L13W |
| USR-003 | Rachel Thompson | Category Analyst | Bolt | Walmart, Target, Kroger | L4W |
| USR-004 | David Park | Account Manager | Silke | Walmart, Costco, Kroger | L4W |
| USR-005 | Jennifer Walsh | VP Sales | All | All retailers | YTD |

---

## Deployment (BigB VPS)

Source: `/root/testgpt/` on `31.97.210.170`
Docker compose: `/docker/n8n/docker-compose.yml` (service: `testgpt`)
Traefik: auto-TLS via Let's Encrypt

**Redeploy after code changes**:
```bash
sudo git -C /root/testgpt pull <repo-url> master
cd /docker/n8n && sudo docker compose build --no-cache testgpt
sudo docker compose up -d testgpt
```
