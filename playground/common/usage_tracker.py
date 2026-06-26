import sqlite3
from pathlib import Path
from anthropic.types import Message
from .pricing import PRICING_PER_MILLION
from .renderer import color, YELLOW

DB_PATH = Path(__file__).parent / "usage.db"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
                cache_read_tokens INTEGER NOT NULL DEFAULT 0,
                cost REAL NOT NULL
            ) 
        """)


def on_usage(message: Message) -> None:
    usage = message.usage
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens
    cache_creation = usage.cache_creation_input_tokens or 0
    cache_read = usage.cache_read_input_tokens or 0

    pricing = PRICING_PER_MILLION.get(message.model)
    if pricing is None:
        return

    rate = pricing["input"] / 1_000_000
    cost = (
        input_tokens * rate
        + output_tokens * pricing["output"] / 1_000_000
        + cache_creation * rate * 1.25
        + cache_read * rate * 0.1
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO usage (model, input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens, cost) VALUES (?, ?, ?, ?, ?, ?)",
            (
                message.model,
                input_tokens,
                output_tokens,
                cache_creation,
                cache_read,
                cost,
            ),
        )
        total: float = conn.execute("SELECT SUM(cost) FROM usage").fetchone()[0]

    print(color(f"[All-time: ${total:.2f}]", YELLOW))
