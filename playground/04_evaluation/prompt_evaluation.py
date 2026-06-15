from anthropic.types import MessageParam
from ..common.chat import chat, add_user_message
from .generate_dataset import TestCase
from .report import write_html_report
from pydantic import BaseModel, TypeAdapter
from pathlib import Path
import json


class ModelGrade(BaseModel):
    strengths: list[str]
    weaknesses: list[str]
    reasoning: str
    score: float


class EvalResult(BaseModel):
    output: str
    test_case: TestCase
    reasoning: str
    score: float


def run_prompt(test_case: TestCase) -> str:
    """Merges the prompt and test case input, then returns the result"""
    prompt = f"""
Please solve the following task:

{test_case.task}
"""

    messages: list[MessageParam] = []
    add_user_message(messages, prompt)
    output = chat(messages)
    return output


def grade_by_model(test_case: TestCase, output) -> ModelGrade:
    eval_prompt = f"""
You are an expert code reviewer. Evaluate this AI-generated solution.

Task:
<task>
{test_case.task}
</task>

Solution:
<solution>
{output}
</solution>

Provide your evaluation as a structured JSON object with:
- "strengths": An array of 1-3 key strengths.
- "weaknesses": An array of 1-3 key areas for improvement.
- "reasoning": A concise explanation of your assessment.
- "score": A number between 0-10. Can have up to two fixed decimal numbers.
"""

    messages: list[MessageParam] = []
    add_user_message(messages, eval_prompt)
    return chat(messages, output_format=ModelGrade)


def run_test_case(test_case: TestCase) -> EvalResult:
    """Calls run_prompt, then grades the result"""
    output = run_prompt(test_case)

    # Grade the output
    model_grade = grade_by_model(test_case, output)
    score = model_grade.score
    reasoning = model_grade.reasoning

    return EvalResult(
        output=output, test_case=test_case, score=score, reasoning=reasoning
    )


def run_eval(dataset: list[TestCase]) -> list[EvalResult]:
    """Loads the dataset and calls run_test_case with each case"""
    results = []

    for test_case in dataset:
        result = run_test_case(test_case)
        results.append(result)

    return results


dataset_path = Path(__file__).parent / "dataset.json"
raw = json.loads(dataset_path.read_text())
dataset = TypeAdapter(list[TestCase]).validate_python(raw)

results = run_eval(dataset)
write_html_report(results)
