import base64
from pathlib import Path
from anthropic.types import ToolParam, ImageBlockParam
from typing import Literal

ImageMediaType = Literal["image/png", "image/jpeg", "image/gif", "image/webp"]

SUPPORTED_EXTENSIONS: dict[str, ImageMediaType] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

read_image_schema: ToolParam = {
    "name": "read_image",
    "description": (
        "Read an image file from the local filesystem."
        "Use this tool when the user asks you to look at, analyze, or describe an image."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the image file.",
            }
        },
        "required": ["path"],
    },
}


def read_image(
    path: str, root: Path = Path.cwd()
) -> list[ImageBlockParam] | dict[str, str]:
    file_path = (root / Path(path)).resolve()

    if not file_path.is_relative_to(root.resolve()):
        return {"error": f"Access denied. Path must be within {root}."}

    if not file_path.is_file():
        return {"error": f"File not found: {path}"}

    suffix = file_path.suffix.lower()
    media_type = SUPPORTED_EXTENSIONS.get(suffix)

    if media_type is None:
        supported = ", ".join(SUPPORTED_EXTENSIONS.keys())
        return {"error": f"Unsupported image format '{suffix}'. Supported: {supported}"}

    data = base64.standard_b64encode(file_path.read_bytes()).decode("utf-8")

    return [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        }
    ]
