from claude_agent_sdk import ResultMessage

from .usage_tracker import record_usage


def record_result(model: str, message: ResultMessage) -> str:
    """Record an Agent SDK run (subscription-covered) and return a per-run breakdown:
    token counts, this run's estimated cost, and the all-time subscription total."""
    stats = message.usage or {}
    input_tokens = int(stats.get("input_tokens", 0))
    output_tokens = int(stats.get("output_tokens", 0))
    cache_write_tokens = int(stats.get("cache_creation_input_tokens", 0))
    cache_read_tokens = int(stats.get("cache_read_input_tokens", 0))
    cost = message.total_cost_usd or 0.0

    all_time = record_usage(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_write_tokens,
        cache_read_tokens=cache_read_tokens,
        cost=cost,
        billing="subscription",
    )

    return (
        f"tokens: in={input_tokens} out={output_tokens} "
        f"cache_write={cache_write_tokens} cache_read={cache_read_tokens} | "
        f"cost≈${cost:.4f} | all-time (subscription): ${all_time:.4f}"
    )
