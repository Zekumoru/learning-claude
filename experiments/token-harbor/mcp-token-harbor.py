#!/usr/bin/env python3
import sys
import json
import os
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

LITELLM_PRICING_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
)

FALLBACK_PRICES = {
    "claude-sonnet-4-6": {
        "input_cost_per_token": 3e-6,
        "output_cost_per_token": 15e-6,
        "cache_creation_input_token_cost": 3.75e-6,
        "cache_read_input_token_cost": 0.30e-6,
    },
    "claude-opus-4-8": {
        "input_cost_per_token": 15e-6,
        "output_cost_per_token": 75e-6,
        "cache_creation_input_token_cost": 18.75e-6,
        "cache_read_input_token_cost": 1.50e-6,
    },
    "claude-haiku-4-5-20251001": {
        "input_cost_per_token": 0.80e-6,
        "output_cost_per_token": 4e-6,
        "cache_creation_input_token_cost": 1.00e-6,
        "cache_read_input_token_cost": 0.08e-6,
    },
}

TOOL = {
    "name": "get_usage",
    "description": (
        "Returns token usage and estimated cost across Claude Code sessions. "
        "By default aggregates all projects since the very beginning. "
        "Supports date range filtering and project scoping."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "Start date YYYY-MM-DD (inclusive). Omit for all time.",
            },
            "end_date": {
                "type": "string",
                "description": "End date YYYY-MM-DD (inclusive). Omit for all time.",
            },
            "project": {
                "type": "string",
                "description": (
                    '"all" (default) — every project under ~/.claude/projects/; '
                    '"current" — only the project for the active working directory; '
                    'any other string — treated as a project slug to match exactly.'
                ),
            },
        },
    },
}


def fetch_litellm_prices():
    try:
        with urllib.request.urlopen(LITELLM_PRICING_URL, timeout=8) as resp:
            data = json.loads(resp.read())
        prices = {
            model: entry
            for model, entry in data.items()
            if isinstance(entry, dict) and "input_cost_per_token" in entry
        }
        return prices, "live (LiteLLM)"
    except Exception:
        return FALLBACK_PRICES, "hardcoded fallback"


def get_current_project_slug():
    cwd = os.environ.get("PWD", os.getcwd())
    return cwd.replace("/", "-")


def collect_jsonl_paths(project_filter):
    projects_root = Path.home() / ".claude" / "projects"
    if not projects_root.exists():
        return []

    if project_filter in (None, "all"):
        dirs = [d for d in projects_root.iterdir() if d.is_dir()]
    elif project_filter == "current":
        slug = get_current_project_slug()
        d = projects_root / slug
        dirs = [d] if d.is_dir() else []
    else:
        d = projects_root / project_filter
        dirs = [d] if d.is_dir() else []

    paths = []
    for d in dirs:
        paths.extend(d.glob("*.jsonl"))
        paths.extend(d.glob("*/subagents/*.jsonl"))
    return paths


def parse_all_sessions(paths, start_date, end_date):
    start_prefix = start_date or ""
    end_prefix = (end_date + "T23:59:59.999Z") if end_date else ""

    seen_msg_ids = set()
    by_model = {}
    total_turns = 0
    active_sessions = set()
    active_projects = set()

    for path in paths:
        session_had_turns = False
        try:
            lines_raw = path.read_text().splitlines()
        except Exception:
            continue

        for raw in lines_raw:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if obj.get("type") != "assistant":
                continue

            ts = obj.get("timestamp", "")
            if start_prefix and ts < start_prefix:
                continue
            if end_prefix and ts > end_prefix:
                continue

            msg = obj.get("message") or {}
            msg_id = msg.get("id")
            if msg_id:
                if msg_id in seen_msg_ids:
                    continue
                seen_msg_ids.add(msg_id)

            usage = msg.get("usage") or {}
            input_t = usage.get("input_tokens", 0)
            output_t = usage.get("output_tokens", 0)
            cache_w = usage.get("cache_creation_input_tokens", 0)
            cache_r = usage.get("cache_read_input_tokens", 0)

            if input_t == 0 and output_t == 0 and cache_w == 0 and cache_r == 0:
                continue

            model = msg.get("model") or "unknown"
            if model not in by_model:
                by_model[model] = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
            by_model[model]["input"] += input_t
            by_model[model]["output"] += output_t
            by_model[model]["cache_write"] += cache_w
            by_model[model]["cache_read"] += cache_r
            total_turns += 1
            session_had_turns = True

        if session_had_turns:
            active_sessions.add(path)
            # Project dir is two levels up from subagent files, one level up from root files
            if "subagents" in path.parts:
                active_projects.add(path.parent.parent.parent)
            else:
                active_projects.add(path.parent)

    return {
        "projects": len(active_projects),
        "sessions": len(active_sessions),
        "turns": total_turns,
        "by_model": by_model,
    }


def compute_cost(tokens, model, prices):
    entry = prices.get(model) or {}
    return (
        tokens["input"] * entry.get("input_cost_per_token", 0)
        + tokens["output"] * entry.get("output_cost_per_token", 0)
        + tokens["cache_write"] * entry.get("cache_creation_input_token_cost", 0)
        + tokens["cache_read"] * entry.get("cache_read_input_token_cost", 0)
    )


def format_output(result, prices, prices_source, fetched_at, start_date, end_date, project_filter):
    if start_date and end_date:
        date_range = f"{start_date} to {end_date}"
    elif start_date:
        date_range = f"from {start_date}"
    elif end_date:
        date_range = f"up to {end_date}"
    else:
        date_range = "all time"

    if project_filter in (None, "all"):
        scope = "all projects"
    elif project_filter == "current":
        scope = f"project: {get_current_project_slug()}"
    else:
        scope = f"project: {project_filter}"

    header = f"Token Usage & Cost Summary ({date_range}, {scope})"
    meta = f"Sessions: {result['sessions']}  |  Turns: {result['turns']}  |  Projects: {result['projects']}"

    col_w = {"model": 26, "input": 12, "output": 10, "cache_w": 10, "cache_r": 12, "cost": 10}
    sep = "─" * (sum(col_w.values()) + len(col_w) - 1)
    col_header = (
        f"{'Model':<{col_w['model']}} {'Input':>{col_w['input']}} {'Output':>{col_w['output']}} "
        f"{'Cache↑':>{col_w['cache_w']}} {'Cache↓':>{col_w['cache_r']}} {'Cost':>{col_w['cost']}}"
    )

    rows = []
    total_tok = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    total_cost = 0.0

    for model, tok in sorted(result["by_model"].items()):
        cost = compute_cost(tok, model, prices)
        total_cost += cost
        for k in total_tok:
            total_tok[k] += tok[k]
        display_model = model[:col_w["model"]]
        rows.append(
            f"{display_model:<{col_w['model']}} {tok['input']:>{col_w['input']},} "
            f"{tok['output']:>{col_w['output']},} {tok['cache_write']:>{col_w['cache_w']},} "
            f"{tok['cache_read']:>{col_w['cache_r']},} ${cost:>{col_w['cost'] - 1}.4f}"
        )

    total_row = (
        f"{'TOTAL':<{col_w['model']}} {total_tok['input']:>{col_w['input']},} "
        f"{total_tok['output']:>{col_w['output']},} {total_tok['cache_write']:>{col_w['cache_w']},} "
        f"{total_tok['cache_read']:>{col_w['cache_r']},} ${total_cost:>{col_w['cost'] - 1}.4f}"
    )

    footer = f"Prices: {prices_source}  |  As of: {fetched_at}"

    return "\n".join([header, meta, sep, col_header, sep] + rows + [sep, total_row, sep, footer])


def respond(id_, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": id_, "result": result}) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    if "id" not in msg:
        continue

    method = msg.get("method", "")

    if method == "initialize":
        respond(msg["id"], {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "token-harbor", "version": "1.0.0"},
            "capabilities": {"tools": {}},
        })
    elif method == "tools/list":
        respond(msg["id"], {"tools": [TOOL]})
    elif method == "tools/call" and msg.get("params", {}).get("name") == "get_usage":
        try:
            args = (msg.get("params", {}).get("arguments") or {})
            start_date = args.get("start_date")
            end_date = args.get("end_date")
            project_filter = args.get("project") or "all"

            prices, prices_source = fetch_litellm_prices()
            fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            paths = collect_jsonl_paths(project_filter)
            if not paths:
                raise FileNotFoundError(
                    f"No JSONL session files found for project filter: {project_filter!r}"
                )

            result = parse_all_sessions(paths, start_date, end_date)
            text = format_output(result, prices, prices_source, fetched_at, start_date, end_date, project_filter)
            respond(msg["id"], {"content": [{"type": "text", "text": text}]})
        except Exception as e:
            respond(msg["id"], {"isError": True, "content": [{"type": "text", "text": str(e)}]})
    else:
        respond(msg["id"], {})
