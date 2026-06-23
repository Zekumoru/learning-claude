from anthropic.types import ToolParam
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import uuid

save_article_schema = ToolParam(
    {
        "name": "save_article",
        "description": "Saves a journal article",
        "eager_input_streaming": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "abstract": {
                    "type": "string",
                    "description": "Abstract of the article. One short sentence max",
                },
                "meta": {
                    "type": "object",
                    "properties": {
                        "word_count": {
                            "type": "integer",
                            "description": "Word count",
                        },
                        "review": {
                            "type": "string",
                            "description": "Eight sentence max review of the paper",
                        },
                    },
                    "required": ["word_count", "review"],
                },
                "content": {"type": "string", "description": "Content of the article"},
            },
            "required": ["abstract", "meta"],
        },
    }
)


def save_article(
    abstract: str,
    meta: dict[str, Any],
    content: str,
    articles_dir: str = "articles",
) -> dict[str, Any]:
    if not abstract.strip():
        raise ValueError("abstract cannot be empty")

    word_count = meta.get("word_count")
    review = meta.get("review")

    if not isinstance(word_count, int):
        raise TypeError("meta.word_count must be an integer")

    if word_count < 0:
        raise ValueError("meta.word_count cannot be negative")

    if not isinstance(review, str):
        raise TypeError("meta.review must be a string")

    if not review.strip():
        raise ValueError("meta.review cannot be empty")

    if not content.strip():
        raise ValueError("content cannot be empty")

    article = {
        "abstract": abstract,
        "meta": {
            "word_count": word_count,
            "review": review,
        },
        "content": content,
    }

    output_dir = Path(articles_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    article_id = uuid.uuid4().hex[:8]
    filename = f"article_{timestamp}_{article_id}.json"

    output_path = output_dir / filename

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(article, file, indent=2, ensure_ascii=False)

    return {
        "status": "saved",
        "path": str(output_path),
        "article": article,
    }
