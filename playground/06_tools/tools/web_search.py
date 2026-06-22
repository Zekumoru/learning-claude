from anthropic.types import WebSearchTool20260209Param

web_search_schema = WebSearchTool20260209Param(
    type="web_search_20260209",
    name="web_search",
    max_uses=3,
)
