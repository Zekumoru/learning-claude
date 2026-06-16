from .prompt_evaluator import EvalResult, DEFAULT_PASS_THRESHOLD
from pathlib import Path
import html as html_lib
import re


def _pascal_case(key: str) -> str:
    return "".join(word[:1].upper() + word[1:] for word in re.split(r"[_\s]+", key) if word)


def _input_table_html(inputs: dict[str, str]) -> str:
    rows = "".join(
        f'<tr><td class="input-key">{html_lib.escape(_pascal_case(key))}</td>'
        f'<td class="input-value">{html_lib.escape(value)}</td></tr>'
        for key, value in inputs.items()
    )
    return f'<div class="input-table-wrap"><table class="input-table">{rows}</table></div>'


def write_html_report(
    results: list[EvalResult],
    task_description: str,
    output_path: str | Path,
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
) -> None:
    overall = (
        sum(r.model_grade.score for r in results) / len(results) if results else 0
    )
    max_score = 10
    passed = sum(1 for r in results if r.model_grade.score >= pass_threshold)
    pass_rate = passed / len(results) * 100 if results else 0

    def score_class(score: float) -> str:
        if score >= 8:
            return "score-high"
        if score >= 5:
            return "score-mid"
        return "score-low"

    def rate_class(rate: float) -> str:
        if rate >= 70:
            return "rate-high"
        if rate >= 40:
            return "rate-mid"
        return "rate-low"

    def li_items(items: list[str]) -> str:
        return "".join(f"<li>{html_lib.escape(item)}</li>" for item in items)

    cards_html = ""
    for i, result in enumerate(results, 1):
        grade = result.model_grade
        score = grade.score
        sc = score_class(score)
        cards_html += f"""  <div class="card">
    <div class="card-toggle">
      <div class="toggle-top">
        <span class="task-num">Task {i}</span>
        <div class="toggle-right">
          <span class="score-badge {sc}">{score:.1f}&thinsp;/&thinsp;{max_score}</span>
          <span class="chevron">&#x203A;</span>
        </div>
      </div>
      <div class="card-section">
        <h4>Description</h4>
        <p>{html_lib.escape(task_description)}</p>
      </div>
      <div class="card-section">
        <h4>Inputs</h4>
        {_input_table_html(result.test_case.prompt_inputs)}
      </div>
      <div class="card-section">
        <h4>Solution Criteria</h4>
        <p>{html_lib.escape(result.test_case.solution_criteria)}</p>
      </div>
    </div>
    <div class="output-section">
      <div class="output-inner">
        <div class="tabs">
          <button class="tab-btn active" data-tab="assessment">Assessment</button>
          <button class="tab-btn" data-tab="output">Output</button>
        </div>
        <div class="tab-panel" data-panel="assessment">
          <div class="score-breakdown">
            <span class="score-pill">Model&thinsp;grade: {score:.1f}&thinsp;/&thinsp;{max_score}</span>
          </div>
          <p class="assessment-reasoning">{html_lib.escape(grade.reasoning)}</p>
          <div class="assessment-cols">
            <div class="assessment-strengths">
              <h4>Strengths</h4>
              <ul>{li_items(grade.strengths)}</ul>
            </div>
            <div class="assessment-weaknesses">
              <h4>Weaknesses</h4>
              <ul>{li_items(grade.weaknesses)}</ul>
            </div>
          </div>
        </div>
        <div class="tab-panel hidden" data-panel="output">
          <div class="output-rendered"></div>
          <div class="md-source" hidden>{html_lib.escape(result.output)}</div>
        </div>
      </div>
    </div>
  </div>
"""

    report = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Evaluation Report</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; background: #0f1117; color: #e2e8f0; padding: 2rem 1.5rem; min-height: 100vh; }}
    .container {{ max-width: 860px; margin: 0 auto; }}

    .overall {{
      background: linear-gradient(135deg, #1e2235 0%, #252b42 100%);
      border: 1px solid #2d3450; border-radius: 12px;
      padding: 1.75rem 2rem; margin-bottom: 1rem;
    }}
    .overall h1 {{ font-size: 1.35rem; font-weight: 600; margin-bottom: 0.2rem; }}
    .overall-desc {{ font-size: 0.88rem; color: #94a3b8; margin: 0.35rem 0 0.2rem; max-width: 480px; }}

    .stats {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; }}
    .stat-card {{
      flex: 1; background: #1a1f2e; border: 1px solid #2d3450; border-radius: 10px;
      padding: 1.1rem 1.4rem;
    }}
    .stat-label {{
      font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: #64748b; margin-bottom: 0.45rem;
    }}
    .stat-value {{ font-size: 1.75rem; font-weight: 700; color: #e2e8f0; line-height: 1; }}
    .stat-value small {{ font-size: 0.95rem; color: #94a3b8; font-weight: 400; }}
    .stat-value.rate-high {{ color: #4ade80; }}
    .stat-value.rate-mid  {{ color: #fbbf24; }}
    .stat-value.rate-low  {{ color: #f87171; }}

    .card {{ background: #1a1f2e; border: 1px solid #2d3450; border-radius: 10px; margin-bottom: 0.85rem; overflow: hidden; }}

    .card-toggle {{ padding: 1.1rem 1.4rem; cursor: pointer; user-select: none; transition: background 0.15s; }}
    .card-toggle:hover {{ background: #1e2438; }}
    .toggle-top {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.55rem; }}
    .task-num {{ font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.09em; color: #64748b; }}
    .toggle-right {{ display: flex; align-items: center; gap: 0.65rem; }}

    .score-badge {{ font-size: 0.78rem; font-weight: 700; padding: 0.18rem 0.6rem; border-radius: 20px; }}
    .score-high {{ background: #14532d; color: #4ade80; }}
    .score-mid  {{ background: #713f12; color: #fbbf24; }}
    .score-low  {{ background: #7f1d1d; color: #f87171; }}

    .chevron {{ font-size: 1.3rem; color: #64748b; display: inline-block; transition: transform 0.3s ease; line-height: 1; }}
    .card.open .chevron {{ transform: rotate(90deg); }}

    .card-section {{ margin-top: 0.85rem; }}
    .card-section h4 {{
      font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: #818cf8; margin-bottom: 0.4rem;
    }}
    .card-section p {{ font-size: 0.87rem; line-height: 1.6; color: #cbd5e1; }}

    .input-table-wrap {{
      border: 1px solid #2d3450; border-radius: 8px; overflow: hidden; margin-top: 0.4rem;
    }}
    .input-table {{ border-collapse: collapse; width: 100%; font-size: 0.87rem; }}
    .input-table tr:nth-child(odd) {{ background: #181d2e; }}
    .input-table tr:nth-child(even) {{ background: #1c2235; }}
    .input-table td {{ padding: 0.5rem 0.85rem; border-bottom: 1px solid #2d3450; }}
    .input-table tr:last-child td {{ border-bottom: none; }}
    .input-table .input-key {{ color: #94a3b8; font-weight: 600; width: 35%; }}
    .input-table .input-value {{ color: #e2e8f0; }}

    .output-section {{ max-height: 0; overflow: hidden; transition: max-height 0.35s ease; border-top: 1px solid transparent; }}
    .card.open .output-section {{ border-top-color: #2d3450; }}
    .output-inner {{ padding: 1.25rem 1.4rem; }}

    /* Tabs */
    .tabs {{ display: flex; gap: 0.25rem; border-bottom: 1px solid #2d3450; margin-bottom: 1rem; }}
    .tab-btn {{
      background: none; border: none; cursor: pointer;
      font-size: 0.82rem; font-weight: 600; padding: 0.45rem 0.85rem;
      color: #64748b; border-bottom: 2px solid transparent;
      margin-bottom: -1px; transition: color 0.15s, border-color 0.15s;
    }}
    .tab-btn:hover {{ color: #94a3b8; }}
    .tab-btn.active {{ color: #e2e8f0; border-bottom-color: #6366f1; }}

    .tab-panel.hidden {{ display: none; }}

    /* Assessment panel */
    .score-breakdown {{ display: flex; gap: 0.5rem; margin-bottom: 0.85rem; }}
    .score-pill {{
      font-size: 0.78rem; font-weight: 600; color: #94a3b8;
      background: #252b42; border: 1px solid #2d3450;
      border-radius: 20px; padding: 0.2rem 0.65rem;
    }}
    .assessment-reasoning {{
      font-size: 0.88rem; line-height: 1.65; color: #94a3b8;
      font-style: italic; margin-bottom: 1rem;
    }}
    .assessment-cols {{ display: flex; gap: 1.25rem; }}
    .assessment-strengths, .assessment-weaknesses {{ flex: 1; }}
    .assessment-strengths h4, .assessment-weaknesses h4 {{
      font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; margin-bottom: 0.5rem;
    }}
    .assessment-strengths h4 {{ color: #4ade80; }}
    .assessment-weaknesses h4 {{ color: #f87171; }}
    .assessment-strengths ul, .assessment-weaknesses ul {{
      list-style: none; display: flex; flex-direction: column; gap: 0.35rem;
    }}
    .assessment-strengths li, .assessment-weaknesses li {{
      font-size: 0.87rem; line-height: 1.5; padding-left: 1rem; position: relative;
    }}
    .assessment-strengths li::before {{ content: "+"; position: absolute; left: 0; color: #4ade80; font-weight: 700; }}
    .assessment-weaknesses li::before {{ content: "−"; position: absolute; left: 0; color: #f87171; font-weight: 700; }}
    .assessment-strengths li {{ color: #cbd5e1; }}
    .assessment-weaknesses li {{ color: #cbd5e1; }}

    /* Output panel (markdown) */
    .output-rendered h1, .output-rendered h2, .output-rendered h3, .output-rendered h4 {{
      color: #e2e8f0; font-weight: 600; margin: 1.2rem 0 0.45rem;
    }}
    .output-rendered h1 {{ font-size: 1.25rem; }}
    .output-rendered h2 {{ font-size: 1.1rem; }}
    .output-rendered h3 {{ font-size: 0.97rem; }}
    .output-rendered h1:first-child, .output-rendered h2:first-child, .output-rendered h3:first-child {{ margin-top: 0; }}
    .output-rendered p {{ color: #cbd5e1; font-size: 0.91rem; line-height: 1.65; margin-bottom: 0.65rem; }}
    .output-rendered ul, .output-rendered ol {{ color: #cbd5e1; font-size: 0.91rem; margin: 0.4rem 0 0.65rem 1.4rem; }}
    .output-rendered li {{ margin-bottom: 0.2rem; line-height: 1.55; }}
    .output-rendered code:not(pre code) {{
      background: #282c34; color: #e06c75;
      padding: 0.15em 0.4em; border-radius: 4px;
      font-size: 0.87em; font-family: 'Menlo', 'Consolas', monospace;
    }}
    .output-rendered pre {{ margin: 0.65rem 0; border-radius: 8px; overflow-x: auto; }}
    .output-rendered pre code {{ font-size: 0.84rem; }}
    .output-rendered table {{ border-collapse: collapse; width: 100%; margin: 0.65rem 0; font-size: 0.87rem; }}
    .output-rendered th {{ background: #252b42; color: #94a3b8; font-weight: 600; padding: 0.45rem 0.7rem; text-align: left; border: 1px solid #2d3450; }}
    .output-rendered td {{ padding: 0.4rem 0.7rem; border: 1px solid #2d3450; color: #cbd5e1; }}
    .output-rendered tr:nth-child(even) td {{ background: #1e2438; }}
    .output-rendered blockquote {{ border-left: 3px solid #4ade80; padding: 0.45rem 0.9rem; margin: 0.65rem 0; color: #94a3b8; font-style: italic; }}
    .output-rendered hr {{ border: none; border-top: 1px solid #2d3450; margin: 0.9rem 0; }}
    .output-rendered strong {{ color: #e2e8f0; }}
    .output-rendered a {{ color: #60a5fa; text-decoration: none; }}
    .output-rendered a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="overall">
      <div>
        <h1>Evaluation Report</h1>
        <div class="overall-desc">{html_lib.escape(task_description)}</div>
      </div>
    </div>

    <div class="stats">
      <div class="stat-card">
        <div class="stat-label">Total Test Cases</div>
        <div class="stat-value">{len(results)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Average Score</div>
        <div class="stat-value">{overall:.1f} <small>/ {max_score}</small></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Pass Rate (&ge;{pass_threshold:g})</div>
        <div class="stat-value {rate_class(pass_rate)}">{pass_rate:.1f}%</div>
      </div>
    </div>

{cards_html}  </div>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked@9/marked.min.js"></script>
  <script>
    document.querySelectorAll('.card').forEach(card => {{
      const rendered = card.querySelector('.output-rendered');
      const source = card.querySelector('.md-source');
      rendered.innerHTML = marked.parse(source.textContent);
    }});
    hljs.highlightAll();

    function switchTab(card, tabName) {{
      card.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tabName));
      card.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('hidden', p.dataset.panel !== tabName));
    }}

    document.querySelectorAll('.tab-btn').forEach(btn => {{
      btn.addEventListener('click', e => {{
        e.stopPropagation();
        const card = btn.closest('.card');
        switchTab(card, btn.dataset.tab);
        const section = card.querySelector('.output-section');
        section.style.maxHeight = section.scrollHeight + 'px';
      }});
    }});

    document.querySelectorAll('.card-toggle').forEach(toggle => {{
      toggle.addEventListener('click', () => {{
        const card = toggle.closest('.card');
        const isOpen = card.classList.contains('open');

        document.querySelectorAll('.card.open').forEach(openCard => {{
          openCard.classList.remove('open');
          openCard.querySelector('.output-section').style.maxHeight = '0';
        }});

        if (!isOpen) {{
          switchTab(card, 'assessment');
          card.classList.add('open');
          const section = card.querySelector('.output-section');
          section.style.maxHeight = section.scrollHeight + 'px';
        }}
      }});
    }});
  </script>
</body>
</html>
"""

    path = Path(output_path)
    path.write_text(report)
    print(f"Report written to {path}")
