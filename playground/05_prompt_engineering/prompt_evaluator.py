from anthropic.types import MessageParam
from ..common.chat import chat, add_user_message, text_from_message
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from pathlib import Path
import json


# dict[str, str] fields don't survive Anthropic's structured-output schema
# transform (it forces additionalProperties: False on object-typed fields), so
# free-form prompt_inputs are generated in this list-of-name/value shape and
# converted to a plain dict right after parsing.
class _InputField(BaseModel):
    name: str
    value: str


class _GeneratedCase(BaseModel):
    prompt_inputs: list[_InputField]
    solution_criteria: str


class _GeneratedDataset(BaseModel):
    cases: list[_GeneratedCase]


class TestCase(BaseModel):
    prompt_inputs: dict[str, str]
    solution_criteria: str


class Dataset(BaseModel):
    task_description: str
    prompt_inputs_spec: dict[str, str]
    cases: list[TestCase]


class ModelGrade(BaseModel):
    strengths: list[str]
    weaknesses: list[str]
    reasoning: str
    score: float


class EvalResult(BaseModel):
    output: str
    test_case: TestCase
    model_grade: ModelGrade


DEFAULT_PASS_THRESHOLD = 7.0


class PromptEvaluator:
    def __init__(self, max_concurrent_tasks: int = 3) -> None:
        self.max_concurrent_tasks = max_concurrent_tasks

    def generate_dataset(
        self,
        task_description: str,
        prompt_inputs_spec: dict[str, str],
        output_file: str,
        num_cases: int = 3,
    ) -> Dataset:
        """Generates a synthetic dataset of test cases and writes it to output_file."""
        spec_lines = "\n".join(
            f"- {name}: {description}"
            for name, description in prompt_inputs_spec.items()
        )

        prompt = f"""
Generate an evaluation dataset for testing a prompt. The prompt's task is:

{task_description}

Each test case must provide realistic, varied input values for these fields:
{spec_lines}

Example output:
```json
[
    {{
        "prompt_inputs": [
            {{"name": "height", "value": "180 cm"}},
            {{"name": "weight", "value": "75 kg"}}
        ],
        "solution_criteria": "Solution criteria for this specific case"
    }},
    ...additional
]
```

* Invent realistic, plausible values for every field listed above for each case.
* Vary the cases meaningfully so the dataset tests a range of scenarios.
* Each case's "prompt_inputs" array must contain exactly one entry per field listed above, using the exact field name as "name".
* "solution_criteria" must describe what a correct, high-quality output looks like for this specific case.

Please generate {num_cases} objects.
"""

        messages: list[MessageParam] = []
        add_user_message(messages, prompt)
        generated = chat(messages, output_format=_GeneratedDataset)

        expected_keys = set(prompt_inputs_spec.keys())
        cases: list[TestCase] = []
        for case in generated.cases:
            prompt_inputs = {field.name: field.value for field in case.prompt_inputs}
            if set(prompt_inputs.keys()) != expected_keys:
                raise ValueError(
                    f"Generated case has keys {set(prompt_inputs.keys())}, "
                    f"expected {expected_keys}"
                )
            cases.append(
                TestCase(
                    prompt_inputs=prompt_inputs,
                    solution_criteria=case.solution_criteria,
                )
            )

        dataset = Dataset(
            task_description=task_description,
            prompt_inputs_spec=prompt_inputs_spec,
            cases=cases,
        )

        Path(output_file).write_text(dataset.model_dump_json(indent=2))
        return dataset

    def run_evaluation(
        self,
        run_prompt_function: Callable[[dict[str, str]], str],
        dataset_file: str,
        extra_criteria: str = "",
        results_file: str = "results.json",
        report_file: str = "results.html",
        pass_threshold: float = DEFAULT_PASS_THRESHOLD,
    ) -> list[EvalResult]:
        """Runs run_prompt_function against every case in dataset_file, grades each
        output with an LLM judge, and writes results_file and report_file."""
        dataset = Dataset.model_validate_json(Path(dataset_file).read_text())

        with ThreadPoolExecutor(max_workers=self.max_concurrent_tasks) as executor:
            futures = [
                executor.submit(
                    self._run_test_case,
                    test_case,
                    run_prompt_function,
                    extra_criteria,
                )
                for test_case in dataset.cases
            ]
            results = [future.result() for future in futures]

        Path(results_file).write_text(
            json.dumps([result.model_dump() for result in results], indent=2)
        )

        from .report import write_html_report

        write_html_report(
            results, dataset.task_description, report_file, pass_threshold
        )

        if results:
            average_score = sum(r.model_grade.score for r in results) / len(results)
            passed = sum(1 for r in results if r.model_grade.score >= pass_threshold)
            pass_rate = passed / len(results) * 100
            print(f"Average score: {average_score:.1f} / 10")
            print(
                f"Pass rate (>= {pass_threshold:g}): {pass_rate:.1f}% ({passed}/{len(results)})"
            )

        return results

    def _run_test_case(
        self,
        test_case: TestCase,
        run_prompt_function: Callable[[dict[str, str]], str],
        extra_criteria: str,
    ) -> EvalResult:
        output = run_prompt_function(test_case.prompt_inputs)
        model_grade = self._grade_by_model(test_case, output, extra_criteria)
        return EvalResult(output=output, test_case=test_case, model_grade=model_grade)

    def _grade_by_model(
        self, test_case: TestCase, output: str, extra_criteria: str
    ) -> ModelGrade:
        inputs_block = "\n".join(
            f"- {key}: {value}" for key, value in test_case.prompt_inputs.items()
        )

        criteria_block = test_case.solution_criteria
        if extra_criteria:
            criteria_block += (
                "\n\nAdditionally, every response must satisfy these requirements:\n"
                f"{extra_criteria}"
            )

        eval_prompt = f"""
You are an expert evaluator. Evaluate this AI-generated response.

Do not be cheesy with the scoring, if the output perfectly abode to the criteria, it should be 10.
Any other suggestions or negative comments must just go to the negatives explaining why, but it shouldn't mean that the solver failed. 

Inputs given to the prompt:
<inputs>
{inputs_block}
</inputs>

Response:
<response>
{output}
</response>

Evaluation criteria:
<criteria>
{criteria_block}
</criteria>

Provide your evaluation as a structured JSON object with:
- "strengths": An array of 1-3 key strengths.
- "weaknesses": An array of 1-3 key areas for improvement.
- "reasoning": A concise explanation of your assessment.
- "score": A number between 0-10. Can have up to two fixed decimal numbers.
"""

        messages: list[MessageParam] = []
        add_user_message(messages, eval_prompt)
        return chat(messages, output_format=ModelGrade)


def evaluate_prompt(
    evaluator: PromptEvaluator,
    prompt: str,
    task_description: str,
    prompt_inputs_spec: dict[str, str],
    output_file: str,
    num_cases: int = 3,
    extra_criteria: str = "",
    results_file: str = "results.json",
    report_file: str = "results.html",
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
    regenerate_dataset: bool = False,
) -> list[EvalResult]:
    """Generates output_file if it doesn't exist yet (or regenerate_dataset=True),
    then evaluates `prompt` against every case in it. `prompt` is a template using
    {field} placeholders matching prompt_inputs_spec's keys, e.g. "...{height}...".

    Reuses an existing dataset by default — only the prompt text needs to change
    between calls, so successive runs stay comparable against the same test cases.
    """
    if regenerate_dataset or not Path(output_file).exists():
        evaluator.generate_dataset(
            task_description=task_description,
            prompt_inputs_spec=prompt_inputs_spec,
            output_file=output_file,
            num_cases=num_cases,
        )

    def run_prompt_function(prompt_inputs: dict[str, str]) -> str:
        messages: list[MessageParam] = []
        add_user_message(messages, prompt.format(**prompt_inputs))
        return text_from_message(chat(messages))

    return evaluator.run_evaluation(
        run_prompt_function=run_prompt_function,
        dataset_file=output_file,
        extra_criteria=extra_criteria,
        results_file=results_file,
        report_file=report_file,
        pass_threshold=pass_threshold,
    )
