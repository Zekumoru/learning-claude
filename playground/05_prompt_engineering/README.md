# Prompt engineering

A reusable evaluation platform for the iterative prompt-engineering workflow:

1. Set a goal for what the prompt should accomplish.
2. Write an initial (often naive) prompt.
3. Generate a synthetic test dataset and evaluate the prompt against it.
4. Apply a prompt-engineering technique (few-shot examples, structure, explicit
   constraints, chain-of-thought, etc.).
5. Re-evaluate and compare scores.

Repeat steps 4-5 until the score is good enough. `prompt_evaluator.py` and
`report.py` are the reusable platform — they have no domain logic baked in.
Each concrete exercise (meal plans, or any other course exercise) gets its own
subfolder so generated files never collide between exercises.

## Layout

```
05_prompt_engineering/
├── prompt_evaluator.py   # PromptEvaluator class — the platform
├── report.py              # HTML report generator
├── README.md              # this file
└── meal_plan/              # one exercise: a runnable example
    └── run.py               # just prompt variables + one evaluate_prompt() call
        # dataset.json / results.json / results.html land here too
        # (gitignored — regenerated each run, never committed)
```

## Adding a new exercise

Create a new subfolder next to `meal_plan/`, e.g. `05_prompt_engineering/code_review/`,
with a script that's just variables — write the prompt you're iterating on as a plain
string, and call `evaluate_prompt(...)` to test it. No function definitions, no API
calls to wire up yourself:

```python
from ..prompt_evaluator import PromptEvaluator, evaluate_prompt
from pathlib import Path

evaluator = PromptEvaluator(max_concurrent_tasks=3)

task_description = "What the prompt should accomplish"

prompt_inputs_spec = {"field_name": "description of the field"}

# {field_name} placeholders get filled in from each test case via str.format() —
# the names must match prompt_inputs_spec's keys exactly.
prompt = """
...{field_name}...
"""

extra_criteria = "Anything every response must satisfy, regardless of test case."

if __name__ == "__main__":
    evaluate_prompt(
        evaluator=evaluator,
        prompt=prompt,
        task_description=task_description,
        prompt_inputs_spec=prompt_inputs_spec,
        output_file=str(Path(__file__).parent / "dataset.json"),
        num_cases=3,
        extra_criteria=extra_criteria,
        results_file=str(Path(__file__).parent / "results.json"),
        report_file=str(Path(__file__).parent / "results.html"),
    )
```

Run it with:

```bash
uv run python -m playground.05_prompt_engineering.code_review.run
```

To iterate: edit the `prompt` string and rerun the same command. `evaluate_prompt`
reuses the existing `dataset.json` instead of regenerating it (see below), so
scores stay comparable across edits — that's what makes "did this change actually
help?" a fair question.

(`from ..prompt_evaluator import ...` — two dots — works for any script living
directly in a subfolder of `05_prompt_engineering/`, same as `meal_plan/run.py`.)

## `PromptEvaluator` API

```python
PromptEvaluator(max_concurrent_tasks: int = 3)
```

Bounds how many test cases run concurrently (each case makes two API calls: run the
prompt, then grade it). Start low — 3 is the default — and raise it only if your API
quota allows; too high a value risks 429 rate-limit errors.

### `evaluate_prompt(...)` — the entry point for an exercise

```python
evaluate_prompt(
    evaluator: PromptEvaluator,
    prompt: str,                    # template using {field} placeholders, e.g. "...{height}..."
    task_description: str,          # what the prompt should accomplish
    prompt_inputs_spec: dict[str, str],  # field name -> description, e.g. {"topic": "..."}
    output_file: str,               # dataset path; reused if it already exists
    num_cases: int = 3,
    extra_criteria: str = "",       # requirements applied to every case, on top of its own solution_criteria
    results_file: str = "results.json",
    report_file: str = "results.html",
    pass_threshold: float = 7.0,    # score at/above which a case counts as "passing" in the report
    regenerate_dataset: bool = False,  # force a fresh dataset even if output_file exists
) -> list[EvalResult]
```

Generates `output_file` the first time it's called (skipped on later calls unless
`regenerate_dataset=True` — deliberately, so tweaking `prompt` and rerunning compares
against the *same* test cases instead of a fresh random batch each time), fills
`prompt`'s `{field}` placeholders with each case's generated inputs, runs it through
the model, grades the output with an LLM judge, and writes `results_file` +
`report_file`. Prints the average score and pass rate to stdout.

### Lower-level methods

`evaluate_prompt` is a convenience wrapper around two `PromptEvaluator` methods you
can call directly if you want more control (e.g. a custom `run_prompt_function` that
isn't just `prompt.format(**inputs)` — multi-turn, a system prompt, etc.):

```python
evaluator.generate_dataset(task_description, prompt_inputs_spec, output_file, num_cases=3) -> Dataset
evaluator.run_evaluation(run_prompt_function, dataset_file, extra_criteria="", results_file=..., report_file=..., pass_threshold=7.0) -> list[EvalResult]
```

`run_prompt_function` is any `Callable[[dict[str, str]], str]` — it receives one
test case's `prompt_inputs` dict and returns the model's output.

## The report

`report.py` writes a dark-theme HTML report with:

- **Total Test Cases**, **Average Score**, and **Pass Rate** (percentage of cases
  scoring at or above `pass_threshold`) as summary stats up top.
- One collapsible card per test case, showing its inputs and solution criteria, a
  score badge, and two tabs: **Assessment** (judge's reasoning, strengths,
  weaknesses) and **Output** (the rendered response).

Don't be discouraged by low first-pass scores — a naive baseline prompt scoring
2-5/10 is normal. The weaknesses listed per case are what guide the next
prompt-engineering iteration.
