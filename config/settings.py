"""
TestGPT — Configuration
All model/provider keys and endpoints live here.
Switching the base model = change ANALYST_MODEL. The agent graph is model-agnostic.
"""

import os

# ─── Primary Model (Reasoning, SQL, Charts, Narratives) ──────────────────────
ANALYST_MODEL = os.getenv("ANALYST_MODEL", "claude-sonnet-4-6")   # Anthropic default
ANALYST_PROVIDER = os.getenv("ANALYST_PROVIDER", "anthropic")     # "anthropic" | "google" | "openai"

# Provider API keys — set via environment, never hardcode
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY    = os.getenv("GOOGLE_API_KEY", "")

# ─── Secondary Model (Infographic Image Generation — P2) ─────────────────────
INFOGRAPHIC_MODEL    = os.getenv("INFOGRAPHIC_MODEL", "gemini-2.5-flash-exp")
INFOGRAPHIC_PROVIDER = os.getenv("INFOGRAPHIC_PROVIDER", "google")
INFOGRAPHIC_ENDPOINT = os.getenv(
    "INFOGRAPHIC_ENDPOINT",
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-exp:generateContent"
)

# ─── Database ─────────────────────────────────────────────────────────────────
# TODO: Replace with real Engine warehouse connection string
DB_URL = os.getenv("DB_URL", "sqlite:///./testgpt_prototype.db")  # SQLite for prototype

# ─── Safety ───────────────────────────────────────────────────────────────────
READONLY_ENFORCED = True   # Never set to False in production
MAX_SQL_ROWS      = 10_000 # Guard against accidental full-table scans

# ─── Prototype Flags ──────────────────────────────────────────────────────────
SYNTHETIC_DATA_MODE = os.getenv("SYNTHETIC_DATA_MODE", "true").lower() == "true"
PROTOTYPE_LABEL     = "[SYNTHETIC DATA — DEMO ONLY]"
