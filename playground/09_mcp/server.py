from typing import Annotated
from pydantic import Field
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base

# To run the MCP Inspector: uv run mcp dev playground/09_mcp/server.py
mcp = FastMCP("DocumentMCP", log_level="ERROR")

docs: dict[str, str] = {
    "deposition.md": "This deposition covers the testimony of Angela Smith, P.E.",
    "report.pdf": "The report details the state of a 20m condenser tower.",
    "financials.docx": "These financials outline the project's budget and expenditure",
    "outlook.pdf": "This document presents the projected future performance of the",
    "plan.md": "The plan outlines the steps for the project's implementation.",
    "spec.txt": "These specifications define the technical requirements for the equipment",
}


@mcp.tool(
    name="read_doc_contents",
    description="Read the contents of a document and return it as a string.",
)
def read_document(
    doc_id: Annotated[str, Field(description="Id of the document to read.")],
) -> str:
    if doc_id not in docs:
        raise ValueError(f"Doc with id '{doc_id}' not found")
    return docs[doc_id]


@mcp.tool(
    name="edit_document",
    description="Edit a document by replacing a string in the document's content with a new string.",
)
def edit_document(
    doc_id: Annotated[
        str, Field(description="Id of the document that will be edited.")
    ],
    old_str: Annotated[
        str,
        Field(
            description="The text to replace. Must match exactly, including whitespace."
        ),
    ],
    new_str: Annotated[
        str, Field(description="The new text to insert in place of the old text.")
    ],
) -> None:
    if doc_id not in docs:
        raise ValueError(f"Doc with id '{doc_id}' not found")

    content = docs[doc_id]
    match content.count(old_str):
        case 0:
            raise ValueError(f"Text to replace not found in doc '{doc_id}'")
        case 1:
            docs[doc_id] = content.replace(old_str, new_str)
        case _:
            raise ValueError(
                f"Text to replace is not unique in doc '{doc_id}'; it appears "
                "multiple times. Provide more surrounding context."
            )


@mcp.resource("docs://documents", mime_type="application/json")
def list_docs() -> list[str]:
    return list(docs.keys())


@mcp.resource(
    "docs://documents/{doc_id}",
    mime_type="text/plain",
)
def fetch_doc(doc_id: str) -> str:
    if doc_id not in docs:
        raise ValueError(f"Doc with id '{doc_id}' not found")
    return docs[doc_id]


@mcp.prompt(
    name="format",
    description="Rewrites the contents of the document in Markdown format",
)
def format_document(
    doc_id: Annotated[str, Field(description="Id of the document to format")],
) -> list[base.Message]:
    prompt = f"""\
Your goal is to reformat the document with id '{doc_id}' using Markdown syntax.

Add headers, bullet points, tables, code blocks, and any other Markdown formatting \
that makes the content clearer and well-structured.

Use the `edit_document` tool to apply your changes, make as many calls as needed. \
Edit the document directly; do not print the reformatted text in your reply.
"""
    messages: list[base.Message] = [base.UserMessage(prompt)]
    return messages


if __name__ == "__main__":
    mcp.run(transport="stdio")
