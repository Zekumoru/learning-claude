from ..prompt_evaluator import PromptEvaluator, evaluate_prompt
from pathlib import Path

evaluator = PromptEvaluator(max_concurrent_tasks=3)

task_description = """
Categorize sentiments of a tweet: either it's a positive tweet or a negative tweet. Take care of sarcasm.
"""

prompt_inputs_spec = {"tweet": "The tweet to evaluate sentiment from."}

prompt = """
Categorize the sentiment of the below tweet. Watch for sarcasm — superficially positive words can signal a negative sentiment when used sarcastically.

<input_tweet>
{tweet}
</input_tweet>

Here are examples of the ONLY acceptable responses:
<sample_input>
Great game tonight!
</sample_input>
<ideal_output>
Positive
</ideal_output>

<sample_input>
Oh yeah, I really needed a flight delay tonight! Excellent!
</sample_input>
<ideal_output>
Negative
</ideal_output>

Respond with ONLY the single word "Positive" or "Negative". Do not include any explanation, reasoning, punctuation, or additional text — just the single classification word.
"""

extra_criteria = """
The response should only be either "Positive" or "Negative".
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
