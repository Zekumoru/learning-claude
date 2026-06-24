import base64
from pathlib import Path
from typing import Literal, cast

from anthropic.types import ToolParam, ImageBlockParam, DocumentBlockParam

ImageMediaType = Literal["image/png", "image/jpeg", "image/gif", "image/webp"]
DocumentMediaType = Literal["application/pdf"]

SUPPORTED_IMAGE_EXTENSIONS: dict[str, ImageMediaType] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

SUPPORTED_DOCUMENT_EXTENSIONS: dict[str, DocumentMediaType] = {
    ".pdf": "application/pdf",
}

read_media_schema: ToolParam = {
    "name": "read_media",
    "description": (
        "Read an image or PDF file from the local filesystem."
        "Use this tool when the user asks you to look at, analyze, or describe an image or document."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the image file or PDF file.",
            }
        },
        "required": ["path"],
    },
}

MediaBlock = ImageBlockParam | DocumentBlockParam
ReadMediaResult = list[MediaBlock] | dict[str, str]


def _error(message: str) -> dict[str, str]:
    return {"error": message}


def _resolve_safe_file(path: str, root: Path) -> Path | dict[str, str]:
    root = root.resolve()
    file_path = (root / Path(path)).resolve()

    if not file_path.is_relative_to(root):
        return _error(f"Access denied. Path must be within {root}.")

    if not file_path.is_file():
        return _error(f"File not found: {path}")

    return file_path


def _image_block(media_type: ImageMediaType, data: str) -> ImageBlockParam:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": data,
        },
    }


def _document_block(
    media_type: DocumentMediaType, title: str, data: str
) -> DocumentBlockParam:
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": data,
        },
        "title": title,
        "citations": {"enabled": True},
    }


def _supported_extensions_message() -> str:
    supported = sorted(
        [*SUPPORTED_IMAGE_EXTENSIONS.keys(), *SUPPORTED_DOCUMENT_EXTENSIONS.keys()]
    )

    return ", ".join(supported)


def _build_media_block(file_path: Path, data: str) -> MediaBlock | dict[str, str]:
    suffix = file_path.suffix.lower()

    if suffix in SUPPORTED_IMAGE_EXTENSIONS:
        return _image_block(SUPPORTED_IMAGE_EXTENSIONS[suffix], data)

    if suffix in SUPPORTED_DOCUMENT_EXTENSIONS:
        return _document_block(
            SUPPORTED_DOCUMENT_EXTENSIONS[suffix], file_path.name, data
        )

    return _error(
        f"Unsupported media format '{suffix}'. "
        f"Supported: {_supported_extensions_message()}"
    )


def read_media(path: str, root: Path | None = None) -> ReadMediaResult:
    root = Path.cwd() if root is None else root

    file_path = _resolve_safe_file(path, root)

    if isinstance(file_path, dict):
        return file_path

    data = base64.standard_b64encode(file_path.read_bytes()).decode("utf-8")
    block = _build_media_block(file_path, data)

    if "error" in block:
        return cast(dict[str, str], block)

    return [cast(MediaBlock, block)]
