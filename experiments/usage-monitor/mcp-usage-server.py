#!/usr/bin/env python3
import sys
import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone

def _find_project_root() -> Path:
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / "CLAUDE.md").exists():
            return p
        p = p.parent
    return Path(__file__).parent

TMUX_CAPTURE_FILE = _find_project_root() / ".claude" / "cc-usage.txt"
TMUX_CAPTURE_MAX_AGE_SECS = 60

TOOL = {
    "name": "get_usage",
    "description": "Returns token usage statistics for the current Claude Code session.",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}


def find_session_start():
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session_id:
        return session_id, None
    sessions_dir = Path.home() / ".claude" / "sessions"
    for f in sessions_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("sessionId") == session_id:
                started_at_ms = data.get("startedAt")
                if started_at_ms:
                    cutoff = datetime.fromtimestamp(started_at_ms / 1000, tz=timezone.utc)
                    return session_id, cutoff.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            pass
    return session_id, None


def find_jsonl(session_id):
    cwd = os.environ.get("PWD", os.getcwd())
    slug = cwd.replace("/", "-")
    project_dir = Path.home() / ".claude" / "projects" / slug
    if session_id:
        p = project_dir / f"{session_id}.jsonl"
        if p.exists():
            return p
    files = sorted(project_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No session JSONL found in {project_dir}")
    return files[0]


def compute_usage(path, cutoff):
    lines = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    assistant_uuids = {obj["uuid"] for obj in lines if obj.get("type") == "assistant" and "uuid" in obj}

    totals = {"input_tokens": 0, "output_tokens": 0,
              "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    turns = 0
    for obj in lines:
        if obj.get("type") != "assistant":
            continue
        if cutoff and obj.get("timestamp", "") < cutoff:
            continue
        # Skip streaming updates — their parent is another assistant message
        if obj.get("parentUuid") in assistant_uuids:
            continue
        u = (obj.get("message") or {}).get("usage") or {}
        turns += 1
        for k in totals:
            totals[k] += u.get(k, 0)
    totals["total_tokens"] = sum(totals.values())
    totals["turns"] = turns
    return totals


def format_usage(u):
    sep = "─" * 38
    return "\n".join([
        f"Session Token Usage ({u['turns']} turns)",
        sep,
        f"Input tokens:              {u['input_tokens']:,}",
        f"Output tokens:             {u['output_tokens']:,}",
        f"Cache creation (write):    {u['cache_creation_input_tokens']:,}",
        f"Cache read:                {u['cache_read_input_tokens']:,}",
        sep,
        f"Total tokens:              {u['total_tokens']:,}",
    ])


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
            "serverInfo": {"name": "usage-server", "version": "1.0.0"},
            "capabilities": {"tools": {}},
        })
    elif method == "tools/list":
        respond(msg["id"], {"tools": [TOOL]})
    elif method == "tools/call" and msg.get("params", {}).get("name") == "get_usage":
        try:
            # Prefer tmux-captured /usage output when fresh
            if (TMUX_CAPTURE_FILE.exists() and
                    time.time() - TMUX_CAPTURE_FILE.stat().st_mtime < TMUX_CAPTURE_MAX_AGE_SECS):
                text = TMUX_CAPTURE_FILE.read_text().strip()
                if text:
                    respond(msg["id"], {"content": [{"type": "text", "text": text}]})
                    continue
            # Fallback: compute from JSONL
            session_id, cutoff = find_session_start()
            path = find_jsonl(session_id)
            usage = compute_usage(path, cutoff)
            respond(msg["id"], {"content": [{"type": "text", "text": format_usage(usage)}]})
        except Exception as e:
            respond(msg["id"], {"isError": True, "content": [{"type": "text", "text": str(e)}]})
    else:
        respond(msg["id"], {})
