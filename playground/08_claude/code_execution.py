import csv
import random
from pathlib import Path
from anthropic.types.beta import (
    BetaMessage,
    BetaTextBlock,
    BetaServerToolUseBlock,
    BetaBashCodeExecutionToolResultBlock,
    BetaBashCodeExecutionResultBlock,
    BetaBashCodeExecutionToolResultError,
    BetaCodeExecutionTool20260120Param,
    BetaContainerUploadBlockParam,
)
from ..common.chat import client
from ..common.defaults import model, max_tokens
from ..common.renderer import color, CYAN, GREEN, RED
from typing import Literal

ASSETS = Path(__file__).parent / "assets"
ROWS = 10  # Number of rows to generate for dummy data
CSV_PATH = ASSETS / "streaming.csv"

Tier = Literal["free", "basic", "premium"]


def generate_csv(path: Path = CSV_PATH, rows: int = ROWS) -> Path:
    tiers: list[Tier] = ["free", "basic", "premium"]

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "user_id",
                "subscription_tier",
                "monthly_views",
                "months_subscribed",
                "churned",
            ]
        )

        for i in range(1, rows + 1):
            tier = random.choice(tiers)
            views = random.randint(0, 50 if tier == "free" else 200)
            months = random.randint(1, 24)
            churn_prob = 0.6 if tier == "free" else 0.3 if tier == "basic" else 0.1
            churn_prob += 0.2 if views < 10 else 0
            churn_prob += 0.1 if months < 3 else 0
            writer.writerow(
                [f"U{i:03d}", tier, views, months, int(random.random() < churn_prob)]
            )

        print(color(f"Generated: {path.name}", CYAN))

        return path


# Files API: Uploading a file
csv_path = generate_csv() if not CSV_PATH.exists() else CSV_PATH

with open(csv_path, "rb") as f:
    file_object = client.beta.files.upload(file=(csv_path.name, f, "text/csv"))

print(color(f"Uploaded: {file_object.id}", CYAN))

# Code Execution: Referencing a file and using it in the container.
tool: BetaCodeExecutionTool20260120Param = {
    "type": "code_execution_20260120",
    "name": "code_execution",
}

upload_block: BetaContainerUploadBlockParam = {
    "type": "container_upload",
    "file_id": file_object.id,
}

response: BetaMessage = client.beta.messages.create(
    model=model,
    max_tokens=max_tokens,
    betas=["files-api-2025-04-14"],
    tools=[tool],
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Analyze this CSV data to identify the major drivers of churn. Include only one plot saved as a PNG.",
                },
                upload_block,
            ],
        }
    ],
)

# Code Execution: Response parsing
file_ids: list[str] = []


def _handle_tool_result_block(block: BetaBashCodeExecutionToolResultBlock) -> None:
    match block.content:
        case BetaBashCodeExecutionResultBlock():
            if block.content.stdout:
                print(color(block.content.stdout, GREEN))
            if block.content.stderr:
                print(color(block.content.stderr, RED))
            for output in block.content.content:
                file_ids.append(output.file_id)
        case BetaBashCodeExecutionToolResultError():
            print(color(f"Error: {block.content.error_code}", RED))


for block in response.content:
    match block:
        case BetaTextBlock():
            print(block.text)
        case BetaServerToolUseBlock():
            cmd = block.input.get("command", "")
            if isinstance(cmd, str):
                print(color(f"\n[{block.name}] {cmd[:120]}", CYAN))
        case BetaBashCodeExecutionToolResultBlock():
            _handle_tool_result_block(block)

for file_id in file_ids:
    metadata = client.beta.files.retrieve_metadata(file_id)
    content = client.beta.files.download(file_id)
    output_path = ASSETS / metadata.filename
    content.write_to_file(str(output_path))
    print(color(f"\nDownloaded: {output_path.name}", GREEN))
