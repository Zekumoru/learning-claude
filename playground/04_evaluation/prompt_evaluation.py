from anthropic.types import MessageParam
from ..common.chat import chat, add_user_message
from ..common.validation import validate_json, validate_python, validate_regex
from .generate_dataset import TestCase
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
    model_grade: ModelGrade
    syntax_score: float
    total_score: float


def run_prompt(test_case: TestCase) -> str:
    """Merges the prompt and test case input, then returns the result"""
    prompt = f"""
Please solve the following task:

{test_case.task}

* Respond only with {test_case.format}.
* Do not add any comments or commentary or explanation.
"""

    messages: list[MessageParam] = []
    add_user_message(messages, prompt)
    output = chat(messages)
    return output


def grade_by_model(test_case: TestCase, output: str) -> ModelGrade:
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


def grade_by_syntax(test_case: TestCase, output: str) -> float:
    match test_case.format:
        case "json":
            return validate_json(output)
        case "python":
            return validate_python(output)
        case "regex":
            return validate_regex(output)


def run_test_case(test_case: TestCase) -> EvalResult:
    """Calls run_prompt, then grades the result"""
    output = run_prompt(test_case)

    # Grade the output
    model_grade = grade_by_model(test_case, output)
    syntax_score = grade_by_syntax(test_case, output)
    total_score = (model_grade.score + syntax_score) / 2

    return EvalResult(
        output=output,
        test_case=test_case,
        model_grade=model_grade,
        syntax_score=syntax_score,
        total_score=total_score,
    )


def run_eval(dataset: list[TestCase]) -> list[EvalResult]:
    """Loads the dataset and calls run_test_case with each case"""
    results = []

    for test_case in dataset:
        result = run_test_case(test_case)
        results.append(result)

    return results


if __name__ == "__main__":
    from .report import write_html_report

    print("Evaluating dataset")
    dataset_path = Path(__file__).parent / "dataset.json"
    raw = json.loads(dataset_path.read_text())
    dataset = TypeAdapter(list[TestCase]).validate_python(raw)

    results = run_eval(dataset)

    results_path = Path(__file__).parent / "results.json"
    results_path.write_text(json.dumps([r.model_dump() for r in results], indent=2))
    print(f"Results written to {results_path}")

    print("Generating HTML report...")
    write_html_report(results)
