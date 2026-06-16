from ..prompt_evaluator import PromptEvaluator, evaluate_prompt
from pathlib import Path

evaluator = PromptEvaluator(max_concurrent_tasks=3)

task_description = "Write a compact, concise 1 day meal plan for a single athlete"

prompt_inputs_spec = {
    "height": "Athlete's height in cm",
    "weight": "Athlete's weight in kg",
    "goal": "Goal of the athlete",
    "restrictions": "Dietary restrictions of the athlete",
}

prompt = """
What should this person eat?

- Height: {height}
- Weight: {weight}
- Goal: {goal}
- Dietary restrictions: {restrictions}
"""

extra_criteria = """
The output should include:
- Daily caloric total
- Macronutrient breakdown
- Meals with exact foods, portions, and timing
"""

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
