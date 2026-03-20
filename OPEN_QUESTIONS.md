# TestGPT — Open Questions & Assumptions
**Last Updated:** 2026-03-20

---

## ✅ Resolved Questions

| # | Question | Decision |
|---|----------|----------|
| I1 | Which cloud? | Azure — Engine's existing infrastructure |
| I2 | Which database? | SQLite (prototype) → Databricks Delta Lake (production) |
| I3 | How many retailers? | **Walmart only** — CPG customer team calling on one retailer; multi-retailer removed from prototype scope |
| I4 | Data refresh cadence? | Weekly grain; daily/intra-week not in v1 scope |
| I5 | Latency target? | Target <20s; current avg ~10–20s with pre-fetch brief optimization |
| A1 | Auth model? | API key for prototype (`TESTGPT_API_KEY`); SSO/SAML for production Engine |
| D2 | Synthetic data? | Yes — fully synthetic, deterministic (seed=42), labeled `[SYNTHETIC DATA — DEMO ONLY]` |
| D3 | Prior year comparison? | Computed at query time via anchor-date-aware period bounds |
| M1 | Claude model tier? | `claude-sonnet-4-6` — best quality/speed balance for CPG narratives |
| M2 | Gemini image API? | Deferred to P2 — `generate_infographic_image` is a stub |
| M3 | Model provider lock-in? | Provider-agnostic by design (`ANALYST_MODEL` + `ANALYST_PROVIDER` config) |

---

## 🔍 Still Pending — Needs Product Input

### Infrastructure
| # | Question | Impact |
|---|----------|--------|
| I6 | **Production OTIF/supply chain data source?** Engine warehouse has OTIF/DC fill rate? Or does it come from a separate supplier scorecard system (e.g., Retail Link Direct Connect)? | High |

### Auth & Access
| # | Question | Impact |
|---|----------|--------|
| A2 | **Data scoping enforcement**: Does retailer/brand scope come from the auth token or user_preferences table in production? | High |
| A3 | **Multi-tenant?** One Engine instance per CPG client, or multiple brands in one instance with row-level security? | High |
| A4 | **Issue assignment permissions?** Any user can assign, or managers/admins only? Role model needed for `flag_issue` → `send_for_approval` → assign flow. | Medium |

### Data & Schema
| # | Question | Impact |
|---|----------|--------|
| D1 | **Live Engine data connection**: Is the Engine warehouse accessible via JDBC/ODBC/REST API? What's the credential format? | High |
| D4 | **Category definitions**: Are `category`/`sub_category` standardized across retailer feeds, or do they vary? Affects Fineline mapping. | Medium |
| D5 | **Walmart-specific fields**: Should OTIF rate and DC fill rate be added to the main `sales_kpi_weekly` grain, or kept in a separate supply chain table? | Medium |
| D6 | **Actual Engine client data**: Brad to provide real velocity/price ranges for Apex/Bolt/Silke equivalents to calibrate synthetic data better. Current ranges are educated estimates. | Low |

### Model & AI
| # | Question | Impact |
|---|----------|--------|
| M4 | **Confidence scoring calibration**: How should HIGH/MEDIUM/LOW confidence be defined for CPG recommendations? Tie to data recency? Sample size? | Medium |
| M5 | **Session memory persistence**: In-memory dict works for prototype. Production: Redis? DB-backed? What's the session expiry policy? | Medium |

### Product / UX
| # | Question | Impact |
|---|----------|--------|
| P1 | **Frontend integration**: Standalone SPA (current), or embed in Engine Glass? Affects Vega-Lite rendering approach. | High |
| P2 | **Issue queue UI**: Native to Engine, or Jira/Slack integration for issue assignment? | Medium |
| P3 | **Narrative mode**: Executive/Merchant/Analyst selectable per-query (current: per user config only)? | Low |
| P4 | **Monday Reports** (Req #17): Email provider for scheduled reports? SendGrid, SES, or Engine native? | P2 |
| P5 | **Walmart-specific fields to add**: Brad to confirm which additional fields are needed (e.g., OTIF rate at item level, DC fill rate, on-shelf availability from store checks). | Medium |
| P6 | **Bolt velocity max**: Synthetic data caps Bolt promo velocity at ~40 U/S/W. Brad to confirm this is realistic for extreme promo weeks. | Low |

---

## Assumptions in Effect

1. **Walmart-only** — no multi-retailer comparisons; all users have `retailer_scope: Walmart`
2. **Weekly grain** — sub-week analysis not in scope for v1
3. **SQLite for prototype** — swappable via `DB_URL` env var; SQLAlchemy is DB-agnostic
4. **In-memory session store** — `_agent_sessions` dict; Redis recommended for production
5. **Infographic generation deferred** — until Gemini API access confirmed (P2)
6. **No PII in outputs** — enforced by system prompt; not yet enforced in code (TODO for production)
7. **HITL mandatory** — all outbound actions require explicit user approval; no autonomous sends
8. **Req #23 (Engine-7B fine-tuning) explicitly deferred** — validate Claude base model first
9. **Feature branches from Phase 4** — PR-based review workflow; no direct pushes to master for features
10. **Hot-copy for Python files** — `docker cp` + `docker restart`; full rebuild only for schema/dependency changes
