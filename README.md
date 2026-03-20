# RetailGPT — Prototype Scaffold

AI analyst agent for CPG retail analytics, built on **Anthropic Claude** as primary reasoning model.

**Status:** Step 1 skeleton — interfaces and stubs, not full implementations.

---

## Architecture

```
RetailLLM/
├── api/
│   └── main.py              ← FastAPI endpoint (POST /chat, POST /approve, GET /issues)
├── agents/
│   └── retailgpt_agent.py   ← Main orchestration loop (tool use + HITL)
├── tools/
│   ├── execute_sql.py        ← SQL query tool (read-only enforced)
│   ├── generate_vega_chart.py ← Vega-Lite chart spec generator
│   ├── kpi_tools.py          ← get_kpi_card, get_promo_calendar, get_retailer_account, search_memory
│   └── workflow_tools.py     ← flag_issue, send_for_approval, generate_infographic_image (P2)
├── models/
│   ├── schema.py             ← SQLAlchemy ORM (5 tables from Synthetic Data Schema)
│   └── queries.py            ← Pre-built read-only query library
├── prompts/
│   └── retailgpt_system_prompt.md ← Full Claude system prompt
├── config/
│   └── settings.py           ← Model/provider/DB config (swap model = change 1 line)
└── README.md
```

---

## Implementation Steps

| Step | Requirements | Status |
|------|-------------|--------|
| **Step 1** — Core analytics: conversation, KPI narratives, charts | #1, #2, #3, #4, #10, #11 | 🔧 Skeleton |
| **Step 2** — Reactive agents, issue workflow, HITL, user priorities | #5, #6, #7, #9 | 📋 Planned |
| **Step 3** — Infographic generation via Gemini (optional) | #8 | 📋 P2 |

---

## Quickstart

```bash
# Install dependencies
pip install anthropic fastapi uvicorn sqlalchemy

# Set environment variables
export ANTHROPIC_API_KEY=your_key
export SYNTHETIC_DATA_MODE=true  # Uses synthetic data; labels all outputs [SYNTHETIC DATA — DEMO ONLY]

# Create DB tables
python models/schema.py

# Run the API
uvicorn api.main:app --reload --port 8000

# Test
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "USR-001", "message": "How is my business?"}'
```

---

## Switching the Base Model

Everything is model-agnostic. To switch from Claude to GPT-4 or Gemini:

```python
# config/settings.py
ANALYST_MODEL    = "gpt-4o"
ANALYST_PROVIDER = "openai"
```

The agent graph does not need to change. Only the client initialization in `retailgpt_agent.py` needs a provider factory (TODO item).

---

## Key Design Decisions

- **Read-only enforced**: `_assert_readonly()` blocks any SQL mutation before execution
- **HITL mandatory**: `send_for_approval` always halts the tool loop before any outbound action
- **Model-agnostic**: provider/model in `config/settings.py`; agent graph unchanged
- **Synthetic data mode**: `SYNTHETIC_DATA_MODE=true` labels all outputs; realistic CPG ranges
- **Per-user context**: user preferences loaded from `user_preferences` table shape every default summary

---

## Open Questions (See OPEN_QUESTIONS.md)
