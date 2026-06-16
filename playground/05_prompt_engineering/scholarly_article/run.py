from ..prompt_evaluator import PromptEvaluator, evaluate_prompt
from pathlib import Path

evaluator = PromptEvaluator(max_concurrent_tasks=3)

task_description = """
Extract topics out of a passage of text from a scholarly article into a JSON array of strings.
"""

prompt_inputs_spec = {
    "content": "One paragraph of text from a scholarly journal written in English."
}

prompt = """
Extract key topics mentioned from a passage from a scholarly journal into a JSON array of strings.

<article>
{content}
</article>

Follow these steps:
1. Closely examine the provided text.
2. Identify each topic mentioned.
3. Add each topic to a JSON array.
4. Respond with the JSON array directly without code blocks. Do not provide any other text or commentary.
"""

extra_criteria = """
- Contains a JSON array of strings, containing each topic mentioned in the article.
- The strings should contain only a topic without any extra commentary.
- Response should contain the JSON array and nothing else.
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
