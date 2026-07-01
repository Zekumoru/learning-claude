import sqlite3
from pathlib import Path
from .pricing import pricing_for
from .renderer import color, YELLOW
from .types import AnyMessage

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

        # CHECK (id = 1) forces single row
        conn.execute("""
                CREATE TABLE IF NOT EXISTS balance (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    amount REAL NOT NULL
                )
        """)


def set_balance(amount: float) -> None:
    """Snapshot the money you have left right now."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO balance (id, amount) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET amount = excluded.amount",
            (amount,),
        )


def get_balance() -> float | None:
    """None means you haven't set a balance yet."""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT amount FROM balance WHERE id = 1").fetchone()
    return row[0] if row else None


def total_spent() -> float:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT COALESCE(SUM(cost), 0) FROM usage").fetchone()[0]


def record_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int,
    cache_read_tokens: int,
    cost: float,
) -> float:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO usage (model, input_tokens, output_tokens, "
            "cache_creation_tokens, cache_read_tokens, cost) VALUES (?, ?, ?, ?, ?, ?)",
            (
                model,
                input_tokens,
                output_tokens,
                cache_creation_tokens,
                cache_read_tokens,
                cost,
            ),
        )
        conn.execute("UPDATE balance SET amount = amount - ? WHERE id = 1", (cost,))
        total: float = conn.execute("SELECT SUM(cost) FROM usage").fetchone()[0]
    return total


def on_usage(message: AnyMessage) -> None:
    usage = message.usage
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens
    cache_creation = usage.cache_creation_input_tokens or 0
    cache_read = usage.cache_read_input_tokens or 0

    pricing = pricing_for(message.model)
    if pricing is None:
        return

    rate = pricing["input"] / 1_000_000
    cost = (
        input_tokens * rate
        + output_tokens * pricing["output"] / 1_000_000
        + cache_creation * rate * 1.25
        + cache_read * rate * 0.1
    )

    total = record_usage(
        message.model, input_tokens, output_tokens, cache_creation, cache_read, cost
    )

    print(color(f"[All-time: ${total:.2f}]", YELLOW))
