#!/usr/bin/env python3
"""Toggle which ANTHROPIC_API_KEY is active in .env."""

from pathlib import Path

env_path = Path(__file__).parent / ".env"
lines = env_path.read_text().splitlines()

toggled = []
label = ""
for i, line in enumerate(lines):
    stripped = line.lstrip()
    if stripped.startswith("# ANTHROPIC_API_KEY="):
        toggled.append(stripped.removeprefix("# "))
        label = lines[i - 1].removeprefix("# ").strip()
    elif stripped.startswith("ANTHROPIC_API_KEY="):
        toggled.append(f"# {stripped}")
    else:
        toggled.append(line)

env_path.write_text("\n".join(toggled) + "\n")

print(f"Switched to: {label}'s API key")
