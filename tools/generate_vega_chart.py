"""
TestGPT Tool: generate_vega_chart
Builds a Vega-Lite JSON spec from tabular data and a chart type.
Claude calls this after execute_sql returns rows.
The frontend renders the spec using the Vega-Lite runtime.
"""

from __future__ import annotations
from typing import Any
import json


# ─── Tool Definition (Claude tool_use schema) ─────────────────────────────────
TOOL_DEFINITION = {
    "name": "generate_vega_chart",
    "description": (
        "Generate a Vega-Lite JSON specification for a chart. "
        "The spec is returned to the frontend for rendering. "
        "Select the best chart type based on data shape and question intent."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "chart_type": {
                "type": "string",
                "enum": ["line", "bar", "horizontal_bar", "scatter", "pie", "stacked_bar", "bullet"],
                "description": (
                    "Chart type selection guide:\n"
                    "  line           → trends over time\n"
                    "  bar            → compare ≤5 categories\n"
                    "  horizontal_bar → compare >5 categories or long labels\n"
                    "  scatter        → correlation between two metrics\n"
                    "  pie            → composition (≤6 slices only)\n"
                    "  stacked_bar    → part-of-whole over time\n"
                    "  bullet         → KPI vs. target"
                ),
            },
            "data": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Array of row dicts from execute_sql output.",
            },
            "x_field": {"type": "string", "description": "Column name for X axis."},
            "y_field": {"type": "string", "description": "Column name for Y axis (primary metric)."},
            "color_field": {"type": "string", "description": "Optional: column for color/grouping."},
            "title": {"type": "string", "description": "Chart title shown above the visualization."},
            "x_label": {"type": "string", "description": "X axis label."},
            "y_label": {"type": "string", "description": "Y axis label."},
            "caption": {"type": "string", "description": "One-sentence narrative caption below the chart."},
        },
        "required": ["chart_type", "data", "x_field", "y_field", "title"],
    },
}


# ─── Tool Handler ─────────────────────────────────────────────────────────────
def generate_vega_chart(
    chart_type: str,
    data: list[dict],
    x_field: str,
    y_field: str,
    title: str,
    color_field: str = None,
    x_label: str = None,
    y_label: str = None,
    caption: str = None,
) -> dict[str, Any]:
    """
    Returns a Vega-Lite spec dict ready for frontend rendering.

    Args:
        chart_type: One of the supported types
        data: Rows from execute_sql
        x_field, y_field: Column names for axes
        title: Chart title
        color_field: Optional grouping dimension
        x_label, y_label: Axis labels (defaults to field name if omitted)
        caption: Narrative caption for the chart

    Returns:
        { "spec": <Vega-Lite JSON>, "caption": str, "chart_type": str }
    """
    if not data:
        return {"spec": None, "caption": "No data available for this chart.", "chart_type": chart_type}

    # TODO: Add input validation (check fields exist in data rows)
    # TODO: Add synthetic data watermark to spec for prototype mode (from config.settings.PROTOTYPE_LABEL)
    # TODO: Support custom color palettes per brand

    spec = _build_spec(chart_type, data, x_field, y_field, color_field, title, x_label, y_label)

    return {
        "spec": spec,
        "caption": caption or f"{title} — {y_label or y_field} by {x_label or x_field}",
        "chart_type": chart_type,
    }


def _build_spec(chart_type, data, x_field, y_field, color_field, title, x_label, y_label) -> dict:
    """Build the Vega-Lite spec dict for a given chart type."""

    base = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "data": {"values": data},
        "width": "container",
        "height": 300,
    }

    x_axis = {"field": x_field, "title": x_label or x_field}
    y_axis = {"field": y_field, "title": y_label or y_field, "type": "quantitative"}

    if chart_type == "line":
        # Time-series trend
        x_axis["type"] = "temporal"
        encoding = {"x": x_axis, "y": y_axis}
        if color_field:
            encoding["color"] = {"field": color_field, "type": "nominal"}
        base.update({"mark": {"type": "line", "point": True}, "encoding": encoding})

    elif chart_type in ("bar", "horizontal_bar"):
        # Category comparison
        # Auto-detect which field is categorical vs numeric — don't trust Claude's x/y order
        def _is_numeric(field):
            vals = [row.get(field) for row in data if row.get(field) is not None]
            if not vals:
                return False
            try:
                [float(v) for v in vals]
                return True
            except (TypeError, ValueError):
                return False

        # Identify categorical and metric fields
        if _is_numeric(y_field) and not _is_numeric(x_field):
            cat_field, metric_field = x_field, y_field
        elif _is_numeric(x_field) and not _is_numeric(y_field):
            cat_field, metric_field = y_field, x_field
        else:
            # Both numeric or both nominal — trust original order
            cat_field, metric_field = x_field, y_field

        cat_axis    = {"field": cat_field,    "type": "nominal",      "title": x_label or cat_field}
        metric_axis = {"field": metric_field, "type": "quantitative", "title": y_label or metric_field}

        avg_label_len = sum(len(str(row.get(cat_field, ""))) for row in data) / max(len(data), 1)
        use_horizontal = chart_type == "horizontal_bar" or avg_label_len > 12 or len(data) > 6

        encoding = {}
        if use_horizontal:
            encoding["y"] = {**cat_axis, "sort": "-x"}
            encoding["x"] = metric_axis
        else:
            encoding["x"] = cat_axis
            encoding["y"] = metric_axis

        if color_field:
            encoding["color"] = {"field": color_field, "type": "nominal"}
        base["height"] = max(300, len(data) * 36) if use_horizontal else 300
        base.update({"mark": {"type": "bar", "cornerRadiusEnd": 3}, "encoding": encoding})

    elif chart_type == "scatter":
        # Correlation
        x_axis["type"] = "quantitative"
        encoding = {"x": x_axis, "y": y_axis}
        if color_field:
            encoding["color"] = {"field": color_field, "type": "nominal"}
        base.update({"mark": {"type": "point", "filled": True}, "encoding": encoding})

    elif chart_type == "pie":
        # Composition — max 6 slices
        base.update({
            "mark": "arc",
            "encoding": {
                "theta": {"field": y_field, "type": "quantitative"},
                "color": {"field": x_field, "type": "nominal"},
            },
        })

    elif chart_type == "stacked_bar":
        # Part-of-whole over time
        x_axis["type"] = "temporal"
        encoding = {
            "x": x_axis,
            "y": {**y_axis, "stack": "normalize"},
            "color": {"field": color_field or x_field, "type": "nominal"},
        }
        base.update({"mark": "bar", "encoding": encoding})

    elif chart_type == "bullet":
        # KPI vs target — TODO: implement full bullet spec
        # Placeholder: simple bar with reference line
        x_axis["type"] = "nominal"
        base.update({
            "mark": "bar",
            "encoding": {"x": x_axis, "y": y_axis},
            # TODO: Add reference line layer for target value
        })

    else:
        # Fallback: plain bar
        x_axis["type"] = "nominal"
        base.update({"mark": "bar", "encoding": {"x": x_axis, "y": y_axis}})

    return base
