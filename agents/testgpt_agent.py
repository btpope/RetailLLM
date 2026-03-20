"""
TestGPT — Main Orchestration Agent (Step 1 Skeleton)
Implements the core analyst loop: receive query → call tools → return narrative + charts.

Architecture:
  - Model-agnostic: swap ANALYST_MODEL in config/settings.py, nothing else changes
  - Tool loop: runs until Claude stops requesting tools or max_iterations reached
  - HITL: send_for_approval halts the loop and surfaces a pending approval to the caller
  - All tool calls logged for audit trail (TODO: implement persistent logging)

Step 1 covers: Req #1, #2, #3, #4, #10, #11
Step 2 adds:   Req #5, #6, #7, #9 (reactive agents, issue workflow, HITL, user priorities)
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

import anthropic

from config.settings import ANALYST_MODEL, ANTHROPIC_API_KEY, SYNTHETIC_DATA_MODE, PROTOTYPE_LABEL
from tools.execute_sql import execute_sql, TOOL_DEFINITION as SQL_TOOL
from tools.generate_vega_chart import generate_vega_chart, TOOL_DEFINITION as CHART_TOOL
from tools.metric_store import get_metric, TOOL_DEFINITION as METRIC_TOOL
from tools.benchmark import (
    get_benchmark, BENCHMARK_TOOL_DEFINITION,
    get_trend_analysis, TREND_TOOL_DEFINITION,
)
from tools.kpi_tools import (
    get_kpi_card, KPI_CARD_TOOL,
    get_business_summary, BUSINESS_SUMMARY_TOOL,
    get_promo_calendar, PROMO_CALENDAR_TOOL,
    get_retailer_account, RETAILER_ACCOUNT_TOOL,
    search_memory, SEARCH_MEMORY_TOOL,
)
from tools.workflow_tools import (
    flag_issue, FLAG_ISSUE_TOOL,
    send_for_approval, SEND_FOR_APPROVAL_TOOL,
)

# All tools exposed to Claude — add generate_infographic_image here in Step 3
ALL_TOOLS = [
    METRIC_TOOL,               # P1: pre-computed metric store — first call for any KPI question
    BENCHMARK_TOOL_DEFINITION, # P2: benchmark comparisons + Walmart thresholds
    TREND_TOOL_DEFINITION,     # P2: multi-period trend signals + line review risk
    SEARCH_MEMORY_TOOL,        # load prefs before anything else
    BUSINESS_SUMMARY_TOOL,     # Req #1: "How is my business?" (fallback if metric_store insufficient)
    KPI_CARD_TOOL,             # Req #2/#4: single-metric drilldown (fallback)
    SQL_TOOL,                  # Req #10: ad-hoc custom queries only — last resort
    CHART_TOOL,                # Req #3: visualization
    PROMO_CALENDAR_TOOL,       # promo schedule
    RETAILER_ACCOUNT_TOOL,     # JBP / account scorecard
    FLAG_ISSUE_TOOL,           # Req #5: issue flagging
    SEND_FOR_APPROVAL_TOOL,    # Req #9: HITL gate
]

MAX_TOOL_ITERATIONS = 10  # Safety cap on agentic loops


def load_system_prompt(user_context: dict) -> str:
    """
    Load the base system prompt and inject per-user context.
    user_context keys: user_name, user_role, priority_metrics, retailer_scope,
                       region_scope, default_period, narrative_mode
    """
    prompt_path = Path(__file__).parent.parent / "prompts" / "testgpt_system_prompt.md"
    prompt = prompt_path.read_text()

    # Replace placeholders with actual user context
    replacements = {
        "[USER_NAME]":        user_context.get("user_name", "User"),
        "[USER_ROLE]":        user_context.get("user_role", "Brand Manager"),
        "[PRIORITY_METRICS]": user_context.get("priority_metrics", "Revenue, Velocity, OOS Rate"),
        "[RETAILER_SCOPE]":   user_context.get("retailer_scope", "All retailers"),
        "[REGION_SCOPE]":     user_context.get("region_scope", "National"),
        "[DEFAULT_PERIOD]":   user_context.get("default_period", "L4W"),
        "[NARRATIVE_MODE]":   user_context.get("narrative_mode", "Merchant"),
    }
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)

    if SYNTHETIC_DATA_MODE:
        prompt += f"\n\n> ⚠️ PROTOTYPE MODE ACTIVE — Label all outputs: {PROTOTYPE_LABEL}"

    return prompt


class TestGPTAgent:
    """
    Main analyst agent. One instance per user session.
    Maintains conversation history for multi-turn support.
    """

    def __init__(self, session, user_context: dict):
        """
        Args:
            session: SQLAlchemy DB session (injected by FastAPI dependency)
            user_context: Dict with user_id, user_name, role, preferences
        """
        self.session = session
        self.user_context = user_context
        self.system_prompt = load_system_prompt(user_context)
        self.conversation_history: list[dict] = []
        self._first_turn = True         # used to gate the one-time data brief injection
        self._turn_count = 0            # tracks total turns for trimming

        # TODO: Restore prior conversation history from search_memory
        # TODO: Initialize Anthropic client from provider factory (for model-switching)
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # ── History management ────────────────────────────────────────────────────
    _MAX_HISTORY_PAIRS = 12   # keep last 12 user+assistant exchange pairs (24 messages)
    _TRIM_TO_PAIRS     = 8    # after trimming, keep 8 pairs (16 messages)

    def _trim_history(self):
        """Keep conversation history within token-safe bounds.
        Never trims the first 2 messages (data brief + ack).
        """
        # Count only role=user/assistant messages (not tool_result blobs)
        # Preserve first 2 (brief + ack) + last N pairs
        if len(self.conversation_history) <= self._MAX_HISTORY_PAIRS * 2 + 2:
            return
        preserved = self.conversation_history[:2]   # brief + ack
        rest = self.conversation_history[2:]
        # Keep last _TRIM_TO_PAIRS * 2 messages
        rest = rest[-(self._TRIM_TO_PAIRS * 2):]
        self.conversation_history = preserved + rest

    def chat(self, user_message: str) -> "AgentResponse":
        """
        Main entry point. Accepts a user message, runs the tool loop, returns response.

        Returns an AgentResponse with:
          - narrative: the final text answer
          - charts: list of Vega-Lite specs
          - issues: list of flagged issues
          - pending_approval: HITL approval request (if any — pauses further action)
        """
        self._turn_count += 1
        self._trim_history()

        # ── Speed optimisation: pre-fetch & inject business context ─────────
        # Inject ONCE on the first turn only. Subsequent turns use accumulated history.
        if not self._first_turn:
            self.conversation_history.append({"role": "user", "content": user_message})
            return self._run_tool_loop(charts=[], issues=[], pending_approval=None)

        self._first_turn = False
        try:
            from tools.kpi_tools import get_business_summary
            brief = get_business_summary(
                session=self.session,
                user_id=self.user_context.get("user_id", ""),
                retailer_scope=self.user_context.get("retailer_scope", ""),
                brand_scope=self.user_context.get("brand_scope", ""),
                default_period=self.user_context.get("default_period", "L4W"),
            )
            if brief and not brief.get("error"):
                kpi_lines = []
                for card in brief.get("kpi_cards", []):
                    delta = f"{card['delta_pct']:+.1f}%" if card.get("delta_pct") is not None else "n/a"
                    kpi_lines.append(
                        f"  • {card['metric']}: {card.get('unit','')}{card.get('current_value','n/a')} "
                        f"({delta} vs prior {card.get('period_label','')}) [{card.get('trend','flat').upper()}]"
                    )
                alerts = brief.get("open_alerts", [])
                alert_lines = [f"  • [{a.get('severity','?')}] {a.get('alert_message','')}" for a in alerts[:3]]
                brief_text = (
                    f"[PRE-FETCHED DATA BRIEF — use this directly, do not call search_memory or get_business_summary]\n"
                    f"User: {self.user_context.get('user_name')} | Role: {self.user_context.get('user_role')} | "
                    f"Brand: {self.user_context.get('brand_scope') or 'All'} | "
                    f"Retailer: {self.user_context.get('retailer_scope')} | "
                    f"Period: {brief.get('period_label')} ending {brief.get('anchor_date')}\n\n"
                    f"KPI Summary:\n" + "\n".join(kpi_lines) + "\n\n" +
                    (f"Open Alerts:\n" + "\n".join(alert_lines) if alert_lines else "Open Alerts: None") +
                    "\n\nYou already have this data. Answer the user's question using it. "
                    "Only call tools if you need data NOT shown above (e.g. specific SKU drill-down, promo details, chart generation)."
                )
                self.conversation_history.append({
                    "role": "user",
                    "content": brief_text,
                })
                self.conversation_history.append({
                    "role": "assistant",
                    "content": "Understood. I have the pre-fetched business data and will use it directly.",
                })
        except Exception:
            pass  # pre-fetch failure is non-fatal; Claude will call tools normally

        # Append user message then hand off to shared tool loop
        self.conversation_history.append({"role": "user", "content": user_message})
        return self._run_tool_loop(charts=[], issues=[], pending_approval=None)

    def _run_tool_loop(
        self,
        charts: list[dict],
        issues: list[dict],
        pending_approval: dict | None,
    ) -> "AgentResponse":
        """Run the Claude tool loop on the current conversation history."""
        # ── Tool loop ────────────────────────────────────────────────────────
        for iteration in range(MAX_TOOL_ITERATIONS):

            # TODO: Support provider switching (OpenAI, Google) via a model factory
            response = self.client.messages.create(
                model=ANALYST_MODEL,
                max_tokens=4096,
                system=self.system_prompt,
                tools=ALL_TOOLS,
                messages=self.conversation_history,
            )

            # If Claude has finished (no more tool calls), return
            if response.stop_reason == "end_turn":
                narrative = _extract_text(response)
                self.conversation_history.append({"role": "assistant", "content": response.content})
                return AgentResponse(
                    narrative=narrative,
                    charts=charts,
                    issues=issues,
                    pending_approval=pending_approval,
                )

            # Process tool calls
            if response.stop_reason == "tool_use":
                tool_results = []
                self.conversation_history.append({"role": "assistant", "content": response.content})

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name = block.name
                    tool_input = block.input
                    result = self._dispatch_tool(tool_name, tool_input)

                    # Collect charts and issues for structured response
                    if tool_name == "generate_vega_chart" and result.get("spec"):
                        charts.append(result)
                    elif tool_name == "flag_issue":
                        issues.append(result)
                    elif tool_name == "send_for_approval":
                        pending_approval = result

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

                    # HITL: if approval is pending, halt loop and surface to user
                    if tool_name == "send_for_approval":
                        self.conversation_history.append({"role": "user", "content": tool_results})
                        return AgentResponse(
                            narrative="Action requires your approval before proceeding.",
                            charts=charts,
                            issues=issues,
                            pending_approval=pending_approval,
                        )

                self.conversation_history.append({"role": "user", "content": tool_results})

        # Safety: exceeded max iterations
        return AgentResponse(
            narrative="TestGPT reached the maximum analysis depth. Please try a more specific question.",
            charts=charts,
            issues=issues,
            pending_approval=None,
        )

    def _dispatch_tool(self, tool_name: str, tool_input: dict) -> dict:
        """Route a tool call to the correct handler. Add new tools here."""
        # TODO: Add structured logging for every tool call (audit trail)
        try:
            if tool_name == "execute_sql":
                return execute_sql(
                    self.session,
                    query_type=tool_input.get("query_type"),
                    params=tool_input.get("params"),
                    raw_sql=tool_input.get("raw_sql"),
                )
            elif tool_name == "get_metric":
                return get_metric(self.session, **tool_input)
            elif tool_name == "get_benchmark":
                return get_benchmark(self.session, **tool_input)
            elif tool_name == "get_trend_analysis":
                return get_trend_analysis(self.session, **tool_input)
            elif tool_name == "generate_vega_chart":
                return generate_vega_chart(**tool_input)
            elif tool_name == "get_kpi_card":
                return get_kpi_card(self.session, tool_input["metric"], tool_input.get("filters"))
            elif tool_name == "get_business_summary":
                return get_business_summary(self.session, **tool_input)
            elif tool_name == "get_promo_calendar":
                return get_promo_calendar(self.session, **tool_input)
            elif tool_name == "get_retailer_account":
                return get_retailer_account(self.session, **tool_input)
            elif tool_name == "search_memory":
                return search_memory(self.session, **tool_input)
            elif tool_name == "flag_issue":
                return flag_issue(self.session, **tool_input)
            elif tool_name == "send_for_approval":
                return send_for_approval(**tool_input)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            # TODO: Log full traceback
            return {"error": f"Tool '{tool_name}' failed: {str(e)}"}


class AgentResponse:
    """Structured response from TestGPTAgent.chat()"""

    def __init__(self, narrative: str, charts: list, issues: list, pending_approval: dict | None):
        self.narrative = narrative
        self.charts = charts          # Vega-Lite specs for rendering
        self.issues = issues          # Flagged issues for the issue queue
        self.pending_approval = pending_approval  # HITL gate — must be resolved before next action

    def to_dict(self) -> dict:
        return {
            "narrative": self.narrative,
            "charts": self.charts,
            "issues": self.issues,
            "pending_approval": self.pending_approval,
            "has_approval_gate": self.pending_approval is not None,
        }


def _extract_text(response) -> str:
    """Extract plain text from Claude's response content blocks."""
    parts = []
    for block in response.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts)
