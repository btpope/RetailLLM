# TestGPT — Open Questions & Assumptions

Generated during initial scaffold. Needs product input before Step 1 implementation begins.

---

## 🏗️ Infrastructure

| # | Question | Impact |
|---|----------|--------|
| I1 | **Which cloud?** AWS, GCP, or Azure? Affects DB choice, auth, and Gemini API availability. | High |
| I2 | **Which database?** SQLite is prototype-only. Production: Snowflake, BigQuery, Redshift, or Postgres? | High |
| I3 | **How many retailers?** Schema supports 8 top US retailers. Is that the right scope for v1? | Medium |
| I4 | **Data refresh cadence?** Weekly grain in schema. Is daily or intra-week needed for v1? | Medium |
| I5 | **Latency target?** "How is my business?" should return in how many seconds? Affects model choice. | High |

---

## 🔐 Auth & Access

| # | Question | Impact |
|---|----------|--------|
| A1 | **Auth model?** SSO/SAML, OAuth, API key, or session tokens? | High |
| A2 | **Data scoping enforcement**: Does retailer/brand scope come from the auth token or user_preferences table? | High |
| A3 | **Multi-tenant?** Are multiple CPG brands in the same instance, or one instance per client? | High |
| A4 | **Who can assign issues?** Any user, or only managers/admins? Role-based permission model needed. | Medium |

---

## 📊 Data & Schema

| # | Question | Impact |
|---|----------|--------|
| D1 | **Live Engine data connection**: Is Engine warehouse accessible via JDBC/ODBC/API? What credentials format? | High |
| D2 | **Synthetic data seed**: Should we generate realistic synthetic data for demo, or use anonymized real data? | Medium |
| D3 | **Prior year comparison**: Does `prior_year_*` come from the source, or do we compute it at query time? | Medium |
| D4 | **Category definitions**: Are category/sub_category standardized, or do they vary by retailer feed? | Medium |
| D5 | **Syndicated data** (Req #21 benchmarking): Nielsen/Circana feed available? Separate schema needed. | Medium |

---

## 🤖 Model & AI

| # | Question | Impact |
|---|----------|--------|
| M1 | **Claude model tier**: `claude-sonnet-4-6` assumed. Should `claude-opus-4` be used for high-stakes narratives? | Medium |
| M2 | **Gemini image API access**: Is `gemini-2.5-flash-exp` available and approved for Step 3? | P2 |
| M3 | **Model provider lock-in tolerance**: Is there a preference to stay Anthropic-only, or is provider flexibility a real requirement? | Medium |
| M4 | **Confidence scoring calibration**: How should "High / Medium / Low" confidence be defined for CPG recommendations? | Medium |

---

## 💬 Product / UX

| # | Question | Impact |
|---|----------|--------|
| P1 | **Frontend**: React SPA, embedded in Engine, or standalone? Affects Vega-Lite rendering approach. | High |
| P2 | **Issue queue UI**: Is there a Jira/Slack integration for issue assignment, or is it native to Engine? | Medium |
| P3 | **Narrative modes**: Should Executive/Merchant/Analyst be user-selectable per-query, or only configurable in settings? | Low |
| P4 | **Email delivery** (Req #17 Monday Reports): Which email provider? SendGrid, SES, or Engine native? | P2 |
| P5 | **Mobile support?** Vega-Lite charts are responsive, but narrative UX may need optimization for mobile buyers. | Low |

---

## ✅ Assumptions Made in Scaffold

1. **SQLite for prototype**: Swappable via `DB_URL` env var; ORM is DB-agnostic
2. **Claude Sonnet** as default model; configurable in `config/settings.py`
3. **Anthropic Python SDK** used for tool_use; `TestGPTAgent` uses the standard messages API
4. **FastAPI** for the API layer; can swap to Express/Next.js API routes if Engine is Node-based
5. **Top 8 US retailers** in synthetic data: Walmart, Target, Kroger, Costco, Amazon, CVS, Walgreens, Albertsons
6. **Weekly grain** for sales data (CPG industry standard); sub-week not scoped for v1
7. **In-memory session store** for prototype; Redis recommended for production
8. **Infographic generation deferred** until Google API access confirmed (P2)
9. **No PII in outputs** enforced by system prompt; not yet enforced in code (TODO)
10. **Req #23 (Engine-7B fine-tuning) explicitly deferred** — validate Claude base model first
