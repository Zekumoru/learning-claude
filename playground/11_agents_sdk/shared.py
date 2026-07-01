from claude_agent_sdk import ResultMessage

from ..common.usage_tracker import record_usage, get_balance


def record_result(model: str, message: ResultMessage) -> str:
    """Record a run in the ledger; return a formatted all-time/balance line"""
    stats = message.usage or {}
    all_time = record_usage(
        model=model,
        input_tokens=int(stats.get("input_tokens", 0)),
        output_tokens=int(stats.get("output_tokens", 0)),
        cache_creation_tokens=int(stats.get("cache_creation_input_tokens", 0)),
        cache_read_tokens=int(stats.get("cache_read_input_tokens", 0)),
        cost=message.total_cost_usd or 0.0,
    )
    balance = get_balance()
    tail = f" (balance: ${balance:.2f})" if balance is not None else ""
    return f"All-time: ${all_time:.2f}{tail}"
